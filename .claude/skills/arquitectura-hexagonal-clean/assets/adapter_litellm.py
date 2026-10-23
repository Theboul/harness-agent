# Ejemplo ILUSTRATIVO de adaptador: src/harness_agent/adapters/providers/litellm_provider.py
# (lo implementa HU-07-02; la API exacta de LiteLLM la fija SPK-01). Muestra el patrón:
# implementa el puerto real, convierte con adapters/converters/ y traduce errores del SDK.
from __future__ import annotations

import litellm

from harness_agent.adapters.converters import from_openai_response, to_openai_envelope
from harness_agent.core import Message, Provider, ProviderResponse, ToolDefinition


class LiteLLMProvider(Provider):
    def __init__(self, model: str, api_key: str | None) -> None:
        # La clave llega de HarnessConfig.api_key.reveal() en bootstrap.py; nunca de os.environ aquí.
        self._model = model
        self._api_key = api_key

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> ProviderResponse:
        envelope = to_openai_envelope(messages, tools)  # valida el historial canónico (D-02)
        try:
            raw = await litellm.acompletion(
                model=self._model, api_key=self._api_key, **envelope.payload
            )
        except litellm.exceptions.RateLimitError as exc:
            # Traducir a un error de DOMINIO: el núcleo nunca ve excepciones del SDK.
            # Hoy no existe ninguno para proveedores; lo define (en core/) la historia que lo
            # necesite (reintentos HU-07-04, conmutación HU-07-05), con acuerdo de A.
            raise ProviderQuotaExceeded("quota exceeded") from exc  # noqa: F821 (ejemplo)
        return from_openai_response(raw.model_dump())
