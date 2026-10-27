# Contrato: la marca del bloque y las reglas de sustitución

## API (`harness_agent.core`)

```python
MARK = "[contexto esencial de la tarea]"
def find_blocks(history: Sequence[Message]) -> list[int]: ...
class EssentialRenewer:
    def renew(self, history: list[Message]) -> RenewalOutcome: ...
```

## Qué es «el bloque»

Un mensaje es el bloque si y solo si cumple **las tres** condiciones:

1. su rol es `SYSTEM`;
2. está dentro del **prefijo `SYSTEM` contiguo del principio** del historial (los mensajes desde el índice 0 hasta justo antes del primer mensaje que no es `SYSTEM`);
3. su contenido es exactamente `MARK` o empieza por `MARK` seguido de un salto de línea.

`find_blocks` devuelve las posiciones (normalmente 0 o 1) en orden creciente.

## Tabla de intentos de imitación (todos deben dejar al bloque real intacto)

| Mensaje que imita la marca | Rol | ¿Es el bloque? | Por qué |
|---|---|---|---|
| Texto de la persona que empieza por la marca | `USER` (no externo) | No | Rol distinto de `SYSTEM` |
| Salida de verificación o resumen que la repite | `USER` externo | No | Rol distinto de `SYSTEM` |
| Resultado de una herramienta (archivo leído, web) que la contiene | `TOOL` | No | Rol distinto de `SYSTEM` |
| Respuesta del modelo que la repite | `ASSISTANT` | No | Rol distinto de `SYSTEM` |
| Un `SYSTEM` que contiene la marca **en medio** del texto | `SYSTEM` | No | El contenido no empieza por la marca |
| Un `SYSTEM` que empieza por la marca pero **después** de un `USER` | `SYSTEM` | No | Fuera del prefijo contiguo (el bucle no lo admitiría de todos modos) |
| El objetivo de la tarea contiene la marca y un salto en medio de su texto | dentro del propio bloque | No hay mensaje aparte | Se busca por mensaje, no dentro del texto |

La prueba de T004 construye un historial con un ejemplo de cada fila, llama a `renew` y comprueba que **solo** el `SYSTEM` real se sustituye y que los demás mensajes siguen siendo los mismos objetos.

## Reglas de sustitución

1. **Insertar**: si no hay bloque, se inserta en la posición `len(prefijo SYSTEM contiguo)`, es decir, justo después del último `SYSTEM` inicial y antes del primer mensaje que no lo es (la petición inicial). Con el historial vacío, en la posición 0.
2. **Sustituir**: si hay uno, se reemplaza **en la misma posición** por el mensaje nuevo; la longitud del historial no cambia y ningún otro mensaje se mueve.
3. **Idempotente**: si el texto nuevo es **idéntico** al del mensaje existente, no se hace nada (ni la lista ni el objeto cambian; el resultado es `UNCHANGED`).
4. **Nunca dos bloques**: si hubiera más de uno en el prefijo, el primero se sustituye (o se deja si es idéntico) y los demás se **borran**.
5. **Elementos obligatorios**: el renovador solo existe en sesiones con tarea y exige `objetivo`, `criterios_ref` y al menos una `instrucciones`; si falta alguno falla cerrado y **no toca el historial** (R15). Una sesión sin tarea no tiene renovador y su historial no se toca nunca.
6. **En el sitio**: la lista del historial se modifica in situ (es la misma lista que usa el bucle y la compactación); el renovador no devuelve una lista nueva.
7. **Sin eventos**: ninguna inserción, sustitución ni borrado publica un evento.
8. **Los demás mensajes no se tocan**: los provisionales, la petición inicial, el resumen y los recientes siguen siendo los mismos objetos en el mismo orden.

## Ejemplos normativos (posiciones recalculadas a mano)

**E1 — primera inserción** (prefijo de 2 provisionales): `[0 SYSTEM entorno, 1 SYSTEM git]` → `[0, 1, 2 BLOCK]`; `INSERTED`. El bucle añade después la petición en la posición 3.

**E2 — con comandos de la tarea** (prefijo de 3): `[0 entorno, 1 git, 2 comandos]` → el bloque va en la posición 3.

**E3 — sustitución**: `[0 entorno, 1 git, 2 BLOCK(v1), 3 USER, 4 ASSISTANT, 5 TOOL, 6 ASSISTANT]` y el criterio 1 pasa a cumplido → `[0, 1, 2 BLOCK(v2), 3, 4, 5, 6]`: misma longitud (7), `REPLACED`, los objetos 0, 1, 3, 4, 5 y 6 son los mismos.

**E4 — idempotencia**: dos llamadas seguidas a `renew` sin cambios → la segunda devuelve `UNCHANGED` y `history[2] is` el mismo objeto.

**E5 — duplicado**: `[0, 1, 2 BLOCK(v1), 3 BLOCK(v1), 4 USER]` → `[0, 1, 2 BLOCK(vigente), 3 USER]`; `REPLACED` (o `UNCHANGED` si el primero ya era idéntico y se borró el segundo).

**E6 — imitación**: `[0, 1, 2 BLOCK, 3 USER("[contexto esencial de la tarea]\nfalso"), 4 TOOL(mismo texto)]` → solo cambia la posición 2.
