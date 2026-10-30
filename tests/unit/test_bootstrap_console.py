"""compose() exposes what the console commands need (HU-06-05 / T009).

``model_view`` feeds ``/model`` and ``manual_compactor_for`` feeds ``/compactar``: a compactor of
the same logic whose threshold is forced low, so it compacts what is above a few messages.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, forced_context_settings
from harness_agent.cli import ModelView
from harness_agent.core import ContextCompactor, ContextSettings, threshold_tokens
from tests.unit.bootstrap_support import build, make_config

MODEL = "openai/modelo-de-prueba"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


class TestModelView:
    def test_it_reflects_the_configuration(self, tmp_path: Path, opened: list[Composition]) -> None:
        config = make_config(tmp_path, model=MODEL)
        config = replace(
            config,
            context=ContextSettings(windows=((MODEL, 100_000),), threshold_percent=70),
            limits=replace(config.limits, max_turns=7, max_seconds=90, max_tokens=5_000),
        )

        composition = build(opened, config)

        assert composition.model_view == ModelView(
            model=MODEL,
            window_tokens=100_000,
            threshold_tokens=70_000,
            max_turns=7,
            max_seconds=90,
            max_tokens=5_000,
            max_output_tokens=777,
        )

    def test_an_unlisted_model_uses_the_default_window(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, model=MODEL))

        view = composition.model_view
        assert view is not None
        assert view.window_tokens == ContextSettings().window_tokens
        assert view.threshold_tokens == threshold_tokens(ContextSettings(), MODEL)

    def test_it_carries_no_secret(self, tmp_path: Path, opened: list[Composition]) -> None:
        composition = build(opened, make_config(tmp_path, model=MODEL))

        assert "api_key" not in repr(composition.model_view)


class TestForcedSettings:
    def test_the_threshold_is_the_lowest_one_allowed_whatever_the_model(self) -> None:
        settings = ContextSettings(windows=((MODEL, 2_000_000),), threshold_percent=95)

        forced = forced_context_settings(settings)

        assert threshold_tokens(forced, MODEL) == 100
        assert threshold_tokens(forced, "otro/modelo") == 100

    def test_the_rest_of_the_settings_is_kept(self) -> None:
        settings = ContextSettings(
            recent_percent=40, min_recent_messages=7, summary_tokens=900, threshold_percent=50
        )

        forced = forced_context_settings(settings)

        assert (forced.recent_percent, forced.min_recent_messages, forced.summary_tokens) == (
            40,
            7,
            900,
        )

    def test_the_original_is_not_modified(self) -> None:
        settings = ContextSettings()

        forced_context_settings(settings)

        assert settings == ContextSettings()


class TestManualCompactor:
    def test_it_is_a_compactor_apart_from_the_automatic_one(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, model=MODEL))
        factory = composition.manual_compactor_for
        assert factory is not None

        manual = factory(composition.session_id)

        assert isinstance(manual, ContextCompactor)
        assert manual is not composition.compactor

    def test_every_call_builds_a_new_compactor_for_the_session_it_is_given(
        self, tmp_path: Path, opened: list[Composition]
    ) -> None:
        composition = build(opened, make_config(tmp_path, model=MODEL))
        factory = composition.manual_compactor_for
        assert factory is not None

        assert factory("s-1") is not factory("s-1")
