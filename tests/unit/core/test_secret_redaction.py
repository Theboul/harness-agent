"""Tests of the general redaction of secrets (HU-10-02).

Realistic key shapes are built by concatenation so that the repository secret detector
(``tests/architecture/test_no_secrets_in_repo.py``) never sees a whole literal.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from harness_agent.core import HIDDEN_SECRET, SecretRedactor, redact_secrets

ALNUM = "Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4z"
SAMPLES = {
    "openai": "sk-" + "proj-" + ALNUM,
    "groq": "gsk_" + ALNUM,
    "gemini": "AIza" + "Sy" + ALNUM,
    "github": "ghp_" + ALNUM + "0123",
    "github_pat": "github_pat_" + ALNUM + "_01234",
    "slack": "xoxb-" + "1234567890-" + ALNUM,
    "aws": "AKIA" + "ABCDEFGH23456789",
    "jwt": "eyJ" + "hbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "dozjgNryP4J3jVmNHl0w",
}


@pytest.mark.parametrize("label", sorted(SAMPLES))
def test_a_known_key_pattern_is_replaced_by_the_marker(label: str) -> None:
    key = SAMPLES[label]
    result = redact_secrets(f"error calling the API with {key} (status 401)")
    assert key not in result
    assert result == f"error calling the API with {HIDDEN_SECRET} (status 401)"


def test_bearer_and_authorization_headers_lose_their_token() -> None:
    token = "t0k3n" + ALNUM
    result = redact_secrets(f"Authorization: Bearer {token}\nBearer {token}")
    assert token not in result
    assert result.count(HIDDEN_SECRET) == 2
    assert "Bearer" in result


def test_basic_authorization_header_is_hidden() -> None:
    blob = "dXNlcjpwYXNzd29yZDEyMzQ1"
    assert blob not in redact_secrets(f"Authorization: Basic {blob}")


def test_an_already_hidden_authorization_is_left_alone() -> None:
    text = f"Authorization: {HIDDEN_SECRET} and Authorization: Bearer {HIDDEN_SECRET}"
    assert redact_secrets(text) == text


def test_the_word_bearer_in_prose_is_kept() -> None:
    text = "Bearer authentication is described in RFC 6750."
    assert redact_secrets(text) == text


@pytest.mark.parametrize(
    "line",
    [
        "OPENAI_API_KEY=%s",
        "export SECRET_VALUE=%s",
        '{"api_key": "%s"}',
        "password: %s",
        "db.passwd = '%s'",
        "client_secret=%s&grant=x",
    ],
)
def test_name_value_pairs_with_a_secret_name_hide_the_value(line: str) -> None:
    value = "Zq7Kp2Lm9Xw4Rt8V"
    result = redact_secrets(line % value)
    assert value not in result
    assert HIDDEN_SECRET in result


def test_the_name_of_the_variable_stays_visible() -> None:
    name = "GROQ_API_" + "KEY"
    result = redact_secrets(f"{name}=Zq7Kp2Lm9Xw4Rt8V")
    assert result == f"{name}={HIDDEN_SECRET}"


def test_known_values_are_hidden_literally_whatever_their_shape() -> None:
    known = "plain-value-without-pattern"
    result = redact_secrets(f"the key was {known}, again {known}", known=[known])
    assert known not in result
    assert result.count(HIDDEN_SECRET) == 2


def test_short_known_values_are_ignored_so_normal_text_survives() -> None:
    assert redact_secrets("a cat sat on the mat", known=["cat", ""]) == "a cat sat on the mat"


def test_longer_known_values_win_over_their_prefixes() -> None:
    result = redact_secrets(
        "value-12345678-extra", known=["value-12345678", "value-12345678-extra"]
    )
    assert result == HIDDEN_SECRET


def test_url_credentials_are_still_hidden() -> None:
    result = redact_secrets("clone https://user:hunter2@example.com/repo.git")
    assert "hunter2" not in result


def test_redaction_is_idempotent() -> None:
    text = f"k={SAMPLES['openai']} Bearer {ALNUM}1 https://u:p@h/x PASSWORD=abcdef12"
    once = redact_secrets(text, known=["abcdef12xyz"])
    assert redact_secrets(once, known=["abcdef12xyz"]) == once


@pytest.mark.parametrize(
    "text",
    [
        "Plain prose about a monkey and a keyboard.",
        r"C:\Users\alex\Documents\Topicos\harness\src\harness_agent\core\redaction.py",
        "/home/alex/projects/task-runner/src/risk-assessment-notes.md",
        "src/harness_agent/core/secret_redaction.py:42",
        "max_tokens = 4096 and total_tokens: 1000000",
        "def get_key(name: str) -> str: return name",
        "timeout=30 retries=5 path=/usr/local/bin",
        "https://example.com/docs?page=2#secret-section",
        "commit 57efab3d5e0a1c9b8f7e6d5c4b3a291807f6e5d4",
        "",
    ],
)
def test_normal_text_and_paths_are_not_changed(text: str) -> None:
    assert redact_secrets(text) == text


def test_non_text_input_is_rejected() -> None:
    with pytest.raises(TypeError):
        redact_secrets(b"bytes")  # type: ignore[arg-type]


def test_a_very_long_text_is_processed_in_linear_time() -> None:
    hostile = [
        "a" * 3_000_000,
        "key=" * 500_000,
        "key." * 500_000,
        ("sk-" + "a" * 10) * 200_000,
        "=" * 1_000_000,
        "Bearer " * 300_000,
        "eyJ" + "a" * 2_000_000,
        " : " * 500_000,
        "eyJ-" * 50_000,
    ]
    for text in hostile:
        started = time.perf_counter()
        redact_secrets(text, known=["x" * 12])
        assert time.perf_counter() - started < 10.0


class TestSecretRedactor:
    def test_it_hides_known_values_and_patterns(self) -> None:
        redactor = SecretRedactor(["my-provider-key-value"])
        text = f"my-provider-key-value and {SAMPLES['groq']}"
        assert redactor(text) == f"{HIDDEN_SECRET} and {HIDDEN_SECRET}"

    def test_value_cleans_every_text_at_any_depth_and_keeps_the_rest(self) -> None:
        redactor = SecretRedactor()
        key = SAMPLES["openai"]
        source: dict[str, Any] = {
            "a": [key, 3, None, (key, True)],
            "b": {"c": f"x {key}"},
            key: 1.5,
        }
        cleaned = redactor.value(source)
        assert cleaned == {
            "a": [HIDDEN_SECRET, 3, None, (HIDDEN_SECRET, True)],
            "b": {"c": f"x {HIDDEN_SECRET}"},
            key: 1.5,
        }
        assert source["a"][0] == key  # the original is never changed

    def test_from_environment_takes_values_of_variables_named_like_keys(self) -> None:
        environ = {
            "PATH": "/usr/bin:/usr/local/bin",
            "GROQ_API_KEY": "plain-groq-" + "value-9999",
            "MY_TOKEN": "tok-value-" + "abcdef",
            "DB_PASSWORD": "pw",  # too short to be matched literally
            "HOME": "/home/alex",
            "MAX_TOKENS": "100000000",
        }
        redactor = SecretRedactor.from_environment(environ, extra=["extra-secret-value"])
        text = (
            "a plain-groq-value-9999 b tok-value-abcdef c extra-secret-value "
            "d /usr/bin:/usr/local/bin"
        )
        assert redactor(text) == (
            f"a {HIDDEN_SECRET} b {HIDDEN_SECRET} c {HIDDEN_SECRET} d /usr/bin:/usr/local/bin"
        )

    def test_the_known_values_do_not_appear_in_the_representation(self) -> None:
        redactor = SecretRedactor(["never-shown-in-repr"])
        assert "never-shown-in-repr" not in repr(redactor)
        assert "never-shown-in-repr" not in str(redactor)
