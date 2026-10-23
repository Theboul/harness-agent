# Contrato: sección `[permissions]` del archivo de configuración (HU-05-01)

**Spec**: [../spec.md](../spec.md) (FR-021, FR-022, FR-023) · **Plan**: [../plan.md](../plan.md) · **Amplía**: el esquema de `config.py` de HU-00-04 (que dejó las reglas de permisos para esta historia)

La ampliación es mínima y no puede crear reglas de permitir. No se editan los documentos de HU-00-04; este contrato recoge el cambio.

## 1. Esquema

```toml
# Sección opcional. Sin ella (o con las listas vacías) rigen solo las reglas integradas.
[permissions]
deny = ["herramienta_peligrosa"]     # siempre se deniegan
ask  = ["herramienta_delicada"]      # siempre se preguntan (denegar prevalece si está en ambas)
```

| Campo | Tipo | Por defecto | Validación |
|---|---|---|---|
| `permissions` | tabla | ausente = vacía | Si no es una tabla: `debe ser una tabla.` |
| `permissions.deny` | lista de textos | `[]` | Cada elemento es un texto con algún carácter que no sea un espacio |
| `permissions.ask` | lista de textos | `[]` | Igual |

- Los nombres se comparan **tal cual** (distinguen mayúsculas); no se recortan.
- Los duplicados se descartan conservando el primer orden; una lista vacía es válida.
- **No existe `allow`**: cualquier otro campo de `[permissions]` (incluido `allow`) es un campo desconocido y detiene el arranque con el mensaje existente `campo desconocido en el esquema.`, nombrando el campo (`permissions.allow`).

## 2. Mensajes

Siguen el formato de `InvalidConfigError` de HU-00-04 (todos los problemas juntos, sin reproducir valores):

| Caso | Línea del mensaje |
|---|---|
| `deny` o `ask` no es una lista, o algún elemento no es un texto no vacío | `- permissions.deny: debe ser una lista de textos no vacíos.` (igual con `ask`) |
| `permissions` no es una tabla | `- permissions: debe ser una tabla.` |
| Campo desconocido (`allow`, `permitir`…) | `- permissions.allow: campo desconocido en el esquema.` |

Orden de los problemas: primero los de `limits`, luego `paths`, luego `permissions` entre los presentes, y al final los campos desconocidos (el orden de HU-00-04).

## 3. Resultado

`HarnessConfig.permissions` es un `PermissionRules` (`deny` y `ask` como tuplas inmutables). El campo es el último de `HarnessConfig` y vale `PermissionRules()` por defecto: ninguna construcción existente cambia.

## 4. Plantilla

`config.example.toml` incluye la sección **comentada** (`# [permissions]`, `# deny = []`, `# ask = []`) con su explicación y la advertencia de que no hay reglas de permitir. Comentada, porque la prueba de plantillas existente exige que el TOML crudo declare solo `model`, `limits` y `paths`.

## 5. Lo que NO hace

No lee `.env`, no admite secretos ni reglas de permitir, no admite patrones ni comodines y no recarga en caliente.
