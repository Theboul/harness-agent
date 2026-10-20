"""Tests for ``Secret``, ``ConfigProblem`` and the domain errors of the configuration.

HU-00-04 / T003 (``Secret``, ``ConfigProblem`` and the hierarchy of errors) and T004 (the texts of
the errors, as defined in ``contracts/config_loading_contract.md``, section 5). The texts are for
the person who runs the system: complete sentences in Spanish, never a received value.
"""

from __future__ import annotations

import copy
import dataclasses
import pickle
from pathlib import Path

import pytest

from harness_agent.config import (
    ConfigError,
    ConfigFileNotFoundError,
    ConfigFileUnreadableError,
    ConfigProblem,
    ConfigSyntaxError,
    InvalidConfigError,
    MissingKeyError,
    Secret,
    SecretInConfigFileError,
)
from tests.unit.config_support import SECRET_FIELD, SENTINEL

HIDDEN = "<secreto oculto>"
PATH = Path("config.toml")


@dataclasses.dataclass(frozen=True)
class Holder:
    model: str
    key: Secret | None


class TestSecret:
    def test_repr_str_and_format_are_hidden(self) -> None:
        secret = Secret(SENTINEL)

        assert repr(secret) == HIDDEN
        assert str(secret) == HIDDEN
        assert format(secret) == HIDDEN
        assert f"{secret}" == HIDDEN
        assert f"{secret!r}" == HIDDEN

    def test_the_text_has_neither_the_value_nor_its_length(self) -> None:
        text = repr(Secret(SENTINEL)) + str(Secret(SENTINEL))

        assert SENTINEL not in text
        assert str(len(SENTINEL)) not in text
        assert "VALOR" not in text

    def test_reveal_returns_the_value(self) -> None:
        assert Secret(SENTINEL).reveal() == SENTINEL

    def test_two_secrets_with_the_same_value_are_not_equal(self) -> None:
        first, second = Secret(SENTINEL), Secret(SENTINEL)

        assert first != second
        assert first == first  # noqa: PLR0124

    def test_pickle_is_blocked(self) -> None:
        with pytest.raises(TypeError):
            pickle.dumps(Secret(SENTINEL))

    def test_copy_and_deepcopy_return_the_same_object(self) -> None:
        secret = Secret(SENTINEL)

        assert copy.copy(secret) is secret
        assert copy.deepcopy(secret) is secret

    def test_a_dataclass_holding_a_secret_can_be_copied_and_converted_without_exposing_it(
        self,
    ) -> None:
        holder = Holder("fake/test", Secret(SENTINEL))

        converted = dataclasses.asdict(holder)
        duplicated = copy.deepcopy(holder)

        assert SENTINEL not in repr(converted)
        assert SENTINEL not in repr(duplicated)
        assert SENTINEL not in repr(holder)
        assert converted["key"] is holder.key
        assert duplicated.key is holder.key

    def test_it_has_no_dict(self) -> None:
        assert not hasattr(Secret(SENTINEL), "__dict__")


class TestJerarquia:
    def test_config_problem_is_frozen_and_equal_by_value(self) -> None:
        problem = ConfigProblem("limits.max_turns", "debe ser un entero mayor que 0.")

        assert problem == ConfigProblem("limits.max_turns", "debe ser un entero mayor que 0.")
        with pytest.raises(dataclasses.FrozenInstanceError):
            problem.field = "otro"  # type: ignore[misc]

    @pytest.mark.parametrize(
        "error",
        [
            ConfigFileNotFoundError(PATH, "default"),
            ConfigFileUnreadableError(PATH, "la ruta es un directorio"),
            ConfigSyntaxError(PATH, 3),
            SecretInConfigFileError(PATH, ("a",)),
            InvalidConfigError(PATH, (ConfigProblem("model", "falta el campo obligatorio."),)),
            MissingKeyError("ANTHROPIC_API_KEY", "anthropic"),
        ],
    )
    def test_every_error_is_a_config_error_and_an_exception(self, error: ConfigError) -> None:
        assert isinstance(error, ConfigError)
        assert isinstance(error, Exception)
        assert not isinstance(error, ValueError)

    def test_the_attributes_of_each_error(self) -> None:
        not_found = ConfigFileNotFoundError(PATH, "HARNESS_CONFIG")
        unreadable = ConfigFileUnreadableError(PATH, "no hay permiso de lectura")
        syntax = ConfigSyntaxError(PATH, None)
        error = SecretInConfigFileError(PATH, ("a", "limits.token"))
        problems = (ConfigProblem("model", "falta el campo obligatorio."),)
        invalid = InvalidConfigError(PATH, problems)
        missing = MissingKeyError("OPENAI_API_KEY", "openai")

        assert (not_found.path, not_found.origin) == (PATH, "HARNESS_CONFIG")
        assert (unreadable.path, unreadable.reason) == (PATH, "no hay permiso de lectura")
        assert (syntax.path, syntax.line) == (PATH, None)
        assert (error.path, error.fields) == (PATH, ("a", "limits.token"))
        assert (invalid.path, invalid.problems) == (PATH, problems)
        assert (missing.variable, missing.provider) == ("OPENAI_API_KEY", "openai")


