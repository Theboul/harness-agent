"""HU-06-06 with the real composition, loop, retries and policy chain (T006).

AC-01: after ``/model build`` the next calls go to the model of ``build`` and the history is kept.
AC-03: ``/plan`` uses the ``plan`` model and denies every write; ``/implementar`` goes back to the
``build`` model and the write inside the work area is allowed again, as without the mode.
The providers are doubles.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import HarnessConfig, ModelAlias, Secret
from harness_agent.core import Message, Provider, ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import make_config

DEFAULT, PLAN, BUILD = "openai/base", "gemini/plan-model", "groq/build-model"
DENIED = "[permission_denied]"
WRITE = ToolCall(id="w1", name="escribir_archivo", arguments={"path": "nuevo.txt", "content": "x"})
WRITE_AGAIN = ToolCall(
    id="w2", name="escribir_archivo", arguments={"path": "otro.txt", "content": "x"}
)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def tool_answers(messages: list[Message]) -> list[str]:
    return [str(message.content) for message in messages if message.role is Role.TOOL]


async def test_ac_01_and_ac_03_the_models_and_the_mode_follow_the_commands(
    tmp_path: Path, opened: list[Composition]
) -> None:
    workspace = tmp_path / "trabajo"
    workspace.mkdir()
    providers = {
        DEFAULT: FakeProvider([ProviderResponse(content="de base")]),
        PLAN: FakeProvider(
            [ProviderResponse(tool_calls=[WRITE]), ProviderResponse(content="plan listo")]
        ),
        BUILD: FakeProvider(
            [ProviderResponse(tool_calls=[WRITE_AGAIN]), ProviderResponse(content="hecho")]
        ),
    }

    def factory(config: HarnessConfig) -> Provider:
        return providers[config.model]

    config = replace(
        make_config(tmp_path, workspace=workspace, model=DEFAULT),
        models=(
            ModelAlias("plan", PLAN, Secret("k1"), "GEMINI_API_KEY"),
            ModelAlias("build", BUILD, Secret("k2"), "GROQ_API_KEY"),
        ),
    )
    composition = compose(config, provider_factory=factory, system_name="Linux")
    opened.append(composition)
    output = io.StringIO()

    await run_session(
        composition,
        input_stream=io.StringIO("/plan\nexplora el proyecto\n/implementar\nescribe el archivo\n"),
        output=output,
    )

    # /plan: the model of ``plan`` answered and its write was denied before touching the disk.
    assert providers[PLAN].call_count == 2
    assert tool_answers(providers[PLAN].received[1])[0].startswith(DENIED)
    assert not (workspace / "nuevo.txt").exists()
    # /implementar: the model of ``build`` answered, saw the whole history and its write is asked
    # as always (a write inside the work area is allowed), not denied by the mode.
    assert providers[BUILD].call_count == 2
    seen = [str(message.content) for message in providers[BUILD].received[0]]
    assert "explora el proyecto" in seen and "escribe el archivo" in seen
    answer = tool_answers(providers[BUILD].received[1])[-1]
    assert answer.startswith("Archivo creado")
    assert (workspace / "otro.txt").exists()
    assert providers[DEFAULT].call_count == 0
    assert "k1" not in output.getvalue() and "k2" not in output.getvalue()


async def test_a_model_chosen_by_hand_receives_the_next_turn(
    tmp_path: Path, opened: list[Composition]
) -> None:
    providers = {
        DEFAULT: FakeProvider([ProviderResponse(content="uno")]),
        BUILD: FakeProvider([ProviderResponse(content="dos")]),
    }
    config = replace(
        make_config(tmp_path, model=DEFAULT),
        models=(ModelAlias("build", BUILD, Secret("k2"), "GROQ_API_KEY"),),
    )
    composition = compose(
        config, provider_factory=lambda c: providers[c.model], system_name="Linux"
    )
    opened.append(composition)

    await run_session(
        composition,
        input_stream=io.StringIO("primera\n/model build\nsegunda\n/model predeterminado\n"),
        output=io.StringIO(),
    )

    assert providers[DEFAULT].call_count == 1 and providers[BUILD].call_count == 1
    assert "primera" in [str(m.content) for m in providers[BUILD].received[0]]
