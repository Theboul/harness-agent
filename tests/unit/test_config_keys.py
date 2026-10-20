"""Tests for the API keys and for the key-like fields of the file (HU-00-04 / T013 and T014).

The keys come only from the environment (RF-7.6, RNF-16); a key-like field in the file is
rejected before anything else; and the test value of the key never shows up in any text of an
error or of the configuration. Every test passes ``environ`` as a dictionary, except the
production-path test (``environ=None``), which uses ``monkeypatch`` and leaves the real
environment as it found it. Files with a key-like field are built at run time (``toml_with_field``).
"""

from __future__ import annotations

import copy
import dataclasses
import pickle
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigError,
    InvalidConfigError,
    MissingKeyError,
    Secret,
    SecretInConfigFileError,
    load_config,
)
from tests.unit.config_support import (
    MINIMAL_CONFIG,
    SECRET_FIELD,
    SENTINEL,
    toml_with_field,
    write_config,
)

HIDDEN = "<secreto oculto>"
ANTHROPIC = 'model = "anthropic/x"\n'


class SpyEnvironment(Mapping[str, str]):
    """A read-only environment that records every name that is asked for."""

    def __init__(self, values: Mapping[str, str]) -> None:
        self._values = dict(values)
        self.asked: list[str] = []

    def __getitem__(self, key: str) -> str:
        self.asked.append(key)
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)