class TestTextosDeError:
    def test_file_not_found_when_the_location_is_the_default(self) -> None:
        error = ConfigFileNotFoundError(PATH, "default")

        assert str(error) == (
            f"No se encontró el archivo de configuración '{PATH}'. Cree 'config.toml' a partir "
            "de 'config.example.toml' o indique otra ubicación con la variable de entorno "
            "HARNESS_CONFIG o con el parámetro de la función de carga."
        )

    def test_file_not_found_when_the_location_comes_from_the_environment(self) -> None:
        error = ConfigFileNotFoundError(PATH, "HARNESS_CONFIG")

        assert str(error) == (
            f"No se encontró el archivo de configuración '{PATH}', indicado por la variable de "
            "entorno HARNESS_CONFIG. Compruebe la ruta."
        )

    def test_file_not_found_when_the_location_is_a_parameter(self) -> None:
        error = ConfigFileNotFoundError(PATH, "parameter")

        assert str(error) == (
            f"No se encontró el archivo de configuración '{PATH}', indicado como parámetro de "
            "la función de carga. Compruebe la ruta."
        )

    @pytest.mark.parametrize(
        "reason",
        [
            "la ruta es un directorio",
            "no hay permiso de lectura",
            "no está codificado en UTF-8",
            "el sistema devolvió un error de lectura",
        ],
    )
    def test_file_unreadable_with_each_reason(self, reason: str) -> None:
        error = ConfigFileUnreadableError(PATH, reason)

        assert str(error) == f"No se pudo leer el archivo de configuración '{PATH}': {reason}."

    def test_syntax_error_with_the_line(self) -> None:
        assert str(ConfigSyntaxError(PATH, 7)) == (
            f"El archivo de configuración '{PATH}' no es TOML válido (línea 7). Corrija la "
            "sintaxis y vuelva a arrancar."
        )

    def test_syntax_error_without_the_line(self) -> None:
        assert str(ConfigSyntaxError(PATH, None)) == (
            f"El archivo de configuración '{PATH}' no es TOML válido. Corrija la sintaxis y "
            "vuelva a arrancar."
        )

    def test_one_secret_field(self) -> None:
        error = SecretInConfigFileError(PATH, (SECRET_FIELD,))

        assert str(error) == (
            f"El campo '{SECRET_FIELD}' del archivo de configuración '{PATH}' parece una clave "
            "o un secreto, o es un nombre mal escrito de otro campo. Las claves se definen solo "
            "en variables de entorno (vea .env.example); si es un campo legítimo, revise su "
            "nombre; si es una clave, elimine el campo del archivo."
        )

    def test_several_secret_fields(self) -> None:
        error = SecretInConfigFileError(PATH, (SECRET_FIELD, "limits.token"))

        assert str(error) == (
            f"Los campos '{SECRET_FIELD}', 'limits.token' del archivo de configuración '{PATH}' "
            "parecen claves o secretos, o son nombres mal escritos de otros campos. Las claves "
            "se definen solo en variables de entorno (vea .env.example); si son campos "
            "legítimos, revise sus nombres; si son claves, elimine esos campos del archivo."
        )

    def test_invalid_config_lists_every_problem(self) -> None:
        error = InvalidConfigError(
            PATH,
            (
                ConfigProblem("model", "falta el campo obligatorio."),
                ConfigProblem("limits.max_turns", "debe ser un entero mayor que 0."),
                ConfigProblem("paths.sessions_db", "debe ser un texto no vacío."),
                ConfigProblem("limites", "campo desconocido en el esquema."),
            ),
        )

        assert str(error) == (
            f"Configuración inválida en '{PATH}':\n"
            "- model: falta el campo obligatorio.\n"
            "- limits.max_turns: debe ser un entero mayor que 0.\n"
            "- paths.sessions_db: debe ser un texto no vacío.\n"
            "- limites: campo desconocido en el esquema."
        )

    def test_missing_key(self) -> None:
        error = MissingKeyError("ANTHROPIC_API_KEY", "anthropic")

        assert str(error) == (
            "Falta la variable de entorno ANTHROPIC_API_KEY (o está vacía), que el proveedor "
            "'anthropic' necesita para autenticarse. Defínala en el entorno (vea .env.example); "
            "su valor no se muestra."
        )

    def test_a_field_name_longer_than_64_characters_is_clipped(self) -> None:
        name = "x" * 70
        clipped = "x" * 63 + "…"

        invalid = InvalidConfigError(
            PATH, (ConfigProblem(name, "campo desconocido en el esquema."),)
        )
        error = SecretInConfigFileError(PATH, (name,))

        assert f"- {clipped}: campo desconocido" in str(invalid)
        assert name not in str(invalid)
        assert f"'{clipped}'" in str(error)
        assert name not in str(error)
        assert invalid.problems[0].field == name  # the data keeps the full name

    def test_every_text_ends_with_a_period_and_has_no_trace_or_value(self) -> None:
        errors: list[ConfigError] = [
            ConfigFileNotFoundError(PATH, "default"),
            ConfigFileUnreadableError(PATH, "no está codificado en UTF-8"),
            ConfigSyntaxError(PATH, 2),
            SecretInConfigFileError(PATH, (SECRET_FIELD,)),
            InvalidConfigError(PATH, (ConfigProblem("model", "falta el campo obligatorio."),)),
            MissingKeyError("ANTHROPIC_API_KEY", "anthropic"),
        ]

        for error in errors:
            text = str(error)
            assert text.endswith("."), text
            assert "Traceback" not in text
            assert SENTINEL not in text
