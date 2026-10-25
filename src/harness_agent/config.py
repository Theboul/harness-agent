"""Loading of the configuration of HARNESS from a TOML file and from the environment (HU-00-04).

This module lives outside the core on purpose: it is the only place that reads a file or the
environment. The core receives the already loaded, typed and immutable values by injection.

The non-secret values (model, limits and paths) come only from the configuration file. The API
key of the provider comes only from an environment variable and travels inside a ``Secret``,
whose representation is hidden. Every failure is a ``ConfigError`` whose text is a complete
sentence in Spanish that names the field or the variable and never shows a received value.

Standard library only. The contract is in
``specs/010-file-env-configuration/contracts/config_loading_contract.md``.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, NoReturn

from harness_agent.core.permissions import PermissionRules

MAX_FIELD_DISPLAY = 64
ENV_CONFIG_LOCATION = "HARNESS_CONFIG"
DEFAULT_CONFIG_FILE = "config.toml"

# Provider -> environment variable that holds its API key (``None``: the provider needs none).
# This is the only place that knows provider names. HU-07-02 added the providers with a free tier
# or a local server (``gemini``, ``groq``, ``openrouter``, ``ollama``); HU-07-03 may extend it. A
# provider that is not here is rejected.
PROVIDER_KEY_VARIABLES: Mapping[str, str | None] = MappingProxyType(
    {
        "anthropic": "ANTHROPIC_API_KEY",
        "fake": None,
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "ollama": None,
    }
)

_DEFAULT_SESSIONS_DB = Path(".harness") / "sessions.db"
_LIMIT_FIELDS = ("max_turns", "max_seconds", "max_tokens", "max_output_tokens")
_PATH_FIELDS = ("workspace_root", "sessions_db")
_PERMISSION_FIELDS = ("deny", "ask")
_MISSING_FIELD = "falta el campo obligatorio."
_MODEL_FORM = "debe ser un texto con la forma <proveedor>/<modelo>."
_NOT_AN_INTEGER = "debe ser un entero mayor que 0."
_NOT_A_TEXT = "debe ser un texto no vacío."
_NOT_A_TABLE = "debe ser una tabla."
_NOT_A_NAME_LIST = "debe ser una lista de textos no vacíos."
_KEY_NAME_MARKERS = ("key", "secret", "token", "password", "passwd", "credential")
_UNKNOWN_FIELD = "campo desconocido en el esquema."
_TABLE_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"limits": _LIMIT_FIELDS, "paths": _PATH_FIELDS, "permissions": _PERMISSION_FIELDS}
)

_ELLIPSIS = "…"
_HIDDEN = "<secreto oculto>"


def _clip(text: str, limit: int = MAX_FIELD_DISPLAY) -> str:
    """Return ``text`` as is, or cut so that, ellipsis included, it has ``limit`` characters."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + _ELLIPSIS


class Secret:
    """A secret value (the API key of a provider) whose representation is always hidden.

    ``repr``, ``str`` and ``format`` never show the value, nor part of it, nor its length. The
    value only comes out through ``reveal()``. A secret is copied by identity (the configuration
    is immutable) but it cannot be serialized with ``pickle``. Two secrets are never equal by
    value.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the secret value; only the code that must authenticate should call this."""
        return self._value

    def __repr__(self) -> str:
        return _HIDDEN

    def __str__(self) -> str:
        return _HIDDEN

    def __format__(self, format_spec: str) -> str:
        return _HIDDEN

    def __copy__(self) -> Secret:
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> Secret:
        return self

    def __reduce__(self) -> NoReturn:
        raise TypeError("Un secreto no se puede serializar.")


@dataclass(frozen=True)
class ConfigProblem:
    """One problem found in the configuration file.

    Attributes:
        field: Dotted path of the field (``limits.max_turns``).
        message: Complete sentence in Spanish, ending with a period, without the received value.
    """

    field: str
    message: str


class ConfigError(Exception):
    """Base of every error of the loading of the configuration."""


class ConfigFileNotFoundError(ConfigError):
    """The configuration file does not exist.

    Attributes:
        path: Absolute path that was looked for.
        origin: Where the location came from: ``parameter``, ``HARNESS_CONFIG`` or ``default``.
    """

    def __init__(self, path: Path, origin: str) -> None:
        self.path = path
        self.origin = origin
        super().__init__(path, origin)

    def __str__(self) -> str:
        if self.origin == "HARNESS_CONFIG":
            return (
                f"No se encontró el archivo de configuración '{self.path}', indicado por la "
                "variable de entorno HARNESS_CONFIG. Compruebe la ruta."
            )
        if self.origin == "parameter":
            return (
                f"No se encontró el archivo de configuración '{self.path}', indicado como "
                "parámetro de la función de carga. Compruebe la ruta."
            )
        return (
            f"No se encontró el archivo de configuración '{self.path}'. Cree 'config.toml' a "
            "partir de 'config.example.toml' o indique otra ubicación con la variable de "
            "entorno HARNESS_CONFIG o con el parámetro de la función de carga."
        )


