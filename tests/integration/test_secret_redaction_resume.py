"""A key typed by the person never reaches the database, and /reanudar rebuilds without it
(HU-10-02 / T004). Realistic key shapes are built by concatenation in the test.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_agent.bootstrap import Composition, run_session
from harness_agent.config import Secret
from harness_agent.core import HIDDEN_SECRET, ProviderResponse, Role
from tests.doubles import FakeProvider
from tests.unit.bootstrap_support import build, make_config

PATTERN_KEY = "gsk_" + "Ab3dEf6hIj9kLm2nOp5qRs8tUv1wXy4z"
PROVIDER_KEY = "provider-key-without-any-known-prefix"
ENV_VALUE = "value-of-a-key-like-variable-77"


@pytest.fixture
def opened() -> Iterator[list[Composition]]:
    compositions: list[Composition] = []
    yield compositions
    for composition in compositions:
        composition.close()


def make(
    tmp_path: Path, opened: list[Composition], *texts: str
) -> tuple[Composition, FakeProvider]:
    workspace = tmp_path / "trabajo"
    workspace.mkdir(exist_ok=True)
    config = make_config(tmp_path, workspace=workspace, api_key=Secret(PROVIDER_KEY))
    provider = FakeProvider([ProviderResponse(content=text) for text in texts])
    composition = build(
        opened,
        config,
        provider,
        system_name="Linux",
        environ={"SERVICE_API_KEY": ENV_VALUE, "PATH": "/usr/bin"},
    )
    return composition, provider


async def drive(composition: Composition, *lines: str) -> str:
    output = io.StringIO()
    await run_session(
        composition,
        input_stream=io.StringIO("".join(f"{line}\n" for line in (*lines, "/salir"))),
        output=output,
    )
    return output.getvalue()


def everything_on_disk(composition: Composition) -> str:
    connection = composition.store.connection()
    names = [
        name
        for (name,) in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return repr({n: connection.execute(f"SELECT * FROM {n}").fetchall() for n in names})


async def test_no_secret_reaches_the_database_and_the_model_still_sees_it(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past, provider = make(tmp_path, opened, f"entendido, usaré {PATTERN_KEY}")

    await drive(past, f"mi clave es {PATTERN_KEY}, la otra {PROVIDER_KEY} y {ENV_VALUE}")

    disk = everything_on_disk(past)
    for secret in (PATTERN_KEY, PROVIDER_KEY, ENV_VALUE):
        assert secret not in disk
    assert HIDDEN_SECRET in disk
    # What the model saw in the live session is untouched.
    sent = " ".join(m.content for m in provider.received[0])
    assert PATTERN_KEY in sent and PROVIDER_KEY in sent and ENV_VALUE in sent


async def test_resuming_rebuilds_a_conversation_without_the_secret(
    tmp_path: Path, opened: list[Composition]
) -> None:
    past, _ = make(tmp_path, opened, f"hecho con {PATTERN_KEY}")
    await drive(past, f"usa {PATTERN_KEY}")
    past.close()
    past_id = str(past.session_id)

    current, provider = make(tmp_path, opened, "ok")
    await drive(current, f"/reanudar {past_id}", "sigamos")

    history = [m for m in provider.received[0] if m.role is not Role.SYSTEM]
    assert [m.content for m in history] == [
        f"usa {HIDDEN_SECRET}",
        f"hecho con {HIDDEN_SECRET}",
        "sigamos",
    ]
    assert all(PATTERN_KEY not in m.content for m in provider.received[0])
