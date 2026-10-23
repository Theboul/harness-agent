# Contrato: política de permisos por defecto (HU-05-01)

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Modelo**: [../data-model.md](../data-model.md) · **Convención de ruta**: [path_argument_convention.md](path_argument_convention.md)

Describe `DefaultPermissionPolicy` y `PermissionRules` (`harness_agent.core.permissions`, reexportados por `harness_agent.core`) y las cláusulas del contrato de pruebas. **No se escribe código aquí.** El puerto `PermissionPolicy` (`evaluate(call) -> PermissionDecision`) no cambia.

## 1. Superficie pública

```text
PermissionRules(deny: tuple[str, ...] = (), ask: tuple[str, ...] = ())          # inmutable

DefaultPermissionPolicy(registry: ToolRegistry,
                        area: AuthorizedArea | None = None,
                        rules: PermissionRules = PermissionRules(),
                        *, allow_reads_in_area: bool = True)
    .evaluate(call: ToolCall) -> PermissionDecision                               # nunca lanza Exception
```

- `area=None` significa «no hay área de trabajo configurada».
- `allow_reads_in_area=False` apaga la regla de lectura (supuesto pendiente de confirmación del PO): las lecturas de riesgo bajo con `path` pasan a «preguntar».
- Errores de construcción (en español, sin reproducir valores): `TypeError` si `registry`, `area` o `rules` no son del tipo esperado; `ValueError` si un nombre de `PermissionRules` no es un texto no vacío.

## 2. Orden de evaluación

| Paso | Condición | Decisión |
|---|---|---|
| 0 | `call` no es un `ToolCall`; el nombre no es texto o está vacío; `arguments` no es un diccionario | Denegar |
| 1 | El nombre está en `rules.deny` | Denegar |
| 2 | El nombre está en `rules.ask` | Preguntar |
| 3 | `registry.get(nombre)` devuelve `None`, o su `risk` no es un `RiskLevel` | Preguntar |
| 4 | Riesgo alto | Preguntar |
| 5 | Riesgo medio; o riesgo bajo con la clave `path` en los argumentos y `allow_reads_in_area` activo | Regla del área (§3) |
| 6 | Riesgo bajo sin `path`; o riesgo bajo con `path` y `allow_reads_in_area` apagado | Preguntar |

Cualquier `Exception` lanzada durante la evaluación (registro, riesgo, comprobador del área) produce **Denegar**. Las `BaseException` que no son `Exception` no se capturan.

## 3. Regla del área (por aquí pasa todo «permitir»)

| Condición sobre `path` | Decisión |
|---|---|
| Ausente (solo posible con riesgo medio), no es texto, es vacío o solo espacios, o contiene un carácter nulo | Denegar |
| No hay área configurada (`area` es `None`) | Preguntar |
| `area.contains(path)` es exactamente `True` | Permitir |
| `area.contains(path)` devuelve cualquier otro valor | Preguntar |

La política no resuelve rutas: la contención sobre la **ruta real** la decide `AuthorizedArea`.

## 4. Lo que la política no hace

- No lee mensajes, historial, resultados ni contenido de archivos (AC-03): solo ve la llamada.
- No guarda estado entre llamadas: la misma llamada, las mismas reglas y el mismo estado del área dan la misma decisión.
- No devuelve un motivo: el motivo que recibe el modelo es el texto genérico que redacta el bucle (Q3). Hallazgo para A y HU-05-03: ese texto no distingue la causa.
- No resuelve «preguntar» como denegar: lo hace el bucle en el Sprint 1 (AC-05) y se retira allí con HU-05-03.

## 5. Cláusulas del contrato de pruebas

`tests/contracts/test_permission_policy_contract.py` ejecuta las cláusulas comunes contra el doble `ScriptedPolicy` y contra la política real (P-1 y P-2); el resto es solo de la política real.

| Cláusula | Descripción | `ScriptedPolicy` | Real |
|---|---|:---:|:---:|
| P-1 | `evaluate` devuelve siempre un `PermissionDecision` (con cualquier entrada) | Sí | Sí |
| P-2 | Es una subclase de `PermissionPolicy` y `evaluate` es síncrono | Sí | Sí |
| P-3 | Herramienta no registrada o sin riesgo → preguntar | No | Sí |
| P-4 | Nombre en `deny` → denegar, aunque esté en `ask` o la ruta esté dentro del área | No | Sí |
| P-5 | Nombre en `ask` → preguntar, aunque la ruta esté dentro del área | No | Sí |
| P-6 | Riesgo alto → preguntar siempre | No | Sí |
| P-7 | Riesgo medio con `path` dentro del área → permitir | No | Sí |
| P-8 | Riesgo medio con `path` fuera del área o sin área → preguntar | No | Sí |
| P-9 | Riesgo medio con `path` ausente, no textual, vacío o nulo → denegar | No | Sí |
| P-10 | Riesgo bajo con `path` dentro del área → permitir; fuera o sin área → preguntar; apagada la regla → preguntar | No | Sí |
| P-11 | Riesgo bajo sin `path` → preguntar; con `path` inválido → denegar | No | Sí |
| P-12 | Registro o área que lanzan, o `contains` que no devuelve `True` exacto → denegar / preguntar según §3 | No | Sí |
| P-13 | Llamada mal formada → denegar | No | Sí |
| P-14 | Determinismo y ausencia de estado (AC-03): misma decisión antes y después de «leer» contenido con instrucciones | No | Sí |
| P-15 | Precedencia denegar > preguntar > permitir sobre todas las combinaciones | No | Sí |
| P-16 | Todo «permitir» pasa por `AuthorizedArea.contains` con la ruta de `path` (devuelto exactamente `True`) y ninguna entrada permite fuera de las condiciones (matriz exhaustiva con comprobador espía y prueba de `ast`) | No | Sí |

## 6. Integración con el bucle de A (sin modificarlo)

| Decisión de la política | Lo que hace el bucle (ya existe) |
|---|---|
| Permitir | Ejecuta con los argumentos exactos que se evaluaron |
| Preguntar | No ejecuta; entrega al modelo `[approval_required_unavailable] …`; publica `PERMISSION_DECIDED` con `ask` resuelta como `deny` |
| Denegar | No ejecuta; entrega `[permission_denied] …`; publica `PERMISSION_DECIDED` con `deny` |
| Excepción de la política | El bucle ya la trata como denegación (`policy_error`); la política real no la deja escapar |

## 7. Comprobaciones de arquitectura asociadas

`tests/architecture/test_permissions_boundaries.py` falla si un módulo de `core/permissions/` importa algo que no sea biblioteca estándar o `harness_agent.core`, lee archivos o entorno, imprime o usa la terminal, importa `harness_agent.config` o `harness_agent.cli`, o si el código de `policy.py` tiene un `PermissionDecision.ALLOW` que no esté en la rama protegida por `AuthorizedArea.contains` o hay un «permitir» sin esa condición.
