# Research: HU-02-02 — Recorte de salidas largas de herramientas

Sin dudas externas: todo se resolvió leyendo el código. Cada decisión lleva alternativas descartadas.

## D1 — Dónde se aplica el recorte

- **Decisión**: `InMemoryToolRegistry` guarda junto a cada herramienta registrada una versión servida (`TruncatingTool` si hay máximo, la propia herramienta si no). `get` y `list` devuelven la servida.
- **Hecho**: el bucle (`core/loop.py`, `_lookup`/`_execute`) llama `registry.get(nombre)` y luego `tool.run(...)`; `_tool_definitions` lee `registry.list()` y solo usa `name`/`description`/`schema`. La política (`DefaultPermissionPolicy`) usa `registry.get(...)` para `risk`/`schema`. Ninguno compara identidad.
- **Alternativas**: (a) recortar en `core/loop.py` — protegido y de A; (b) cambiar el puerto `ToolRegistry` con un método `run` — exige acuerdo A/B/C; (c) que cada herramienta se recorte sola — es lo que ya hay y es lo que la historia quiere evitar (una herramienta nueva olvidaría hacerlo).

## D2 — Sin máximo no se envuelve

- **Decisión**: `max_output_chars=None` (por defecto) conserva el comportamiento de HU-01-02: `get` devuelve la instancia registrada.
- **Hecho**: `tests/unit/core/tools/test_registry.py` fija en unas 15 aserciones `registry.get(x) is tool`. Envolver siempre las rompería sin ganancia.
- **Riesgo asumido**: un registro construido a mano sin máximo no recorta. Mitigación: `bootstrap.py` lo pasa siempre y una prueba de composición lo comprueba.

## D3 — Algoritmo de recorte

- **Decisión**: si `len(text) <= max`, devolver el mismo objeto. Si no, reservar la longitud de la marca calculada con el número de dígitos de `len(text)` (cota superior), repartir el resto en `head = kept // 2` y `tail = kept - head` y construir `head + marca + tail` con la cantidad omitida exacta (`len(text) - head - tail`). La marca puede ser un carácter más corta que la reserva si la cantidad tiene menos dígitos; el resultado nunca supera el máximo.
- **Marca**: `"\n[salida recortada: se omitieron N caracteres]\n"`, idéntica a `_notice` de `adapters/system/shell_output.py`, para que el modelo vea un solo formato. `core/` no puede importar el adaptador: el texto se repite y una prueba de arquitectura/contrato verifica que ambos coinciden.
- **Mínimo**: `MIN_MAX_OUTPUT_CHARS = 256`: la marca ocupa unos 50–70 caracteres, así que quedan al menos ~180 de contenido útil.
- **Alternativas**: solo principio (pierde el final, donde suelen estar los errores y los resúmenes de pruebas); solo final; recorte por líneas (no acota una sola línea enorme).

## D4 — Qué máximo por defecto

- **Decisión**: 24 000 caracteres en `Limits.max_tool_output_chars`.
- **Hecho**: `ShellTool` devuelve `"[codigo_de_salida=N] El comando terminó con error.\n" + salida` (hasta 20 000) y `"[tiempo_agotado] …\n" + salida`; las herramientas de archivos acotan listados y búsquedas a 20 000 (`MAX_RESULT_CHARS`). Con 20 000 el registro volvería a recortar la salida del shell por culpa de la cabecera.
- **Efecto declarado**: `leer_archivo` puede devolver hasta 262 144 bytes de contenido; con el recorte general, un archivo mayor que 24 000 caracteres llega al modelo recortado con marca. Es el objetivo de la historia; se anota como observación para HU-02-01.
- **Alternativa**: bajar los acotados de las herramientas a un valor menor — cambiaría el comportamiento de HU-01-03/01-04 (prohibido por FR-011).

## D5 — Configuración

- **Decisión**: `Limits.max_tool_output_chars: int = 24000`, campo opcional de `[limits]` en `config.toml`, entero mayor o igual que `MIN_MAX_OUTPUT_CHARS` (la validación importa la constante de `harness_agent.core`, permitido por la flecha `config.py ──▶ core`). Un booleano no es entero. El mensaje de error no reproduce el valor.
- **Coordinación**: `config.py` es de B (HU-00-04); el cambio es aditivo, como `max_output_tokens` (HU-07-02) y `process_environment()` (HU-01-04); se avisa en `PROGRESO.md`.
- **Alternativa**: variable de entorno — la configuración de límites vive en TOML; el entorno es para secretos.

## D6 — Qué no se toca

Los puertos, `events.py`, `loop.py`, la política, la CLI, los dobles de `tests/doubles/` y los acotados de HU-01-03/01-04 (solo se editan sus docstrings).
