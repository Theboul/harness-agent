# Contrato: la condición esperada de un criterio

## Gramática (única en esta versión)

```text
condición  := "codigo_salida" espacios? operador espacios? número
operador   := "==" | "!="
número     := de 1 a 10 dígitos decimales, valor entre 0 y 4294967295
espacios   := espacios o tabulaciones
```

- Se compara el texto entero (sin espacios exteriores). Distingue mayúsculas: `codigo_salida` va en minúsculas y sin tilde.
- No hay signos, ni otros operadores, ni más condiciones encadenadas, ni texto de salida.
- Cualquier otra cosa hace **inválida la tarea al cargarla** (`TaskFormatError("condicion_no_soportada")`); no se llega a verificar.

## API (`harness_agent.core`)

```python
MAX_EXIT_CODE = 4_294_967_295

@dataclass(frozen=True)
class Condition:
    operator: str   # "==" o "!="
    value: int

def parse_condition(text: object) -> Condition | None: ...
def condition_met(condition: Condition, exit_code: int | None) -> bool: ...
```

Garantías: ambas funciones son puras y totales (ninguna entrada lanza); `condition_met(c, None)` es `False`; ampliar la gramática en el futuro (por ejemplo «la salida contiene un texto») no invalida ninguna condición de esta tabla.

## Mensaje del analizador

Código `condicion_no_soportada`, texto fijo que no reproduce lo recibido:

> Un criterio tiene una condición que no se admite: usa 'espera: codigo_salida == N' o 'espera: codigo_salida != N' con N entre 0 y 4294967295.

## Ejemplos normativos

| Texto de `espera:` | `parse_condition` | Notas |
|---|---|---|
| `codigo_salida == 0` | `Condition("==", 0)` | La forma del contrato de HU-11-01 |
| `codigo_salida==0` | `Condition("==", 0)` | Los espacios son opcionales |
| `  codigo_salida != 1  ` | `Condition("!=", 1)` | Espacios exteriores ignorados |
| `codigo_salida == 4294967295` | `Condition("==", 4294967295)` | Máximo admitido |
| `salida 0` | `None` | Era la forma del ejemplo antiguo de HU-11-01 |
| `ok` | `None` | |
| `codigo_salida >= 0` | `None` | Otro operador |
| `codigo_salida == -1` | `None` | Sin signos |
| `CODIGO_SALIDA == 0` | `None` | Distingue mayúsculas |
| `codigo_salida = 0` | `None` | Un solo `=` |
| `codigo_salida == 4294967296` | `None` | Por encima del máximo |
| `codigo_salida ==` | `None` | Falta el número |
| `codigo_salida == 0 y ok` | `None` | Nada más |

| Condición | Código de salida | `condition_met` |
|---|---|---|
| `== 0` | `0` | `True` |
| `== 0` | `1` | `False` |
| `== 0` | `None` (no se ejecutó o tiempo agotado) | `False` |
| `!= 0` | `1` | `True` |
| `!= 0` | `0` | `False` |
| `!= 0` | `None` | `False` |
| `== 3` | `3` | `True` |
