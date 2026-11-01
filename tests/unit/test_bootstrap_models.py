"""Composition root: models by alias and the planning mode (HU-06-06 / T005).

The provider factory is a recording double that returns a ``FakeProvider`` per model: no network,
key or console. The commands run through ``run_session`` with in-memory streams.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, compose, run_session
from harness_agent.config import HarnessConfig, ModelAlias, Secret
from harness_agent.core import Provider, ProviderResponse
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import SENTINEL, make_config

DEFAULT = "openai/modelo-de-prueba"
PLAN = "gemini/modelo-plan"
BUILD = "groq/modelo-build"
KEY = "clave-de-prueba-gemini"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class Factory:
    """Builds one ``FakeProvider`` per model and remembers each configuration it was given."""

    def __init__(self, failing: str | None = None) -> None:
        self.configs: list[HarnessConfig] = []
        self.providers: dict[str, FakeProvider] = {}
        self.failing = failing

    def __call__(self, config: HarnessConfig) -> Provider:
        self.configs.append(config)
        if config.model == self.failing:
            raise RuntimeError(SENTINEL)
        provider = FakeProvider([ProviderResponse(content=f"de {config.model}")] * 5)
        self.providers[config.model] = provider
        return provider

    @property
    def built(self) -> list[str]:
        return [config.model for config in self.configs]


def config_with(
    tmp_path: Path, *aliases: ModelAlias, workspace: bool = True, **options: object
) -> HarnessConfig:
    folder = tmp_path / "trabajo"
    folder.mkdir(exist_ok=True)
    base = make_config(tmp_path, workspace=folder if workspace else None, model=DEFAULT)
    return replace(base, models=aliases, **options)  # type: ignore[arg-type]


PLAN_ALIAS = ModelAlias("plan", PLAN, Secret(KEY), "GEMINI_API_KEY")
BUILD_ALIAS = ModelAlias("build", BUILD, Secret("clave-groq"), "GROQ_API_KEY")


def open_with(
    opened: list[Composition],
    config: HarnessConfig,
    factory: Factory,
    **options: object,
) -> Composition:
    composition = compose(config, provider_factory=factory, system_name="Linux", **options)  # type: ignore[arg-type]
    opened.append(composition)
    return composition


async def drive(composition: Composition, *lines: str) -> list[str]:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    shown = output.getvalue().replace("tarea> ", "").splitlines()
    assert shown[-1] == "Sesión terminada."
    return shown[:-1]


class TestWithoutAliases:
    def test_only_the_configured_provider_is_built(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        factory = Factory()

        composition = open_with(opened, config_with(tmp_path), factory)

        assert factory.built == [DEFAULT]
        assert composition.model_switch is not None and composition.model_switch.aliases == ()
        view = composition.model_view
        assert view is not None and view.models == () and view.planning is False

    async def test_model_shows_the_old_text(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path), Factory())

        shown = await drive(composition, "/model")

        assert shown[0] == f"Modelo: {DEFAULT}"
        assert not any(line.startswith("Modelos") for line in shown)

    async def test_an_alias_is_unknown(self, tmp_path: Path, opened: list[Composition]) -> None:
        composition = open_with(opened, config_with(tmp_path), Factory())

        shown = await drive(composition, "/model plan")

        assert shown[0] == "No existe el modelo 'plan'. Escribe /model para ver los disponibles."


class TestModelCommand:
    def test_the_providers_of_the_aliases_are_built_only_when_chosen(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        factory = Factory()

        open_with(opened, config_with(tmp_path, PLAN_ALIAS, BUILD_ALIAS), factory)

        assert factory.built == [DEFAULT]

    async def test_it_lists_the_aliases_and_never_a_key(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS, BUILD_ALIAS), Factory())

        shown = await drive(composition, "/model")

        assert shown[0] == f"Modelo: {DEFAULT} (predeterminado)"
        assert f"  plan  {PLAN}" in shown and f"  build  {BUILD}" in shown
        assert f"* predeterminado  {DEFAULT}" in shown
        assert KEY not in "\n".join(shown)

    async def test_choosing_an_alias_builds_it_with_its_own_model_and_key(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        factory = Factory()
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS, BUILD_ALIAS), factory)

        shown = await drive(composition, "/model plan", "/model")

        assert shown[0] == f"Modelo activo: {PLAN} (alias plan)."
        built = factory.configs[-1]
        assert (built.model, built.key_variable) == (PLAN, "GEMINI_API_KEY")
        assert built.api_key is not None and built.api_key.reveal() == KEY
        assert shown[1] == f"Modelo: {PLAN} (alias plan)"
        assert f"* plan  {PLAN}" in shown
        assert KEY not in "\n".join(shown)

    async def test_the_window_follows_the_active_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        from harness_agent.core import ContextSettings

        context = ContextSettings(windows=((PLAN, 100_000),))
        config = config_with(tmp_path, PLAN_ALIAS, context=context)
        composition = open_with(opened, config, Factory())

        shown = await drive(composition, "/model plan", "/model")

        assert "Ventana de contexto: 100.000 tokens" in shown

    async def test_the_default_word_goes_back(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS), Factory())

        shown = await drive(composition, "/model plan", "/model predeterminado")

        assert shown[1] == f"Modelo activo: {DEFAULT} (predeterminado)."

    async def test_a_missing_key_changes_nothing_and_names_the_variable(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        keyless = ModelAlias("plan", PLAN, None, "GEMINI_API_KEY")
        factory = Factory()
        composition = open_with(opened, config_with(tmp_path, keyless), factory)

        shown = await drive(composition, "/model plan", "/model")

        assert shown[0] == (
            "No se puede usar 'plan': falta la variable de entorno GEMINI_API_KEY. "
            "El modelo activo no cambia."
        )
        assert shown[1] == f"Modelo: {DEFAULT} (predeterminado)"
        assert factory.built == [DEFAULT]

    async def test_a_provider_without_key_needs_none(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        local = ModelAlias("local", "ollama/llama", None, None)
        composition = open_with(opened, config_with(tmp_path, local), Factory())

        shown = await drive(composition, "/model local")

        assert shown[0] == "Modelo activo: ollama/llama (alias local)."

    async def test_a_failing_provider_is_a_fixed_line_without_its_text(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS), Factory(failing=PLAN))

        shown = await drive(composition, "/model plan")

        assert shown[0] == "No se pudo cambiar a 'plan'. El modelo activo no cambia."
        assert SENTINEL not in "\n".join(shown)

    async def test_the_help_lists_the_commands(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path), Factory())

        shown = "\n".join(await drive(composition, "/ayuda"))

        assert "/plan" in shown and "/implementar" in shown and "/model" in shown

    async def test_a_new_session_records_the_active_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS), Factory())

        await drive(composition, "/model plan", "/nueva")

        models = {summary.model for summary in composition.store.list_sessions()}
        assert PLAN in models


class TestPlanMode:
    async def test_plan_switches_to_the_alias_and_turns_read_only_on(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS, BUILD_ALIAS), Factory())

        shown = await drive(composition, "/plan", "/model")

        assert shown[0] == (
            f"Modo planificación: modelo {PLAN}, solo lectura (se deniega toda escritura). "
            "Vuelve con /implementar."
        )
        assert shown[-1] == "Modo: planificación (solo lectura; vuelve con /implementar)."
        assert composition.read_only_switch is not None and composition.read_only_switch.enabled
        assert composition.work_mode.planning is True

    async def test_without_the_plan_alias_it_uses_the_default_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, BUILD_ALIAS), Factory())

        shown = await drive(composition, "/model build", "/plan")

        assert shown[1].startswith(f"Modo planificación: modelo {DEFAULT},")
        assert composition.read_only_switch is not None and composition.read_only_switch.enabled

    async def test_without_any_alias_it_only_turns_read_only_on(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path), Factory())

        shown = await drive(composition, "/plan")

        assert shown[0].startswith(f"Modo planificación: modelo {DEFAULT},")
        assert composition.read_only_switch is not None and composition.read_only_switch.enabled

    async def test_a_model_that_cannot_be_chosen_changes_nothing(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        keyless = ModelAlias("plan", PLAN, None, "GEMINI_API_KEY")
        composition = open_with(opened, config_with(tmp_path, keyless), Factory())

        shown = await drive(composition, "/plan")

        assert shown[0].startswith("No se puede usar 'plan': falta la variable")
        assert composition.read_only_switch is not None
        assert composition.read_only_switch.enabled is False
        assert composition.work_mode.planning is False

    async def test_implement_goes_back_to_build_and_turns_read_only_off(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS, BUILD_ALIAS), Factory())

        shown = await drive(composition, "/plan", "/implementar", "/model")

        assert shown[1] == (
            f"Modo implementación: modelo {BUILD}; las escrituras siguen la política de permisos."
        )
        assert not any(line.startswith("Modo:") for line in shown)
        assert composition.read_only_switch is not None
        assert composition.read_only_switch.enabled is False
        assert composition.work_mode.planning is False

    async def test_implement_without_build_uses_the_default_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS), Factory())

        shown = await drive(composition, "/plan", "/implementar")

        assert shown[1].startswith(f"Modo implementación: modelo {DEFAULT};")

    async def test_implement_cannot_turn_off_a_mode_fixed_at_the_start(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(
            opened, config_with(tmp_path, BUILD_ALIAS), Factory(), read_only=True
        )

        shown = await drive(composition, "/implementar", "/model")

        assert shown[1] == (
            f"Modo implementación: modelo {BUILD}. El solo lectura sigue activo porque se "
            "fijó al arrancar."
        )
        assert shown[-1] == "Modo: solo lectura (se deniega toda escritura)."
        assert composition.read_only_switch is not None and composition.read_only_switch.enabled

    async def test_implement_fails_without_changing_the_mode_when_build_is_unusable(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        keyless = ModelAlias("build", BUILD, None, "GROQ_API_KEY")
        composition = open_with(opened, config_with(tmp_path, PLAN_ALIAS, keyless), Factory())

        shown = await drive(composition, "/plan", "/implementar")

        assert shown[1].startswith("No se puede usar 'build': falta la variable")
        assert composition.read_only_switch is not None and composition.read_only_switch.enabled
        assert composition.work_mode.planning is True


class TestCompositionsWithoutTheSwitch:
    async def test_the_commands_say_they_are_not_available(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = open_with(opened, config_with(tmp_path), Factory())
        bare = replace(composition, model_switch=None, read_only_switch=None)

        shown = await drive(bare, "/model", "/model x", "/plan", "/implementar")

        assert shown == ["Modelo no disponible en esta ejecución."] * 4