class TestClavesDelEntorno:
    @pytest.mark.parametrize(
        ("model", "variable"),
        [("anthropic/x", "ANTHROPIC_API_KEY"), ("openai/x", "OPENAI_API_KEY")],
    )
    def test_the_key_of_the_provider_comes_from_its_variable(
        self, tmp_path: Path, model: str, variable: str
    ) -> None:
        path = write_config(tmp_path, f'model = "{model}"\n')

        config = load_config(path, environ={variable: SENTINEL})

        assert isinstance(config.api_key, Secret)
        assert config.api_key.reveal() == SENTINEL
        assert config.key_variable == variable

    def test_a_provider_without_key_asks_for_no_variable(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG)
        spy = SpyEnvironment({"ANTHROPIC_API_KEY": SENTINEL})

        config = load_config(path, environ=spy)

        assert config.api_key is None
        assert config.key_variable is None
        assert not [name for name in spy.asked if "KEY" in name]

    @pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
    def test_a_missing_empty_or_blank_variable_is_a_missing_key(
        self, tmp_path: Path, value: str | None
    ) -> None:
        path = write_config(tmp_path, ANTHROPIC)
        environ = {} if value is None else {"ANTHROPIC_API_KEY": value}

        with pytest.raises(MissingKeyError) as info:
            load_config(path, environ=environ)

        assert info.value.variable == "ANTHROPIC_API_KEY"
        assert info.value.provider == "anthropic"
        assert "ANTHROPIC_API_KEY" in str(info.value)
        assert "anthropic" in str(info.value)

    def test_the_value_is_delivered_as_it_is_without_trimming(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)
        value = f"  {SENTINEL}  "

        config = load_config(path, environ={"ANTHROPIC_API_KEY": value})

        assert config.api_key is not None
        assert config.api_key.reveal() == value

    def test_the_key_of_another_provider_is_not_used(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)

        with pytest.raises(MissingKeyError) as info:
            load_config(path, environ={"OPENAI_API_KEY": SENTINEL})

        assert info.value.variable == "ANTHROPIC_API_KEY"

    def test_a_missing_key_is_a_config_error_in_spanish_without_traces(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, ANTHROPIC)

        with pytest.raises(ConfigError) as info:
            load_config(path, environ={})

        assert isinstance(info.value, MissingKeyError)
        assert info.value.__cause__ is None
        assert "Traceback" not in str(info.value)

    def test_the_key_is_checked_after_the_schema(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "anthropic/x"\n[limits]\nmax_turns = 0\n')

        with pytest.raises(InvalidConfigError):
            load_config(path, environ={})

    def test_the_production_path_reads_the_key_from_the_real_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = write_config(tmp_path, ANTHROPIC)
        monkeypatch.setenv("HARNESS_CONFIG", str(path))

        monkeypatch.setenv("ANTHROPIC_API_KEY", SENTINEL)
        config = load_config()
        assert config.api_key is not None
        assert config.api_key.reveal() == SENTINEL

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(MissingKeyError):
            load_config()


class TestSinFiltraciones:
    def test_the_value_of_the_key_is_in_no_text_of_the_configuration(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)

        config = load_config(path, environ={"ANTHROPIC_API_KEY": SENTINEL})

        assert SENTINEL not in str(config)
        assert SENTINEL not in repr(config)
        assert SENTINEL not in repr(config.api_key)
        assert SENTINEL not in str(config.api_key)
        assert SENTINEL not in f"{config.api_key}"
        assert HIDDEN in repr(config)

    def test_asdict_and_deepcopy_work_and_show_the_hidden_text(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)
        config = load_config(path, environ={"ANTHROPIC_API_KEY": SENTINEL})

        as_dict = dataclasses.asdict(config)
        copied = copy.deepcopy(config)

        assert SENTINEL not in repr(as_dict)
        assert HIDDEN in repr(as_dict["api_key"])
        assert SENTINEL not in repr(copied)
        assert copied == config

    def test_pickling_the_configuration_is_refused(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)
        config = load_config(path, environ={"ANTHROPIC_API_KEY": SENTINEL})

        with pytest.raises(TypeError):
            pickle.dumps(config)

    def test_no_error_carries_the_value_of_the_key(self, tmp_path: Path) -> None:
        environ = {"ANTHROPIC_API_KEY": SENTINEL}
        broken = write_config(tmp_path, f"roto = {SENTINEL}\n", name="roto.toml")
        invalid = write_config(tmp_path, 'model = "x"\n', name="invalido.toml")
        with_field = write_config(
            tmp_path, ANTHROPIC + toml_with_field(SECRET_FIELD), name="c.toml"
        )

        for path in (broken, invalid, with_field, tmp_path / "no-existe.toml"):
            with pytest.raises(ConfigError) as info:
                load_config(path, environ=environ)
            assert SENTINEL not in str(info.value)
            assert SENTINEL not in repr(info.value)

    def test_a_missing_key_never_shows_a_part_of_another_value(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC)

        with pytest.raises(MissingKeyError) as info:
            load_config(path, environ={"OPENAI_API_KEY": SENTINEL, "ANTHROPIC_API_KEY": ""})

        assert SENTINEL not in str(info.value)
        assert SENTINEL[:6] not in str(info.value)


class TestCamposDeClaveEnArchivo:
    @pytest.mark.parametrize(
        "name",
        [SECRET_FIELD, "Api" + "Key", "API" + "-KEY", "tok" + "en", "pass" + "word", "sec" + "ret"],
    )
    def test_an_unknown_key_like_field_is_rejected(self, tmp_path: Path, name: str) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG + toml_with_field(name))

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == (name,)
        assert SENTINEL not in str(info.value)
        assert SENTINEL not in repr(info.value)

    def test_a_key_like_field_inside_an_unknown_table_is_rejected(self, tmp_path: Path) -> None:
        text = MINIMAL_CONFIG + "[extra]\n" + toml_with_field(SECRET_FIELD)
        path = write_config(tmp_path, text)

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == (f"extra.{SECRET_FIELD}",)

    def test_a_key_like_field_inside_a_list_of_tables_is_rejected(self, tmp_path: Path) -> None:
        text = MINIMAL_CONFIG + "[[extra]]\n" + toml_with_field(SECRET_FIELD)
        path = write_config(tmp_path, text)

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == (f"extra.{SECRET_FIELD}",)

    def test_an_unknown_key_like_field_inside_a_known_table_is_rejected(
        self, tmp_path: Path
    ) -> None:
        text = MINIMAL_CONFIG + "[limits]\n" + toml_with_field("tok" + "en")
        path = write_config(tmp_path, text)

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == ("limits.tok" + "en",)

    def test_several_fields_are_reported_together_in_the_order_of_the_file(
        self, tmp_path: Path
    ) -> None:
        text = (
            toml_with_field("pass" + "word")
            + MINIMAL_CONFIG
            + "[paths]\n"
            + toml_with_field("sec" + "ret")
            + "[extra]\n"
            + toml_with_field(SECRET_FIELD)
        )
        path = write_config(tmp_path, text)

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        assert info.value.fields == (
            "pass" + "word",
            "paths.sec" + "ret",
            f"extra.{SECRET_FIELD}",
        )

    def test_the_error_comes_before_any_schema_error(self, tmp_path: Path) -> None:
        text = toml_with_field(SECRET_FIELD) + "[limits]\nmax_turns = 0\n"
        path = write_config(tmp_path, text)

        with pytest.raises(SecretInConfigFileError):
            load_config(path, environ={})

    def test_an_unknown_field_without_a_key_name_is_still_a_schema_error(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG + "extra = 1\n")

        with pytest.raises(InvalidConfigError):
            load_config(path, environ={})

    def test_the_text_tells_that_it_may_be_a_misspelled_field_and_to_review_the_name(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG + toml_with_field(SECRET_FIELD))

        with pytest.raises(SecretInConfigFileError) as info:
            load_config(path, environ={})

        text = str(info.value)
        assert "o es un nombre mal escrito de otro campo" in text
        assert "si es un campo legítimo, revise su nombre" in text
        assert SECRET_FIELD in text

    def test_a_field_of_the_schema_is_never_rejected_for_its_name(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, 'model = "fake/test"\n[limits]\nmax_tokens = 1000\n')

        config = load_config(path, environ={})

        assert config.limits.max_tokens == 1000

    def test_the_key_is_never_taken_from_the_file(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, ANTHROPIC + toml_with_field(SECRET_FIELD))

        with pytest.raises(SecretInConfigFileError):
            load_config(path, environ={"ANTHROPIC_API_KEY": "otro"})
