# adapters/providers/litellm_provider.py (ejemplo)
import litellm

from harness_agent.core.errors import CuotaAgotada


class LiteLLMProvider:
    def __init__(self, modelo: str) -> None:
        self._modelo = modelo

    def completar(self, mensajes, herramientas):
        try:
            crudo = litellm.completion(model=self._modelo, messages=_a_formato_proveedor(mensajes))
        except litellm.RateLimitError as e:
            raise CuotaAgotada(str(e)) from e
        return _a_respuesta_interna(crudo)
