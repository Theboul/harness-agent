"""The block that asks the user to approve a tool call (HU-06-05 / T004, AC-01, AC-02)."""

from __future__ import annotations

from typing import Any

import pytest

from harness_agent.cli.approval_view import RULE_WIDTH, approval_block
from harness_agent.cli.style import ESCAPE, Style

SENTINEL = "VALOR-DE-PRUEBA-123"


def details(tool: str = "shell", **arguments: Any) -> dict[str, Any]:
    return {
        "tool": tool,
        "arguments": dict(arguments),
        "effect": "Runs a command in the work area",
        "risk": "high",
    }


def block(**arguments: Any) -> list[str]:
    return approval_block("shell", details(**arguments))


class TestLayout:
    def test_the_command_block_has_the_parts_in_a_fixed_order(self) -> None:
        lines = block(command="pytest -q tests/")

        assert lines[0] == "=" * RULE_WIDTH
        assert lines[1] == " APROBACIÓN REQUERIDA"
        assert lines[2] == "-" * RULE_WIDTH
        assert lines[3] == " El agente quiere ejecutar un comando:"
        assert lines[4] == "     pytest -q tests/"
        assert lines[5] == " Herramienta: shell"
        assert lines[6] == " Riesgo:      ALTO"
        effect = lines[7:-2]
        assert effect[0].startswith(" Efecto:      Ejecuta un comando en tu equipo")
        assert all(line.startswith(" " * 14) for line in effect[1:])
        assert lines[-2] == "-" * RULE_WIDTH
        assert lines[-1] == " [1] aprobar una vez   [2] aprobar para la sesión   [3] rechazar"

    def test_a_path_is_highlighted_and_named_in_the_sentence(self) -> None:
        lines = approval_block("write_file", details("write_file", path="src/app.py", content="x"))

        assert " El agente quiere usar la ruta indicada con 'write_file':" in lines
        assert "     src/app.py" in lines
        assert " Argumentos:" in lines
        assert "   content: x" in lines
        assert not any("path:" in line for line in lines)

    def test_the_command_wins_over_the_path(self) -> None:
        lines = block(command="ls", path="src")

        assert "     ls" in lines
        assert "   path: src" in lines

    def test_a_tool_without_command_or_path_lists_its_arguments(self) -> None:
        lines = approval_block("search", details("search", query="todo", limit=5))

        assert " El agente quiere usar la herramienta 'search'." in lines
        assert " Argumentos:" in lines
        assert "   query: todo" in lines and "   limit: 5" in lines

    def test_without_arguments_there_is_no_arguments_section(self) -> None:
        lines = approval_block("noop", details("noop"))

        assert not any(line.startswith(" Argumentos") for line in lines)

    def test_the_tool_name_falls_back_to_the_call(self) -> None:
        lines = approval_block("from_call", {"arguments": {}, "effect": "", "risk": "low"})

        assert " Herramienta: from_call" in lines


class TestRiskAndEffect:
    @pytest.mark.parametrize(
        ("risk", "word"),
        [("low", "BAJO"), ("medium", "MEDIO"), ("high", "ALTO"), ("weird", "DESCONOCIDO")],
    )
    def test_the_risk_is_a_word(self, risk: str, word: str) -> None:
        lines = approval_block("shell", {**details(command="ls"), "risk": risk})

        assert f" Riesgo:      {word}" in lines

    def test_a_missing_risk_and_effect_are_neutral(self) -> None:
        lines = approval_block("shell", {"tool": "shell", "arguments": {"command": "ls"}})

        assert " Riesgo:      DESCONOCIDO" in lines
        assert " Efecto:      (sin descripción)" in lines

    def test_malformed_details_never_raise(self) -> None:
        lines = approval_block("shell", {"arguments": 5, "effect": 3, "risk": None, "tool": 7})

        assert " Herramienta: shell" in lines
        assert " Efecto:      (sin descripción)" in lines


