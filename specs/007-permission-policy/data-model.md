# Data Model: HU-05-01 — Política denegar, preguntar, permitir que falla cerrada

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Contratos**: [contracts/policy_contract.md](contracts/policy_contract.md), [contracts/permissions_config_contract.md](contracts/permissions_config_contract.md)

La historia reutiliza `ToolCall`, `PermissionDecision`, `RiskLevel`, `ToolRegistry`, `AuthorizedArea` y `PermissionPolicy` (sin cambios). Este documento describe solo los datos nuevos.

## 1. `PermissionRules` (`core/permissions/rules.py`)

Dato inmutable (`@dataclass(frozen=True, slots=True)`).

| Campo | Tipo | Por defecto | Descripción |
|---|---|---|---|
| `deny` | `tuple[str, ...]` | `()` | Nombres de herramienta que siempre se deniegan |
| `ask` | `tuple[str, ...]` | `()` | Nombres de herramienta que siempre se preguntan (salvo si también están en `deny`) |

**Reglas de validación**

- R-1: cada nombre es un `str` no vacío (con algún carácter que no sea un espacio); si no, `ValueError` con un mensaje en español que nombra el campo y la posición, sin reproducir el valor.
- R-2: los duplicados dentro de una lista se descartan conservando el primer orden; una lista vacía es válida.
- R-3: no existe ningún campo `allow`: no hay forma de expresar una regla de permitir.
- R-4: un nombre puede estar en `deny` y en `ask`: gana `deny` (AC-02).

## 2. `DefaultPermissionPolicy` (`core/permissions/policy.py`)

Implementa `PermissionPolicy`. No tiene estado entre llamadas.

| Atributo (privado) | Tipo | Descripción |
|---|---|---|
| `_registry` | `ToolRegistry` | Para consultar el riesgo por nombre |
| `_area` | `AuthorizedArea \| None` | El área autorizada; `None` = no hay área configurada |
| `_rules` | `PermissionRules` | Las listas `deny` y `ask` |
| `_allow_reads` | `bool` | Regla de lectura activa (por defecto `True`; supuesto del PO) |

**Constructor**: `DefaultPermissionPolicy(registry, area=None, rules=PermissionRules(), *, allow_reads_in_area=True)`; `TypeError` en español si `registry` no es un `ToolRegistry`, `area` no es un `AuthorizedArea` ni `None`, o `rules` no es un `PermissionRules`.

**Operación**: `evaluate(call) -> PermissionDecision`. No lanza `Exception`.

## 3. Tabla de decisión (resumen; el orden de evaluación está en el contrato)

| Paso | Condición | Decisión |
|---|---|---|
| 0 | `call` no es `ToolCall`, el nombre no es texto o está vacío, o `arguments` no es un diccionario | Denegar |
| 1 | El nombre está en `deny` | Denegar |
| 2 | El nombre está en `ask` | Preguntar |
| 3 | No está registrada, o su riesgo no es un `RiskLevel` | Preguntar |
| 4 | Riesgo alto | Preguntar |
| 5 | Riesgo medio, o riesgo bajo con `path` (y regla de lectura activa) | Regla del área (siguiente tabla) |
| 6 | Riesgo bajo sin `path`, o riesgo bajo con `path` y regla de lectura apagada | Preguntar |
| — | Cualquier excepción en los pasos anteriores | Denegar |

**Regla del área (`_inside_area`)** — la usan las dos reglas de permitir (escritura y lectura); todo camino que devuelve «permitir» pasa por aquí y por `AuthorizedArea.contains`:

| Condición | Decisión |
|---|---|
| `path` ausente (riesgo medio), no textual, vacío o con carácter nulo | Denegar |
| No hay área configurada | Preguntar |
| `area.contains(path)` es exactamente `True` | **Permitir** |
| `area.contains(path)` es cualquier otra cosa | Preguntar |
| `area.contains` lanza una excepción | Denegar (paso externo) |

## 4. Cambio en `HarnessConfig` (`config.py`)

| Campo nuevo | Tipo | Por defecto |
|---|---|---|
| `permissions` | `PermissionRules` | `PermissionRules()` (último campo, por defecto vacío: las construcciones existentes no cambian) |

Esquema TOML nuevo (ver el contrato de configuración): tabla opcional `[permissions]` con las listas `deny` y `ask`.

## 5. Qué NO existe (fuera de alcance)

Reglas de permitir configurables, patrones o comodines, lista de comandos peligrosos, análisis de comandos encadenados, aprobación y permiso de sesión, motivo de la decisión en el puerto, y cualquier estado entre llamadas.
