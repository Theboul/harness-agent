"""The README, the demo script and the architecture document must match the real system (HU-00-06).

Three documents are read: ``README.md``, ``docs/guion-demostracion.md`` and
``docs/arquitectura-implementada.md``. What they say about the program is compared with the program
itself, never with copied lists:

* G1: every ``/command`` they name is in the real ``/ayuda`` of a session with a task.
* G2: every ``--option`` of a ``harness`` command line is accepted by ``parse_arguments``.
* G3: every ``[section]`` of a ``toml`` block exists in ``config.example.toml``.
* G4: no story is called finished; a ``Pendiente`` story is always marked as deferred; the README
  has none of the obsolete phrases it used to carry.
* G5: every step of the demo script has time, command, expected output and plan B, the required
  steps add up to 10-15 minutes and the section of what is NOT demonstrated exists.
* G6: every relative link points to a file that exists.

The extractors are pure functions with their own tests on synthetic text, so a change in the
documents cannot hide a broken extractor.
"""

from __future__ import annotations

import asyncio
import io
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, StartupError, parse_arguments, run_session
from harness_agent.core import ProviderResponse
from tests.doubles import FakeProvider
from tests.integration.test_essential_context_agent_loop import make_task
from tests.unit.bootstrap_support import build, make_config

ROOT = Path(__file__).resolve().parents[2]
DOCS = ("README.md", "docs/guion-demostracion.md", "docs/arquitectura-implementada.md")
SCRIPT = "docs/guion-demostracion.md"
README = "README.md"
PROGRESS = ROOT / "docs" / "PROGRESO.md"
EXAMPLE = ROOT / "config.example.toml"

