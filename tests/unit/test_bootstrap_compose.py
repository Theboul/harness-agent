"""Composition root (propuesta HU-00-08 / T003): ``compose`` builds the pieces and fails closed.

``compose`` receives the already loaded configuration and builds, in a fixed order, everything the
loop needs. The provider comes from an injected factory (``FakeProvider``), the clock and the
identifiers are injected, and the database is a temporary file: no network, key or console.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness_agent import bootstrap
from harness_agent.adapters.storage import SessionStoreError, SqliteSessionStore
from harness_agent.bootstrap import (
    AREA_NOT_A_FOLDER_NOTICE,
    NO_AREA_NOTICE,
    TEST_ONLY_PROVIDER_MESSAGE,
    Composition,
    StartupError,
    compose,
)
from harness_agent.config import HarnessConfig, Secret
from harness_agent.core import Event, EventType, Provider, ProviderResponse, Role, ToolCall
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import (
    FIXED_TIME,
    SENTINEL,
    build,
    make_config,
    make_event,
    one_turn,
    scripted,
)


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class TestTheSession:
    def test_the_session_exists_in_the_store_with_the_configured_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        config = make_config(tmp_path, workspace=tmp_path)

        composition = build(opened, config, id_factory=lambda: "sesion-fija")

        assert composition.session_id == "sesion-fija"
        stored = composition.store.get_session("sesion-fija")
        assert stored is not None
        assert stored.model == config.model
        assert stored.status == "active"

    def test_the_injected_clock_reaches_the_store(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(
            opened, make_config(tmp_path, workspace=tmp_path), clock=lambda: FIXED_TIME
        )

        stored = composition.store.get_session(composition.session_id)

        assert stored is not None
        assert stored.created_at == FIXED_TIME

    def test_the_database_is_created_with_its_folders(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        build(opened, make_config(tmp_path, workspace=tmp_path))

        assert (tmp_path / "datos" / "sesiones.db").is_file()


class TestTheRecorder:
    def test_every_event_type_emitted_on_the_bus_is_saved(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        for index, event_type in enumerate(EventType):
            composition.bus.emit(make_event(event_type, composition.session_id, index))

        saved = composition.store.load_session(composition.session_id)
        # context_compacted is stored by the compaction archive, not by the recorder (R5, HU-02-03).
        expected = [kind for kind in EventType if kind is not EventType.CONTEXT_COMPACTED]
        assert [event.type for event in saved] == expected

    async def test_the_events_of_a_real_turn_are_saved_before_anyone_else_sees_them(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))
        seen_in_store: list[int] = []

        def late_subscriber(event: Event) -> None:
            seen_in_store.append(len(composition.store.load_session(event.session_id)))

        composition.bus.subscribe(EventType.USER_MESSAGE, late_subscriber)

        await one_turn(composition)

        assert seen_in_store == [1]
        assert len(composition.store.load_session(composition.session_id)) > 1


class TestTheTools:
    async def test_the_file_tools_and_the_shell_are_offered_to_the_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        provider = scripted("listo")
        composition = build(opened, make_config(tmp_path, workspace=tmp_path), provider)

        await one_turn(composition)

        assert provider.received_tools[0] is not None
        names = sorted(tool.name for tool in provider.received_tools[0] or [])
        assert names == [
            "buscar_texto",
            "escribir_archivo",
            "leer_archivo",
            "listar_archivos",
            "shell",
        ]

    def test_with_an_area_there_are_no_notices(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        assert composition.notices == ()

    @pytest.mark.parametrize(
        ("name", "arguments"),
        [
            ("leer_archivo", {"path": "a.txt"}),
            ("escribir_archivo", {"path": "a.txt", "content": "x"}),
            ("listar_archivos", {"path": "."}),
            ("buscar_texto", {"path": ".", "query": "x"}),
        ],
        ids=["leer", "escribir", "listar", "buscar"],
    )
    async def test_without_an_area_there_is_one_notice_and_every_tool_is_denied(
        self, tmp_path: Path, opened: list[Composition], name: str, arguments: dict[str, Any]
    ) -> None:
        provider = FakeProvider(
            [
                ProviderResponse(tool_calls=[ToolCall(id="c1", name=name, arguments=arguments)]),
                ProviderResponse(content="listo"),
            ]
        )
        composition = build(opened, make_config(tmp_path, workspace=None), provider)

        result = await one_turn(composition)

        assert composition.notices == (NO_AREA_NOTICE,)
        tool_messages = [m for m in result.history if m.role is Role.TOOL]
        assert tool_messages[0].content.startswith("[approval_required_unavailable]")
        assert not (tmp_path / "a.txt").exists()

    def test_a_workspace_that_is_not_a_folder_gives_its_own_notice_without_the_path(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        not_a_folder = tmp_path / "archivo-suelto.txt"
        not_a_folder.write_text("x", encoding="utf-8", newline="")

        composition = build(opened, make_config(tmp_path, workspace=not_a_folder))

        assert composition.notices == (AREA_NOT_A_FOLDER_NOTICE,)
        assert "archivo-suelto" not in AREA_NOT_A_FOLDER_NOTICE

    def test_a_workspace_that_does_not_exist_is_treated_as_not_a_folder(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path / "no-existe"))

        assert composition.notices == (AREA_NOT_A_FOLDER_NOTICE,)

    def test_the_notices_are_single_lines_in_spanish_without_a_trailing_break(self) -> None:
        for notice in (NO_AREA_NOTICE, AREA_NOT_A_FOLDER_NOTICE):
            assert notice.startswith("Aviso: ")
            assert "\n" not in notice


class TestTheOrderAndFailures:
    def test_the_provider_is_built_before_the_database_is_opened(self, tmp_path: Path) -> None:
        config = make_config(tmp_path, workspace=tmp_path)

        def failing_factory(_config: HarnessConfig) -> Provider:
            raise RuntimeError("fallo de prueba")

        with pytest.raises(RuntimeError):
            compose(config, provider_factory=failing_factory)

        assert not config.paths.sessions_db.exists()
        assert not config.paths.sessions_db.parent.exists()

    def test_a_failure_after_the_store_is_open_closes_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stores: list[SqliteSessionStore] = []

        class RecordingStore(SqliteSessionStore):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                stores.append(self)

        def failing_recorder(*_args: Any) -> None:
            raise RuntimeError("fallo de prueba")

        monkeypatch.setattr(bootstrap, "SqliteSessionStore", RecordingStore)
        monkeypatch.setattr(bootstrap, "attach_event_recorder", failing_recorder)

        with pytest.raises(RuntimeError):
            compose(
                make_config(tmp_path, workspace=tmp_path),
                provider_factory=lambda _config: scripted("x"),
            )

        assert len(stores) == 1
        with pytest.raises(SessionStoreError):
            stores[0].get_session("lo-que-sea")

    def test_close_closes_the_store_and_can_be_repeated(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        composition.close()
        composition.close()

        with pytest.raises(SessionStoreError):
            composition.store.get_session(composition.session_id)

    def test_the_composition_is_immutable(self, tmp_path: Path, opened: list[Composition]) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path))

        with pytest.raises(dataclasses.FrozenInstanceError):
            composition.session_id = "otra"  # type: ignore[misc]


class TestTheDefaultProvider:
    def test_without_a_factory_it_builds_litellm_with_the_model_cap_and_key(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, opened: list[Composition]
    ) -> None:
        built: list[tuple[str, int, object]] = []
        key = Secret(SENTINEL)

        class RecordingProvider(Provider):
            def __init__(
                self, model: str, *, max_output_tokens: int, api_key: object = None
            ) -> None:
                built.append((model, max_output_tokens, api_key))

            async def complete(self, messages: Any, tools: Any = None) -> ProviderResponse:
                return ProviderResponse(content="x")

        monkeypatch.setattr(bootstrap, "LiteLLMProvider", RecordingProvider)
        config = make_config(tmp_path, workspace=tmp_path, api_key=key)

        composition = compose(config)
        opened.append(composition)

        assert built == [(config.model, 777, key)]


class TestTheSimulatedProviderIsNotACommandProvider:
    """``fake/...`` passes the configuration but only exists as a test double (convergence T016)."""

    def test_the_default_provider_refuses_a_fake_model_before_opening_the_database(
        self, tmp_path: Path
    ) -> None:
        config = make_config(tmp_path, workspace=tmp_path, model="fake/test")

        with pytest.raises(StartupError) as raised:
            compose(config)

        assert str(raised.value) == TEST_ONLY_PROVIDER_MESSAGE
        assert not config.paths.sessions_db.parent.exists()

    def test_the_message_is_one_line_in_spanish_and_does_not_repeat_the_model(self) -> None:
        assert "\n" not in TEST_ONLY_PROVIDER_MESSAGE
        assert "fake" in TEST_ONLY_PROVIDER_MESSAGE
        assert "config.toml" in TEST_ONLY_PROVIDER_MESSAGE

    def test_an_injected_provider_may_use_a_fake_model(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, workspace=tmp_path, model="fake/test"))

        assert composition.session_id
