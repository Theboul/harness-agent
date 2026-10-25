# Contract: `harness_agent.core` — estimación y ensamblado (HU-02-01)

API pública nueva exportada en `core/__init__.py` (sin tocar `core/interfaces/`).

```python
# estimator
def estimate_text(text: str) -> int                         # ceil(len/4); "" -> 0
def estimate_message(message: Message) -> int
def estimate_tool_definition(definition: ToolDefinition) -> int
def estimate_messages(messages: Sequence[Message]) -> int

class TokenEstimator:
    def factor(self, session_id: str) -> float              # 1.0 sin calibrar
    def calibrated(self, session_id: str, raw_tokens: int) -> int   # ceil(raw * factor)
    def observe(self, session_id: str, raw_tokens: int, reported_input_tokens: int) -> None

# prefix
@dataclass(frozen=True) class PrefixSpec: instructions; rules; os_name; interpreter
@dataclass(frozen=True) class StablePrefix: system_message; tools; fingerprint
def build_prefix(spec: PrefixSpec, definitions: Sequence[ToolDefinition]) -> StablePrefix

# assembler
@dataclass(frozen=True) class AssembledContext: prefix; history; raw_tokens; estimated_tokens
class ContextAssembler:
    def __init__(self, spec: PrefixSpec, definitions: Callable[[], Sequence[ToolDefinition]],
                 estimator: TokenEstimator | None = None) -> None
    def assemble(self, session_id: str, history: Sequence[Message]) -> AssembledContext
    def record_usage(self, session_id: str, usage: TokenUsage | None) -> None

class ContextConfigError(ValueError)
```

## Garantías

1. Mismo `session_id` ⇒ mismo `StablePrefix` (misma huella, mismo objeto) en todos los ensamblados, aunque cambien `definitions()` o el orden de registro.
2. Mismo conjunto de definiciones en cualquier orden ⇒ misma huella.
3. `assemble` no muta `history` ni devuelve alias de sus mensajes.
4. `observe`/`record_usage` ignoran informes nulos, cero o negativos y estimaciones crudas de cero; el factor siempre queda en [0,25 ; 4,0].
5. Los errores son `ContextConfigError` con mensaje fijo en español que no reproduce valores.
6. Sin E/S, sin entorno, sin terminal, sin eventos.

## Punto de integración (no implementado aquí; hallazgo para A)

```python
assembled = assembler.assemble(session_id, history)
response = await provider.complete(assembled.provider_messages(), list(assembled.tools))
assembler.record_usage(session_id, response.usage)
```
