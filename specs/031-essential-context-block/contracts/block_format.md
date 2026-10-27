# Contrato: el texto exacto del bloque esencial

El bloque es **un único mensaje `SYSTEM`** cuyo contenido es una función pura de los elementos guardados y del estado de los criterios. Mismos datos, mismo texto, byte a byte.

## API (`harness_agent.core`)

```python
def render_block(items: Sequence[EssentialItem], criteria: Sequence[TaskCriteriaItem]) -> str: ...
def block_message(text: str) -> Message: ...      # Message(Role.SYSTEM, text)
def block_fits(text: str, settings: ContextSettings, model: str) -> bool: ...
```

## Forma

```text
[contexto esencial de la tarea]
Contexto fijo de la tarea: lo guarda el harness fuera del historial y se te entrega completo en cada llamada.

Ticket: <ticket en una línea>

Objetivo:
<objetivo>

Reglas:
<reglas>

Criterios de aceptación (estado actual):
1. [pendiente] <descripción en una línea>
2. [cumplido] <descripción en una línea>
```

## Reglas

1. **Cabecera fija**: las dos primeras líneas (la marca y la frase) van siempre. La marca es exactamente `[contexto esencial de la tarea]` (31 caracteres).
2. **Orden fijo**: Ticket, Objetivo, Reglas, Criterios. Las secciones se separan con **una línea en blanco**; el texto **no termina** en salto de línea.
3. **Sin encabezados vacíos**: un elemento ausente (sin título, sin reglas, sin criterios) se omite **entero**, con su encabezado. Un bloque sin ninguno de los cuatro elementos **no existe** (no se envía solo la cabecera).
4. **Ticket**: una sola línea (los espacios y saltos se colapsan a un espacio).
5. **Objetivo y reglas**: el texto guardado, con sus saltos de línea internos, sin espacios sobrantes en los extremos.
6. **Criterios**: numerados desde 1 en el orden de la fuente; una línea por criterio; el estado es `pendiente` (si `passes` es falso, también el semántico que espera validación humana) o `cumplido` (si es verdadero). **Nunca** se muestran el comando, la condición ni la evidencia. La descripción se limpia en cada renovación: sin caracteres de control ni de formato, espacios y saltos colapsados a uno, credenciales de URL ocultas con `core/redaction.py`.
7. **Las instrucciones no aparecen** (Q2 = A): la clave `instrucciones` se ignora al armar el texto.
8. **Sin variables**: ni fecha, ni identificadores de sesión, ni contadores. Lo único que puede cambiar el texto es el valor de un elemento o el estado de un criterio.

## Ejemplos normativos

### E1 — tarea completa (444 caracteres, 115 tokens estimados)

Elementos: ticket `TAREA-14: Validar el correo`; objetivo `Rechazar correos sin dominio en el formulario de alta.`; reglas `No tocar el esquema de la base.` + salto + `Mantener la API pública.`; criterios: (1) `pendiente` «El validador rechaza a@ y a@b», (2) `cumplido` «Las pruebas del formulario pasan».

```text
[contexto esencial de la tarea]
Contexto fijo de la tarea: lo guarda el harness fuera del historial y se te entrega completo en cada llamada.

Ticket: TAREA-14: Validar el correo

Objetivo:
Rechazar correos sin dominio en el formulario de alta.

Reglas:
No tocar el esquema de la base.
Mantener la API pública.

Criterios de aceptación (estado actual):
1. [pendiente] El validador rechaza a@ y a@b
2. [cumplido] Las pruebas del formulario pasan
```

### E2 — el criterio 1 pasa a cumplido (443 caracteres, 115 tokens)

El mismo texto de E1 cambiando solo la línea `1. [pendiente] El validador rechaza a@ y a@b` por `1. [cumplido] El validador rechaza a@ y a@b`. Una letra menos (`cumplido` tiene 8 caracteres y `pendiente` 9): 443 caracteres.

### E3 — sin título ni reglas (254 caracteres, 68 tokens)

```text
[contexto esencial de la tarea]
Contexto fijo de la tarea: lo guarda el harness fuera del historial y se te entrega completo en cada llamada.

Objetivo:
Documentar la API.

Criterios de aceptación (estado actual):
1. [pendiente] El README describe la API
```

No hay línea `Ticket:` ni `Reglas:`.

### E4 — sin criterios legibles

Con `criterios_ref` presente y una lista vacía de criterios, el texto es el de E3 sin las dos últimas secciones: la cabecera y `Objetivo:` con su texto. Con solo el ticket y nada más, la cabecera y `Ticket: …`.

### E5 — descripción con saltos y caracteres ocultos

Una descripción `Pasa la suite` + salto de línea + `completa` + U+200B + ` (sin saltos)` (donde `U+200B` es el carácter de ancho cero) se muestra en una sola línea: `1. [pendiente] Pasa la suite completa (sin saltos)`.

### E6 — credencial de URL

Un objetivo que contiene una URL con usuario y clave (`https://` + `usuario` + `:` + `clave` + `@servidor.example/r.git`) se **guarda** ya con la credencial oculta: `https://<secreto oculto>@servidor.example/r.git`. El texto de la clave no aparece en la tabla ni en el bloque.

### E7 — el bloque no cabe

Con el umbral por defecto (25 600 tokens) el bloque puede pesar como mucho 5 120 tokens estimados (20 464 caracteres). Un bloque de 20 465 caracteres o más lanza `EssentialContextTooLarge` con el mensaje fijo `El elemento «bloque completo» del contexto esencial supera el tope de 5120 tokens.` (sin valores) y **no se trunca**. Un elemento de más de 8 000 caracteres da `El elemento «objetivo» del contexto esencial supera el tope de 8000 caracteres.` (o `reglas`, `ticket`, `criterios`). Con una ventana de 1 000 tokens y umbral del 45 % (450), el límite es 90 tokens y el bloque E1 (115) **no cabe**.
