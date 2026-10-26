# Research: HU-01-06 — Límites de ejecución

Sin incógnitas técnicas abiertas; las decisiones de vocabulario están en `spec.md § Clarifications`.

## D1. Dónde vive la lógica

- **Decisión**: `core/limits.py` (módulo nuevo, puro, solo stdlib) con `SessionLimits`, `LimitKind`, `LimitReached`, `LimitTracker`. El bucle solo orquesta (pregunta, cuenta y publica).
- **Razón**: la regla de negocio va en `core/`; mantiene el cambio en `core/loop.py` (protegido, dueño A) pequeño y aislado, que es lo que pide el aviso de colisión.
- **Alternativas**: contadores directos en el bucle (más líneas en el archivo protegido, difícil de probar aislado); decorador del `Provider` (no ve las tareas ni puede publicar eventos, y cambiaría la composición).

## D2. Nombre frente a `config.Limits`

- **Decisión**: el tipo del núcleo se llama `SessionLimits`. `config.Limits` (dueño B) conserva el suyo y `bootstrap.py` los mapea campo a campo.
- **Razón**: la nota de HU-00-04 (D5) deja dos salidas (mapear en la raíz o que `config.py` importe del núcleo); mapear no toca `config.py` ni invierte la frontera y evita dos clases con el mismo nombre en un mismo módulo.
- **Alternativa**: que `config.py` importe de `core` (la frontera lo permite: `config → core`), pero exige coordinar con B; queda como mejora posible.

## D3. Reloj

- **Decisión**: `clock: Callable[[], float]` (segundos monótonos) inyectable en `LimitTracker` y en `AgentLoop`; por defecto `time.monotonic`.
- **Razón**: determinismo en pruebas; el reloj de pared puede retroceder; `time` es stdlib sin E/S.

## D4. Momento de la comprobación

- **Decisión**: al inicio de cada vuelta del `while`, antes de calcular las definiciones de herramientas y de llamar al proveedor. La llamada se cuenta justo antes de hacerla; el consumo se suma tras validar la respuesta.
- **Razón**: regla 2 de la ficha («antes, no después»); una respuesta inválida no suma consumo y una excepción del proveedor no pierde el conteo del turno.

## D5. Consumo

- **Decisión**: suma de `usage.total_tokens` (entrada + salida). Dato ausente, negativo o no entero = 0.
- **Razón**: el presupuesto es de toda la ejecución. Sin dato no se puede restar ni inventar; el límite de turnos sigue protegiendo.

## D6. Parada de la tarea

- **Decisión**: `TurnStatus.LIMIT_REACHED` (aditivo), `final_response=None`, el historial intacto (incluida la tarea del usuario, sin mensaje del asistente) y `error` con descripción corta en inglés.
- **Razón**: igual que `PROVIDER_FAILED`; ningún consumidor existente hace `match` exhaustivo sobre `TurnStatus` (comprobado con búsqueda).

## D7. Qué dice la CLI

- **Decisión**: `render.py` lee `limit`, `maximum` (y `used`) solo si son del tipo esperado y `limit` es uno de los tres; si no, el texto genérico actual.
- **Razón**: AC-01 «explica el motivo». La CLI no inventa campos (convención ya acordada).