class ConfigFileUnreadableError(ConfigError):
    """The configuration file cannot be read.

    Attributes:
        path: Absolute path of the file.
        reason: One of a fixed set of phrases (it never carries the message of the system).
    """

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(path, reason)

    def __str__(self) -> str:
        return f"No se pudo leer el archivo de configuración '{self.path}': {self.reason}."


class ConfigSyntaxError(ConfigError):
    """The content of the configuration file is not valid TOML.

    Attributes:
        path: Absolute path of the file.
        line: Line of the error, or ``None`` when it cannot be determined.
    """

    def __init__(self, path: Path, line: int | None) -> None:
        self.path = path
        self.line = line
        super().__init__(path, line)

    def __str__(self) -> str:
        where = "" if self.line is None else f" (línea {self.line})"
        return (
            f"El archivo de configuración '{self.path}' no es TOML válido{where}. Corrija la "
            "sintaxis y vuelva a arrancar."
        )


class SecretInConfigFileError(ConfigError):
    """The file has fields unknown to the schema whose name looks like a key or a secret.

    Attributes:
        path: Absolute path of the file.
        fields: Dotted path of each field, in the order of the file.
    """

    def __init__(self, path: Path, fields: Sequence[str]) -> None:
        self.path = path
        self.fields = tuple(fields)
        super().__init__(path, self.fields)

    def __str__(self) -> str:
        names = ", ".join(f"'{_clip(name)}'" for name in self.fields)
        if len(self.fields) == 1:
            return (
                f"El campo {names} del archivo de configuración '{self.path}' parece una clave "
                "o un secreto, o es un nombre mal escrito de otro campo. Las claves se definen "
                "solo en variables de entorno (vea .env.example); si es un campo legítimo, "
                "revise su nombre; si es una clave, elimine el campo del archivo."
            )
        return (
            f"Los campos {names} del archivo de configuración '{self.path}' parecen claves o "
            "secretos, o son nombres mal escritos de otros campos. Las claves se definen solo "
            "en variables de entorno (vea .env.example); si son campos legítimos, revise sus "
            "nombres; si son claves, elimine esos campos del archivo."
        )


class InvalidConfigError(ConfigError):
    """The file does not satisfy the schema; every problem is reported together.

    Attributes:
        path: Absolute path of the file.
        problems: Every problem found, in deterministic order.
    """

    def __init__(self, path: Path, problems: Sequence[ConfigProblem]) -> None:
        self.path = path
        self.problems = tuple(problems)
        super().__init__(path, self.problems)

    def __str__(self) -> str:
        lines = [f"Configuración inválida en '{self.path}':"]
        lines.extend(f"- {_clip(problem.field)}: {problem.message}" for problem in self.problems)
        return "\n".join(lines)


class MissingKeyError(ConfigError):
    """The provider of the model needs an API key and its environment variable is missing.

    Attributes:
        variable: Name of the environment variable (never its value).
        provider: Provider of the configured model.
    """

    def __init__(self, variable: str, provider: str) -> None:
        self.variable = variable
        self.provider = provider
        super().__init__(variable, provider)

    def __str__(self) -> str:
        return (
            f"Falta la variable de entorno {self.variable} (o está vacía), que el proveedor "
            f"'{self.provider}' necesita para autenticarse. Defínala en el entorno (vea "
            ".env.example); su valor no se muestra."
        )


@dataclass(frozen=True, slots=True)
class Limits:
    """Limits per session (reserved for HU-01-06): turns, seconds and tokens.

    ``max_tokens`` is the token budget of the whole run. ``max_output_tokens`` (HU-07-02) is the
    cap of the tokens the model may generate in one call; the default is low enough for providers
    with a small cap, such as free tiers. They are independent: one is never used as the other.
    """

    max_turns: int = 30
    max_seconds: int = 600
    max_tokens: int = 200000
    max_output_tokens: int = 4096


@dataclass(frozen=True, slots=True)
class Paths:
    """Paths (reserved for HU-01-03 and HU-03-01): the authorized workspace and the sessions DB.

    ``workspace_root`` is ``None`` when it is not configured: consumers must treat that as the
    absence of an authorized area (fail closed), never as the current directory.
    """

    workspace_root: Path | None = None
    sessions_db: Path = _DEFAULT_SESSIONS_DB


