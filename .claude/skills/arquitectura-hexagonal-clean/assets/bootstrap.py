# Ejemplo ILUSTRATIVO de la raíz de composición. La real es src/harness_agent/bootstrap.py (HU-00-08).
# Es el único módulo que conoce núcleo, adaptadores, configuración y CLI a la vez.
# Las pruebas de integración antiguas conectan a mano (make_rig); las nuevas pueden usar compose().
from __future__ import annotations

import uuid

from harness_agent.cli import run_cli
from harness_agent.config import load_config
from harness_agent.core import (
    DefaultPermissionPolicy,
    InMemoryEventBus,
    InMemoryToolRegistry,
    Message,
)
from harness_agent.core.loop import AgentLoop  # bootstrap puede importar submódulos; cli/ no


async def main() -> int:
    config = load_config()
    bus = InMemoryEventBus()
    registry = InMemoryToolRegistry()
    area = make_authorized_area(config.paths.workspace_root)  # adaptador de HU-01-03; None => sin área
    # registry.register(ReadFileTool(area)) ...                # herramientas de HU-01-03
    policy = DefaultPermissionPolicy(registry, area, config.permissions)
    provider = make_provider(config)  # FakeProvider (HU-00-03) o LiteLLMProvider (HU-07-02)
    loop = AgentLoop(provider, registry, policy, bus)

    session_id = str(uuid.uuid4())
    history: list[Message] = []

    async def run_turn(task: str) -> object:
        return await loop.run_turn(session_id=session_id, task=task, history=history)

    return await run_cli(bus, run_turn)  # su valor es el código de salida del proceso (D9)