class TestHostileValues:
    def test_line_breaks_are_escaped_so_the_command_is_one_line(self) -> None:
        lines = block(command="echo a\nrm -rf x\r\nls")

        assert r"     echo a\nrm -rf x\nls" in lines
        assert not any("\n" in line or "\r" in line for line in lines)

    def test_control_sequences_and_bidirectional_marks_are_removed(self) -> None:
        lines = block(command="a\x1b[2J\u202eb\x00c")

        assert "     a[2Jbc" in lines
        assert not any(ESCAPE in line for line in lines)

    def test_a_long_command_is_bounded(self) -> None:
        lines = block(command="x" * 5000)

        main = next(line for line in lines if line.startswith("     x"))
        assert len(main) <= 5 + 400 and main.endswith("...")

    def test_a_huge_command_with_many_lines_keeps_the_block_short(self) -> None:
        lines = block(command="\n".join(f"line {n}" for n in range(40)) * 100)

        assert len(lines) <= 20

    def test_other_values_are_bounded_more_tightly(self) -> None:
        lines = block(command="ls", note="y" * 1000)

        shown = next(line for line in lines if line.startswith("   note:"))
        assert len(shown) <= len("   note: ") + 200

    @pytest.mark.parametrize("name", ["api_key", "Secret", "access_token", "PASSWORD", "auth"])
    def test_values_of_keys_that_look_like_secrets_are_hidden(self, name: str) -> None:
        lines = block(command="ls", **{name: SENTINEL})

        assert SENTINEL not in "\n".join(lines)
        assert f"   {name}: ***" in lines

    def test_a_secret_named_main_value_is_hidden_too(self) -> None:
        lines = approval_block("t", details("t", path="p", token=SENTINEL))

        assert SENTINEL not in "\n".join(lines)

    def test_many_arguments_are_summarized(self) -> None:
        lines = block(command="ls", **{f"k{i}": i for i in range(30)})

        assert "   k0: 0" in lines
        assert not any("k29" in line for line in lines)
        assert "   ... (y 10 más)" in lines

    def test_a_value_that_is_not_text_is_shown_bounded(self) -> None:
        lines = block(command=["a"] * 1000)

        assert any(line.startswith("     [") and line.endswith("...") for line in lines)

    def test_an_empty_command_is_not_highlighted_as_blank(self) -> None:
        lines = block(command="   ")

        assert "     (vacío)" in lines


class TestStyle:
    def test_a_plain_style_has_no_codes(self) -> None:
        assert not any(ESCAPE in line for line in block(command="ls"))

    def test_the_painted_text_without_codes_is_the_plain_text(self) -> None:
        import re

        plain = block(command="ls")
        painted = approval_block("shell", details(command="ls"), Style(enabled=True))

        assert any(ESCAPE in line for line in painted)
        stripped = [re.sub(re.escape(ESCAPE) + r"\[[0-9;]*m", "", line) for line in painted]
        assert stripped == plain


class TestEffect:
    """The effect is shown whole, wrapped, and in Spanish for the native tools (HU-06-02 / UX-b)."""

    LONG = (
        "Una descripción larga de lo que hace la herramienta de un servidor externo, que antes "
        "se cortaba con puntos suspensivos a los doscientos caracteres y dejaba a la persona sin "
        "saber qué iba a ocurrir realmente, porque lo importante solía estar al final del texto."
    )

    @staticmethod
    def effect_lines(lines: list[str]) -> list[str]:
        start = next(n for n, line in enumerate(lines) if line.startswith(" Efecto:"))
        end = next(n for n in range(start + 1, len(lines)) if lines[n] == "-" * RULE_WIDTH)
        return lines[start:end]

    def test_a_long_effect_is_wrapped_and_not_cut(self) -> None:
        lines = approval_block("remota", {**details("remota"), "effect": self.LONG})
        effect = self.effect_lines(lines)

        assert len(effect) > 1
        assert all(len(line) <= RULE_WIDTH for line in effect)
        assert " ".join(part.strip() for part in effect).replace("Efecto: ", "").split() == (
            self.LONG.split()
        )
        assert "…" not in "".join(effect) and "..." not in "".join(effect)

    def test_an_absurdly_long_effect_is_bounded(self) -> None:
        lines = approval_block("remota", {**details("remota"), "effect": "palabra " * 500})

        assert sum(len(line.strip()) for line in self.effect_lines(lines)) < 1_100
        assert self.effect_lines(lines)[-1].endswith("...")

    @pytest.mark.parametrize(
        ("tool", "start"),
        [
            ("leer_archivo", "Lee el contenido"),
            ("escribir_archivo", "Crea o reemplaza"),
            ("listar_archivos", "Lista los archivos"),
            ("buscar_texto", "Busca un texto"),
            ("shell", "Ejecuta un comando"),
            ("preguntar_usuario", "Te hace una pregunta"),
        ],
    )
    def test_native_tools_show_a_fixed_text_in_spanish(self, tool: str, start: str) -> None:
        effect = self.effect_lines(approval_block(tool, {**details(tool), "effect": "English"}))

        assert effect[0].startswith(f" Efecto:      {start}")
        assert "English" not in " ".join(effect)

    def test_a_tool_that_is_not_native_keeps_its_own_text(self) -> None:
        effect = self.effect_lines(approval_block("otra", {**details("otra"), "effect": "Hace x"}))

        assert effect == [" Efecto:      Hace x"]

    def test_the_effect_is_cleaned_of_controls_and_line_breaks(self) -> None:
        raw = "uno" + chr(27) + "[31m" + chr(10) + "dos" + chr(9) + "cuatro"
        lines = approval_block("otra", {**details("otra"), "effect": raw})

        assert self.effect_lines(lines) == [" Efecto:      uno[31m dos cuatro"]