@dataclass(frozen=True, slots=True)
class HarnessConfig:
    """The complete configuration, typed and immutable, that the rest of the system receives.

    Attributes:
        model: Model in use, with the form ``<provider>/<model>``; it only comes from the file.
        limits: Limits per session.
        paths: Absolute paths.
        source: Absolute path of the file that was read.
        api_key: API key of the provider (only from the environment), or ``None`` if the
            provider of the model needs none.
        key_variable: Name of the environment variable of the key, or ``None``.
        permissions: Tools that are always denied or asked (HU-05-01); empty by default. The
            configuration cannot define a rule to allow.
    """

    model: str
    limits: Limits
    paths: Paths
    source: Path
    api_key: Secret | None = None
    key_variable: str | None = None
    permissions: PermissionRules = PermissionRules()


def _locate(path: str | os.PathLike[str] | None, environ: Mapping[str, str]) -> tuple[Path, str]:
    """Where the file is, and where that location came from (parameter, variable or default)."""
    if path is not None:
        return Path(os.path.abspath(os.fspath(path))), "parameter"
    from_environment = environ.get(ENV_CONFIG_LOCATION)
    if from_environment is not None and from_environment.strip():
        return Path(os.path.abspath(from_environment)), ENV_CONFIG_LOCATION
    return Path(os.path.abspath(DEFAULT_CONFIG_FILE)), "default"


def _read(path: Path, origin: str) -> str:
    """Read the file as UTF-8 (a byte order mark is accepted); fail with a domain error."""
    if not path.exists():
        raise ConfigFileNotFoundError(path, origin) from None
    if path.is_dir():
        raise ConfigFileUnreadableError(path, "la ruta es un directorio") from None
    try:
        raw = path.read_bytes()
    except PermissionError:
        raise ConfigFileUnreadableError(path, "no hay permiso de lectura") from None
    except OSError:
        raise ConfigFileUnreadableError(path, "el sistema devolvió un error de lectura") from None
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ConfigFileUnreadableError(path, "no está codificado en UTF-8") from None


def _parse(path: Path, text: str) -> dict[str, Any]:
    """Parse the TOML; the error never quotes the parser message, only the line number."""
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        found = re.search(r"line (\d+)", str(error))
        line = int(found.group(1)) if found else None
        raise ConfigSyntaxError(path, line) from None


def _check_model(
    data: Mapping[str, Any], missing: list[ConfigProblem], present: list[ConfigProblem]
) -> str:
    """The model: required, text with the form ``<provider>/<model>``, provider of the table."""
    if "model" not in data:
        missing.append(ConfigProblem("model", _MISSING_FIELD))
        return ""
    value = data["model"]
    provider, slash, name = value.partition("/") if isinstance(value, str) else ("", "", "")
    if not (slash and provider.strip() and name.strip()):
        present.append(ConfigProblem("model", _MODEL_FORM))
        return ""
    if provider not in PROVIDER_KEY_VARIABLES:
        admitted = ", ".join(sorted(PROVIDER_KEY_VARIABLES))
        present.append(
            ConfigProblem("model", f"el proveedor no es uno de los admitidos ({admitted}).")
        )
        return ""
    return str(value)


def _check_limits(table: Mapping[str, Any], present: list[ConfigProblem]) -> Limits:
    """The limits: integers (a boolean is not one) greater than zero."""
    values: dict[str, int] = {}
    for field in _LIMIT_FIELDS:
        if field not in table:
            continue
        value = table[field]
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            values[field] = value
        else:
            present.append(ConfigProblem(f"limits.{field}", _NOT_AN_INTEGER))
    return Limits(**values)


def _check_paths(table: Mapping[str, Any], base: Path, present: list[ConfigProblem]) -> Paths:
    """The paths: non-empty texts, made absolute against the folder of the file (lexically)."""

    def resolve(value: str | Path) -> Path:
        return Path(os.path.normpath(os.path.join(base, value)))

    found: dict[str, Path] = {}
    for field in _PATH_FIELDS:
        if field not in table:
            continue
        value = table[field]
        if isinstance(value, str) and value.strip():
            found[field] = resolve(value)
        else:
            present.append(ConfigProblem(f"paths.{field}", _NOT_A_TEXT))
    return Paths(
        workspace_root=found.get("workspace_root"),
        sessions_db=found.get("sessions_db", resolve(_DEFAULT_SESSIONS_DB)),
    )


