"""Tests for the location and the reading of the configuration file (HU-00-04 / T006 and T007).

The priority is: the explicit ``path`` parameter, then ``HARNESS_CONFIG``, then ``config.toml`` in
the current working directory. Every test writes its files in ``tmp_path`` and passes ``environ``
as a dictionary, except the two tests of the production path (``environ=None``), which use
``monkeypatch`` and leave the real environment as they found it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigFileNotFoundError,
    ConfigFileUnreadableError,
    ConfigSyntaxError,
    load_config,
)
from tests.unit.config_support import MINIMAL_CONFIG, SENTINEL, write_config


def model_file(tmp_path: Path, folder: str, model: str, name: str = "config.toml") -> Path:
    directory = tmp_path / folder
    directory.mkdir(exist_ok=True)
    return write_config(directory, f'model = "{model}"\n', name=name)


class TestUbicacion:
    def test_the_parameter_beats_the_variable_and_the_variable_beats_the_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        by_parameter = model_file(tmp_path, "parametro", "fake/parametro")
        by_variable = model_file(tmp_path, "variable", "fake/variable")
        model_file(tmp_path, "actual", "fake/actual")
        monkeypatch.chdir(tmp_path / "actual")
        environ = {"HARNESS_CONFIG": str(by_variable)}

        assert load_config(by_parameter, environ=environ).model == "fake/parametro"
        assert load_config(environ=environ).model == "fake/variable"
        assert load_config(environ={}).model == "fake/actual"

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_a_blank_variable_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, blank: str
    ) -> None:
        model_file(tmp_path, "actual", "fake/actual")
        monkeypatch.chdir(tmp_path / "actual")

        assert load_config(environ={"HARNESS_CONFIG": blank}).model == "fake/actual"

    def test_a_relative_explicit_path_is_relative_to_the_working_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        model_file(tmp_path, "sub", "fake/sub", name="otra.toml")
        monkeypatch.chdir(tmp_path)

        config = load_config(Path("sub") / "otra.toml", environ={})

        assert config.model == "fake/sub"
        assert config.source == Path.cwd() / "sub" / "otra.toml"

    def test_the_source_is_the_absolute_path_that_was_read(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG)

        config = load_config(path, environ={})

        assert config.source.is_absolute()
        assert config.source == path

    def test_loading_does_not_modify_the_environment_nor_the_working_directory(
        self, tmp_path: Path
    ) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG)
        environ = {"HARNESS_CONFIG": str(path), "OTRA": "x"}
        copy_of_environ = dict(environ)
        directory = os.getcwd()
        real_environment = dict(os.environ)

        load_config(environ=environ)

        assert environ == copy_of_environ
        assert os.getcwd() == directory
        assert dict(os.environ) == real_environment

    def test_the_same_file_and_environment_give_the_same_result(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG)

        assert load_config(path, environ={}) == load_config(path, environ={})

    def test_the_production_path_reads_harness_config_from_the_real_environment(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        by_variable = model_file(tmp_path, "variable", "fake/variable")
        model_file(tmp_path, "actual", "fake/actual")
        monkeypatch.chdir(tmp_path / "actual")

        monkeypatch.setenv("HARNESS_CONFIG", str(by_variable))
        assert load_config().model == "fake/variable"

        monkeypatch.delenv("HARNESS_CONFIG", raising=False)
        assert load_config().model == "fake/actual"


class TestLectura:
    def test_a_missing_default_file_names_the_default_origin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(ConfigFileNotFoundError) as info:
            load_config(environ={})

        assert info.value.origin == "default"
        assert info.value.path == Path.cwd() / "config.toml"
        assert "Cree 'config.toml' a partir de 'config.example.toml'" in str(info.value)

    def test_a_missing_file_named_by_the_variable_names_that_origin(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-existe.toml"

        with pytest.raises(ConfigFileNotFoundError) as info:
            load_config(environ={"HARNESS_CONFIG": str(missing)})

        assert info.value.origin == "HARNESS_CONFIG"
        assert info.value.path == missing
        assert "indicado por la variable de entorno HARNESS_CONFIG" in str(info.value)

    def test_a_missing_file_named_by_the_parameter_names_that_origin(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-existe.toml"

        with pytest.raises(ConfigFileNotFoundError) as info:
            load_config(missing, environ={"HARNESS_CONFIG": str(tmp_path / "otro.toml")})

        assert info.value.origin == "parameter"
        assert "indicado como parámetro de la función de carga" in str(info.value)

    def test_a_directory_is_unreadable(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigFileUnreadableError) as info:
            load_config(tmp_path, environ={})

        assert info.value.reason == "la ruta es un directorio"

    @pytest.mark.parametrize(
        ("failure", "reason"),
        [
            (PermissionError("denegado"), "no hay permiso de lectura"),
            (OSError("fallo del disco"), "el sistema devolvió un error de lectura"),
        ],
    )
    def test_a_failure_of_the_system_while_reading_is_unreadable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        failure: OSError,
        reason: str,
    ) -> None:
        path = write_config(tmp_path, MINIMAL_CONFIG)

        def fail(self: Path) -> bytes:
            raise failure

        monkeypatch.setattr(Path, "read_bytes", fail)

        with pytest.raises(ConfigFileUnreadableError) as info:
            load_config(path, environ={})

        assert info.value.reason == reason
        assert "denegado" not in str(info.value)
        assert "fallo del disco" not in str(info.value)

    @pytest.mark.parametrize("content", [b"\xff\xfe\x00\x00", b'model = "\xe9"\n'])
    def test_bytes_that_are_not_utf8_are_unreadable(self, tmp_path: Path, content: bytes) -> None:
        path = write_config(tmp_path, content)

        with pytest.raises(ConfigFileUnreadableError) as info:
            load_config(path, environ={})

        assert info.value.reason == "no está codificado en UTF-8"

    def test_broken_toml_gives_the_line_and_never_the_content(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, f'model = "fake/test"\nroto = {SENTINEL}\n')

        with pytest.raises(ConfigSyntaxError) as info:
            load_config(path, environ={})

        assert info.value.line == 2
        assert "(línea 2)" in str(info.value)
        assert SENTINEL not in str(info.value)
        assert SENTINEL not in repr(info.value)
        assert "Invalid" not in str(info.value)

    def test_the_errors_carry_no_chained_cause(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, f"roto = {SENTINEL}\n")

        with pytest.raises(ConfigSyntaxError) as info:
            load_config(path, environ={})

        assert info.value.__cause__ is None
        assert info.value.__suppress_context__

    def test_a_byte_order_mark_is_accepted(self, tmp_path: Path) -> None:
        path = write_config(tmp_path, b"\xef\xbb\xbf" + MINIMAL_CONFIG.encode("utf-8"))

        assert load_config(path, environ={}).model == "fake/test"

    def test_windows_line_breaks_are_read_like_unix_ones(self, tmp_path: Path) -> None:
        text = '# comentario\r\nmodel = "fake/prüeba"\r\n'
        crlf = write_config(tmp_path, text, name="crlf.toml")
        lf = write_config(tmp_path, text.replace("\r\n", "\n"), name="lf.toml")

        first = load_config(crlf, environ={})
        second = load_config(lf, environ={})

        assert first.model == second.model == "fake/prüeba"
        assert first.limits == second.limits
