# Plan: HU-06-02 — `preguntar_usuario` y arreglos de UX

**Spec**: [spec.md](spec.md) · Skills aplicadas: `arquitectura-hexagonal-clean`, `estructura-carpetas-harness`, `verificar-fronteras-hexagonales`.

## Decision Gates (arquitectura-hexagonal-clean)

| Gate | Resultado |
|---|---|
| ¿Es una regla de negocio de `core/`? | Solo la política de «herramientas abiertas» (qué nombres no preguntan): `core/permissions/open_tools.py`. Limpieza del texto libre: se reutiliza `clean_reason` (API pública). |
| ¿Necesita un puerto nuevo? | **No.** `ask` es un invocable definido en el adaptador (`AskFn`); `core/interfaces/` y el catálogo de eventos no cambian. |
| ¿Es un adaptador? | Sí: `adapters/tools/ask_user.py` (herramienta; `Tool` ya es puerto). |
| ¿Dónde se conecta? | Solo `bootstrap.py` (`compose(…, ask=)`, `main()` inyecta la consola). |
| ¿Cómo se prueba? | Unitarias con `ask` falso; integración con `AgentLoop` real + consola con entrada simulada. |

## Estructura (estructura-carpetas-harness)

| Archivo nuevo | Fila / receta |
|---|---|
| `src/harness_agent/adapters/tools/ask_user.py` | Herramienta nativa → `adapters/tools/` (receta «nueva herramienta») |
| `src/harness_agent/core/permissions/open_tools.py` | Regla de permisos → `core/permissions/` |
| `src/harness_agent/cli/question.py`, `cli/question_view.py` | Interacción en terminal → `cli/` (como `approval.py` / `approval_view.py`) |
| `tests/unit/adapters/tools/test_ask_user.py`, `tests/unit/core/permissions/test_open_tools.py`, `tests/unit/cli/test_question.py`, `test_question_view.py`, `tests/integration/test_ask_user_loop.py` | Carpeta equivalente de `tests/` |
| `tests/architecture/test_ask_user_boundaries.py` | Guarda `ast` de la frontera nueva |

Archivos existentes que cambian (mínimo): `adapters/tools/__init__.py` y `cli/__init__.py` (exports), `core/permissions/__init__.py` + `core/__init__.py` (export), `bootstrap.py` (parámetro `ask`, registro, envoltura de política, inyección en `main`), `adapters/providers/litellm_provider.py` (silencio), `cli/approval_view.py`, `cli/render.py`.

## Diseño

- **`AskUserTool(ask)`**: esquema `pregunta` (1..300), `opciones` (2..8 textos de 1..120), `permitir_texto_libre` (bool, por defecto `true`). `run` valida lo que el esquema no cubre (opciones duplicadas o vacías tras limpiar), llama a `ask(Question)`; `Answer(number, text)`: con `number` válido devuelve la opción del propio modelo; sin número, el texto libre limpiado con `clean_reason` (si no se permitía el texto o queda vacío → `[sin_respuesta]`). Excepción de `ask` → `[sin_respuesta]`; `CancelledError` se propaga.
- **`OpenToolsPolicy(inner, names, *, ask_names=())`**: convierte `ASK` en `ALLOW` solo para `names` (sin pasar por `ask_names`); `DENY` y todo lo demás pasan; falla cerrado. Va **dentro** de `ExactCallPolicy` y debajo de `AskCeilingPolicy`, `GitPolicy`, `CommandPolicy` y `ProtectedPolicy`.
- **`ConsoleQuestioner`** (`__call__(request) -> Reply | None`): usa tipos propios de `cli` (`QuestionRequest` por protocolo, `Reply`) para no importar `adapters`; `bootstrap.py` adapta `Question`/`Answer`.
- **Vista de la pregunta** (`question_block`, pura): `? pregunta` + `  [n] opción` + línea de ayuda; limpia controles y escapa saltos.
- **UX-a**: `_load_completion` fija `litellm.suppress_debug_info = True` y deja el logger `LiteLLM` en `CRITICAL` sin propagar, solo cuando se carga el módulo real.
- **UX-b**: `approval_view` ajusta el «Efecto» en líneas de ≤ 60 columnas sangradas; tope de seguridad 1 000 caracteres (con «…» solo si se supera); `EFFECT_TRANSLATIONS` fija por nombre de herramienta nativa (`leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto`, `shell`, `preguntar_usuario`); desconocida → texto recibido.
- **UX-c**: `render._provider_error` rama `retry`.

## Constitution Check

| Principio / skill | Resultado |
|---|---|
| Núcleo solo stdlib; sin `print`/`input` en `core/` | Cumple (`open_tools.py` puro). |
| Fallar cerrado | Cumple (sin respuesta = error, nunca opción por defecto; política abre solo nombres explícitos). |
| Contratos protegidos intactos | Cumple. |
| Sin secretos | La respuesta libre pasa por `hide_url_credentials` vía `clean_reason`. |
| Lista de comprobación `capas-y-reglas.md` | ¿Adaptador sin importar `cli`? sí. ¿`cli` sin importar `adapters`? sí (duck-typing). ¿Dependencias por constructor? sí. ¿Una sola raíz de composición? sí (`bootstrap.py`). ¿Puerto nuevo? no (justificado: `ask` es detalle del adaptador). |

## Hallazgos esperados

1. El bucle marca `is_external=True` todo resultado de herramienta: la respuesta de la persona viaja como dato externo (no se puede cambiar sin tocar `core/loop.py`).
2. `OpenToolsPolicy` es una regla de permisos nueva en `core/`; A y B deben ratificarla.