OBSOLETE_PHRASES = (
    "en desarrollo (sprint 1)",
    "aún no hay adaptador",
    "se documentará cuando exista",
    "observability/",
)
DEFERRED_MARKS = (
    "pendiente",
    "diferid",
    "no se demuestra",
    "no existe",
    "aún no",
    "todavía no",
    "no implementad",
)
FINISHED_WORDS = re.compile(r"\b(?:terminad|completad|hech)[oa]s?\b", re.IGNORECASE)
NEGATION = re.compile(r"\bn[oi]\b[^.|]{0,18}$", re.IGNORECASE)
STORY_ID = re.compile(r"\b(?:HU-\d\d-\d\d(?:\.\d)?|HU-IN-\d\d|SPK-\d\d)\b")
FENCE = re.compile(r"^```([\w-]*)[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE = re.compile(r"`([^`\n]+)`")
SLASH = re.compile(r"^/[a-záéíóúñ]+$")
FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z-]*)")
SECTION = re.compile(r"^\s*#?\s*\[([A-Za-z_][\w.\-<>]*)\]\s*$")
SPAN_SECTION = re.compile(r"secci(?:ón|ones)\s+`\[([A-Za-z_][\w.\-]*)\]`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
HELP_LINE = re.compile(r"^  (/[a-záéíóúñ]+)  ", re.MULTILINE)
PROMPTS = ("PS> ", "PS C:\\> ", "$ ", "> ", "tarea> ")
HARNESS_STARTS = ("harness", "python -m harness_agent", "py -m harness_agent")
STEP_HEADING = re.compile(r"^###\s+(Paso|Opcional)\s+(\d+)\b.*$", re.MULTILINE)
TIME = re.compile(r"Tiempo:\s*([\d]+(?:[.,]\d+)?)\s*min", re.IGNORECASE)
MIN_TOTAL, MAX_TOTAL = 10.0, 15.0


# --- Extractors (pure) -------------------------------------------------------------------------


def fenced_blocks(text: str) -> list[tuple[str, str]]:
    """The fenced code blocks of ``text`` as ``(language, body)``."""
    return [(match.group(1).lower(), match.group(2)) for match in FENCE.finditer(text)]


def outside_fences(text: str) -> str:
    """``text`` without its fenced blocks."""
    return FENCE.sub("", text)


def code_fragments(text: str) -> list[str]:
    """Inline code spans and the lines of the non-diagram blocks, prompts removed."""
    fragments = [span.strip() for span in INLINE.findall(outside_fences(text))]
    for language, body in fenced_blocks(text):
        if language in {"mermaid", "toml"}:
            continue
        fragments.extend(line.strip() for line in body.splitlines())
    cleaned: list[str] = []
    for fragment in fragments:
        for prompt in PROMPTS:
            if fragment.startswith(prompt):
                fragment = fragment[len(prompt) :].strip()
                break
        if fragment and not fragment.startswith("#"):
            cleaned.append(fragment)
    return cleaned


def slash_commands(text: str) -> set[str]:
    """The ``/commands`` named: a code fragment whose first word is a slash and a lowercase word."""
    return {first for fragment in code_fragments(text) if SLASH.match(first := fragment.split()[0])}


def harness_flags(text: str) -> set[str]:
    """The ``--options`` of the code lines that run ``harness`` (other tools are ignored)."""
    flags: set[str] = set()
    for fragment in code_fragments(text):
        words = fragment.replace("\\", "/").lower()
        if (
            words.startswith(HARNESS_STARTS)
            or "/scripts/harness" in words
            or "/bin/harness" in words
        ):
            flags.update(FLAG.findall(fragment))
    return flags


def toml_sections(text: str) -> set[str]:
    """The ``[sections]`` of ``toml`` blocks (live ones) and those named as "sección `[x]`"."""
    sections: set[str] = set()
    for language, body in fenced_blocks(text):
        if language == "toml":
            for line in body.splitlines():
                if line.lstrip().startswith("#"):
                    continue
                match = SECTION.match(line)
                if match:
                    sections.add(match.group(1))
    sections.update(SPAN_SECTION.findall(outside_fences(text)))
    return sections


def story_lines(text: str) -> list[tuple[int, str]]:
    """The lines (1-based number, text) that name a story."""
    return [(n, line) for n, line in enumerate(text.splitlines(), 1) if STORY_ID.search(line)]


def finished_claims(line: str) -> bool:
    """A line that calls something finished, unless the word is denied just before."""
    for match in FINISHED_WORDS.finditer(line):
        if not NEGATION.search(line[: match.start()]):
            return True
    return False


def relative_links(text: str) -> list[str]:
    """The relative targets of the markdown links (anchors cut, external links left out)."""
    targets: list[str] = []
    for target in LINK.findall(outside_fences(text)):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        targets.append(target.split("#", 1)[0])
    return [target for target in targets if target]


def steps(script: str) -> list[tuple[str, int, str]]:
    """The steps as ``(kind, number, body)``; a body ends at the next ``##`` or ``###``."""
    matches = list(STEP_HEADING.finditer(script))
    found: list[tuple[str, int, str]] = []
    for match in matches:
        end = len(script)
        following = re.search(r"^#{2,3}\s", script[match.end() :], re.MULTILINE)
        if following:
            end = match.end() + following.start()
        found.append((match.group(1), int(match.group(2)), script[match.start() : end]))
    return found


def step_problems(kind: str, number: int, body: str) -> list[str]:
    """What a step lacks: time, command, expected output or plan B."""
    problems: list[str] = []
    if not TIME.search(body):
        problems.append("Tiempo")
    for label in ("Comando:", "Salida esperada:"):
        if label not in body:
            problems.append(label.rstrip(":"))
    plan = re.search(r"Plan B:\s*(.*)", body)
    if plan is None or len(plan.group(1).strip()) < 10:
        problems.append("Plan B")
    return [f"{kind} {number}: falta {problem}" for problem in problems]


def required_minutes(script: str) -> float:
    """The sum of the minutes of the required steps (``Paso N``)."""
    total = 0.0
    for kind, _number, body in steps(script):
        found = TIME.search(body)
        if kind == "Paso" and found:
            total += float(found.group(1).replace(",", "."))
    return total


# --- Real sources ------------------------------------------------------------------------------


def progress_states() -> dict[str, str]:
    """Story id -> state, read from the tables of ``docs/PROGRESO.md``."""
    states: dict[str, str] = {}
    section = ""
    text = PROGRESS.read_bytes().decode("utf-8").replace("\r\n", "\n")
    for line in text.split("\n"):
        if line.startswith("## "):
            section = line[3:].strip()
        if line.startswith("| ") and section.startswith(("Sprint", "Backlog")):
            cells = line[2:].split(" | ", 6)
            if len(cells) < 7:
                continue
            link = re.match(r"\[([^\]]+)\]", cells[0])
            story = link.group(1) if link else cells[0].split(" (")[0]
            if STORY_ID.fullmatch(story):
                states[story] = cells[5]
    return states


def example_sections() -> set[str]:
    """The sections of ``config.example.toml``, active or commented out."""
    found: set[str] = set()
    for line in EXAMPLE.read_text("utf-8").splitlines():
        match = SECTION.match(line)
        if match:
            found.add(match.group(1))
    return found


def section_exists(name: str, known: set[str]) -> bool:
    """Known when the example has it (``mcp_servers.<any>`` follows ``mcp_servers.demo``)."""
    return name in known or (name.startswith("mcp_servers.") and "mcp_servers.demo" in known)


async def _real_help(tmp_path: Path) -> str:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    opened: list[Composition] = []
    provider = FakeProvider([ProviderResponse(content="x")])
    composition = build(
        opened,
        make_config(tmp_path, workspace=workspace),
        provider,
        task=make_task(),
        system_name="Linux",
    )
    output = io.StringIO()
    try:
        await run_session(composition, input_stream=io.StringIO("/ayuda\n/salir\n"), output=output)
    finally:
        for item in opened:
            item.close()
    return output.getvalue()


@pytest.fixture(scope="module")
def real_commands(tmp_path_factory: pytest.TempPathFactory) -> set[str]:
    """The commands the real console lists in ``/ayuda`` for a session with a task."""
    shown = asyncio.run(_real_help(tmp_path_factory.mktemp("ayuda")))
    return set(HELP_LINE.findall(shown))


def accepts(flag: str) -> bool:
    """Whether ``parse_arguments`` knows the option (a missing value is not 'unknown')."""
    for argv in ([flag], [flag, "1"]):
        try:
            parse_arguments(argv)
        except StartupError as error:
            if "no reconocido" not in str(error):
                return True
        else:
            return True
    return False


def read_doc(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        pytest.fail(f"Falta el documento {relative}: HU-00-06 lo exige.")
    return path.read_text("utf-8")


@pytest.fixture(params=DOCS)
def doc(request: pytest.FixtureRequest) -> Iterator[tuple[str, str]]:
    name = str(request.param)
    yield name, read_doc(name)


# --- G1 to G6 on the real documents --------------------------------------------------------------


def test_g1_the_commands_the_documents_name_exist(
    doc: tuple[str, str], real_commands: set[str]
) -> None:
    name, text = doc
    unknown = sorted(slash_commands(text) - real_commands)
    assert not unknown, f"{name} nombra comandos que /ayuda no lista: {unknown}"


def test_g1_the_real_console_lists_the_twelve_commands(real_commands: set[str]) -> None:
    assert len(real_commands) == 12 and "/criterios" in real_commands


def test_g1_the_readme_names_every_real_command(real_commands: set[str]) -> None:
    missing = sorted(real_commands - slash_commands(read_doc(README)))
    assert not missing, f"README.md no explica estos comandos: {missing}"


def test_g2_the_options_of_the_harness_lines_are_accepted(doc: tuple[str, str]) -> None:
    name, text = doc
    unknown = sorted(flag for flag in harness_flags(text) if not accepts(flag))
    assert not unknown, f"{name} usa opciones que harness no acepta: {unknown}"


def test_g2_the_readme_explains_the_three_options() -> None:
    flags = harness_flags(read_doc(README))
    assert {"--tarea", "--issue", "--solo-lectura"} <= flags


def test_g3_the_config_sections_exist_in_the_example(doc: tuple[str, str]) -> None:
    name, text = doc
    known = example_sections()
    unknown = sorted(s for s in toml_sections(text) if not section_exists(s, known))
    assert not unknown, f"{name} cita secciones que config.example.toml no tiene: {unknown}"


def test_g4_no_story_is_called_finished(doc: tuple[str, str]) -> None:
    name, text = doc
    bad = [(n, line.strip()) for n, line in story_lines(text) if finished_claims(line)]
    assert not bad, f"{name} llama terminada a una historia (usa «En revisión»): {bad}"


def test_g4_a_pending_story_is_always_marked_as_deferred(doc: tuple[str, str]) -> None:
    name, text = doc
    states = progress_states()
    bad: list[tuple[int, str]] = []
    for number, line in story_lines(text):
        pending = [s for s in STORY_ID.findall(line) if states.get(s) == "Pendiente"]
        if pending and not any(mark in line.lower() for mark in DEFERRED_MARKS):
            bad.append((number, line.strip()[:100]))
    assert not bad, f"{name} cita historias Pendiente sin marcarlas como diferidas: {bad}"


def test_g4_the_readme_has_none_of_the_obsolete_phrases() -> None:
    text = read_doc(README).lower()
    found = [phrase for phrase in OBSOLETE_PHRASES if phrase in text]
    assert not found, f"README.md conserva frases obsoletas: {found}"


def test_g5_the_demo_script_has_complete_steps_and_the_right_length() -> None:
    script = read_doc(SCRIPT)
    found = steps(script)
    assert [n for kind, n, _ in found if kind == "Paso"], "el guion no tiene pasos"
    problems = [p for kind, number, body in found for p in step_problems(kind, number, body)]
    assert not problems, f"pasos incompletos en el guion: {problems}"
    total = required_minutes(script)
    assert MIN_TOTAL <= total <= MAX_TOTAL, f"los pasos obligatorios suman {total} min"
    assert "## Lo que NO se demuestra" in script


def test_g6_the_relative_links_point_to_existing_files(doc: tuple[str, str]) -> None:
    name, text = doc
    base = (ROOT / name).parent
    broken = [t for t in relative_links(text) if not (base / t).resolve().exists()]
    assert not broken, f"{name} enlaza archivos que no existen: {broken}"


# --- Self-tests of the extractors (synthetic text) -----------------------------------------------

SAMPLE = """\
Usa `/model` o `/reanudar <id>`; la ruta `/tmp/x` y `/Users/yo` no son comandos.

```bash
harness --tarea tarea.md --solo-lectura
pytest --cov=harness_agent --no-cov
> /compactar
# /comentario
```

```toml
[memory]
enabled = true
# [failover]
```

Ver la sección `[subagents]`, el error `[memoria_llena]` y [guion](docs/guion.md#paso-1), [web](https://example.org/a).
"""


def test_the_slash_commands_skip_paths_and_comments() -> None:
    assert slash_commands(SAMPLE) == {"/model", "/reanudar", "/compactar"}


def test_the_flags_come_only_from_harness_lines() -> None:
    assert harness_flags(SAMPLE) == {"--tarea", "--solo-lectura"}


def test_the_toml_sections_skip_commented_ones() -> None:
    assert toml_sections(SAMPLE) == {"memory", "subagents"}


def test_the_links_keep_only_relative_files() -> None:
    assert relative_links(SAMPLE) == ["docs/guion.md"]


def test_finished_claims_ignore_a_denied_word() -> None:
    assert finished_claims("HU-11-07 está terminada")
    assert not finished_claims("HU-11-07 no está terminada")
    assert not finished_claims("HU-11-07 En revisión")


def test_the_step_checks_find_what_is_missing() -> None:
    full = (
        "### Paso 1 — a (2 min)\n- Tiempo: 2 min\n- Comando: `x`\n"
        "- Salida esperada: y\n- Plan B: di esto al público\n"
    )
    assert step_problems("Paso", 1, full) == []
    assert step_problems("Paso", 2, full.replace("Plan B", "Otro")) == ["Paso 2: falta Plan B"]
    assert required_minutes(full + "### Opcional 1 — b (9 min)\n- Tiempo: 9 min\n") == 2.0


def test_the_unknown_option_is_not_accepted() -> None:
    assert accepts("--tarea") and accepts("--issue") and accepts("--solo-lectura")
    assert not accepts("--inventada")