def _check_permissions(table: Mapping[str, Any], present: list[ConfigProblem]) -> PermissionRules:
    """The lists of denied and asked tools: lists of non-empty texts (duplicates are dropped)."""
    values: dict[str, tuple[str, ...]] = {}
    for field in _PERMISSION_FIELDS:
        if field not in table:
            continue
        value = table[field]
        if isinstance(value, list) and all(isinstance(n, str) and n.strip() for n in value):
            values[field] = tuple(dict.fromkeys(value))
        else:
            present.append(ConfigProblem(f"permissions.{field}", _NOT_A_NAME_LIST))
    return PermissionRules(**values)


def _table(data: Mapping[str, Any], name: str, present: list[ConfigProblem]) -> Mapping[str, Any]:
    """The table ``name`` (empty if absent); a value that is not a table is a problem."""
    value = data.get(name, {})
    if isinstance(value, dict):
        return value
    present.append(ConfigProblem(name, _NOT_A_TABLE))
    return {}


def _walk_names(value: object, prefix: str, found: list[str]) -> None:
    """Add the names of every table inside ``value``: all of them are unknown to the schema."""
    if isinstance(value, dict):
        for key, inner in value.items():
            name = f"{prefix}.{key}"
            found.append(name)
            _walk_names(inner, name, found)
    elif isinstance(value, list):
        for item in value:
            _walk_names(item, prefix, found)


def _looks_like_a_key(name: str) -> bool:
    """Whether the last part of a field name suggests a key or a secret.

    Case, ``_`` and ``-`` are ignored, so ``ApiKey`` and ``API-KEY`` match like ``api_key``.
    """
    simple = name.rsplit(".", 1)[-1].lower().replace("_", "").replace("-", "")
    return any(marker in simple for marker in _KEY_NAME_MARKERS)


def _unknown_names(data: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """The field names that the schema does not know, in the order of the file.

    Returns ``(reported, every_name)``: the first list names an unknown table once, without
    descending into it; the second one also includes the names found inside unknown tables
    (and inside a known field whose value is not of the expected type).
    """
    reported: list[str] = []
    every_name: list[str] = []
    for key, value in data.items():
        if key == "model":
            _walk_names(value, key, every_name)
        elif key in _TABLE_FIELDS:
            known = _TABLE_FIELDS[key]
            if not isinstance(value, dict):
                _walk_names(value, key, every_name)
                continue
            for field, inner in value.items():
                name = f"{key}.{field}"
                if field not in known:
                    reported.append(name)
                    every_name.append(name)
                _walk_names(inner, name, every_name)
        else:
            reported.append(key)
            every_name.append(key)
            _walk_names(value, key, every_name)
    return reported, every_name


def process_environment() -> dict[str, str]:
    """A copy of the environment of the running process.

    ``config`` is the one module that reads the environment, so the composition root asks it for
    the environment it hands to the shell instead of reading ``os.environ`` itself (HU-01-04).
    """
    return dict(os.environ)


def load_config(
    path: str | os.PathLike[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> HarnessConfig:
    """Load the configuration: locate, read, parse and validate the file.

    The location is, in this order: the ``path`` parameter, the ``HARNESS_CONFIG`` variable
    (ignored if it is empty) and ``config.toml`` in the current working directory.
    """
    environment = os.environ if environ is None else environ
    file_path, origin = _locate(path, environment)
    data = _parse(file_path, _read(file_path, origin))
    missing: list[ConfigProblem] = []
    present: list[ConfigProblem] = []
    reported, every_name = _unknown_names(data)
    key_fields = [name for name in every_name if _looks_like_a_key(name)]
    if key_fields:
        raise SecretInConfigFileError(file_path, key_fields)
    model = _check_model(data, missing, present)
    limits = _check_limits(_table(data, "limits", present), present)
    paths = _check_paths(_table(data, "paths", present), file_path.parent, present)
    permissions = _check_permissions(_table(data, "permissions", present), present)
    unknown = [ConfigProblem(name, _UNKNOWN_FIELD) for name in reported]
    problems = [*missing, *present, *unknown]
    if problems:
        raise InvalidConfigError(file_path, problems)
    provider = model.split("/", 1)[0]
    variable = PROVIDER_KEY_VARIABLES[provider]
    if variable is None:
        return HarnessConfig(
            model=model, limits=limits, paths=paths, source=file_path, permissions=permissions
        )
    value = environment.get(variable)
    if value is None or not value.strip():
        raise MissingKeyError(variable, provider) from None
    return HarnessConfig(
        model=model,
        limits=limits,
        paths=paths,
        source=file_path,
        api_key=Secret(value),
        key_variable=variable,
        permissions=permissions,
    )
