"""Tests for ``hide_url_credentials`` (HU-11-02 / T005).

One small pure function hides the credentials of URLs (``scheme://user:secret@host`` and
``scheme://token@host``) with the marker ``<secreto oculto>``. A URL without credentials and a
text without URLs do not change. HU-10-02 must absorb it. The test secrets are built in pieces, so
no literal here has the shape of a key.
"""

from __future__ import annotations

import pytest

from harness_agent.core import HIDDEN_SECRET, hide_url_credentials

USER = "usuario" + "-de-prueba"
SECRET = "secreto" + "-de-prueba"
TOKEN = "token" + "DePrueba" + "123"
HOST = "servidor.example"


def url(credentials: str, scheme: str = "https") -> str:
    return f"{scheme}://{credentials}@{HOST}/repo.git"


class TestTheFourCases:
    def test_user_and_secret(self) -> None:
        hidden = hide_url_credentials(url(f"{USER}:{SECRET}"))

        assert hidden == f"https://{HIDDEN_SECRET}@{HOST}/repo.git"
        assert USER not in hidden and SECRET not in hidden

    def test_only_a_token(self) -> None:
        hidden = hide_url_credentials(url(TOKEN))

        assert hidden == f"https://{HIDDEN_SECRET}@{HOST}/repo.git"
        assert TOKEN not in hidden

    def test_a_url_without_credentials_does_not_change(self) -> None:
        text = f"https://{HOST}/repo.git"

        assert hide_url_credentials(text) == text

    def test_a_text_without_urls_does_not_change(self) -> None:
        text = "On branch main\nnothing to commit, working tree clean\n"

        assert hide_url_credentials(text) == text


class TestMore:
    @pytest.mark.parametrize("scheme", ["http", "https", "ssh", "git+ssh", "ftp"])
    def test_any_scheme(self, scheme: str) -> None:
        hidden = hide_url_credentials(url(f"{USER}:{SECRET}", scheme))

        assert hidden == f"{scheme}://{HIDDEN_SECRET}@{HOST}/repo.git"

    def test_several_urls_in_one_text(self) -> None:
        text = f"origin\t{url(TOKEN)} (fetch)\norigin\t{url(f'{USER}:{SECRET}')} (push)\n"

        hidden = hide_url_credentials(text)

        assert TOKEN not in hidden and SECRET not in hidden and USER not in hidden
        assert hidden.count(HIDDEN_SECRET) == 2
        assert "(fetch)" in hidden and "(push)" in hidden

    @pytest.mark.parametrize(
        "text",
        [
            f"{USER}@{HOST}",
            f"git@{HOST}:repo.git",
            "correo: alguien@example.com",
            f"https://{HOST}/a@b",
            "",
        ],
    )
    def test_texts_without_credentials_in_a_url_do_not_change(self, text: str) -> None:
        assert hide_url_credentials(text) == text

    def test_it_is_idempotent(self) -> None:
        once = hide_url_credentials(url(f"{USER}:{SECRET}"))

        assert hide_url_credentials(once) == once

    def test_the_marker_is_the_existing_one(self) -> None:
        assert HIDDEN_SECRET == "<secreto oculto>"

    @pytest.mark.parametrize("value", [None, 3, b"https://a:b@c"])
    def test_only_texts(self, value: object) -> None:
        with pytest.raises(TypeError):
            hide_url_credentials(value)  # type: ignore[arg-type]
