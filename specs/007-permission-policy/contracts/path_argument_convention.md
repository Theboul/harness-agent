# Convención: el argumento de ruta de las herramientas de archivos se llama `path`

**Spec**: [../spec.md](../spec.md) (FR-007, FR-008, FR-011, FR-012) · **Decisión**: Q2, opción A (2026-10-21) · **La cumple**: HU-01-03 (herramientas de archivos, Sprint 1)

La política de permisos (HU-05-01) decide sobre una llamada mirando solo su nombre y sus argumentos. Para saber **dónde** va a leer o escribir una herramienta necesita una convención común, porque el puerto de herramienta (`Tool`) no declara qué argumento es una ruta y **no se modifica**.

## 1. La convención

| Regla | Texto |
|---|---|
| C-1 | La ruta sobre la que actúa una herramienta de archivos va en un único argumento llamado `path`. |
| C-2 | El valor de `path` es texto no vacío (una ruta absoluta o relativa al área de trabajo). |
| C-3 | La contención en el área autorizada la decide `AuthorizedArea.contains(path)` sobre la **ruta real** (resuelve `..`, enlaces simbólicos, unidades y rutas UNC); la política no resuelve rutas por su cuenta. |
| C-4 | El nivel de riesgo lo declara cada herramienta: **medio** si escribe o modifica archivos, **bajo** si solo lee, lista o busca, **alto** si ejecuta código o usa la red. |
| C-5 | Una herramienta que necesite más de una ruta (copiar, mover) o que no pueda usar `path` no cumple esta convención: hasta que se defina otra, se declara de riesgo alto (siempre se pregunta). |

## 2. Qué decide la política con esa convención

| Herramienta | Llamada | Decisión |
|---|---|---|
| Riesgo medio | `path` ausente, no textual, vacío o inválido, o el comprobador del área falla | Denegar (llamada mal formada) |
| Riesgo medio | `path` con ruta real dentro del área | Permitir (regla de escritura, AC-04) |
| Riesgo medio | `path` con ruta real fuera del área, o sin área configurada | Preguntar |
| Riesgo bajo | incluye `path` no textual, vacío o inválido, o el comprobador falla | Denegar (llamada mal formada) |
| Riesgo bajo | incluye `path` con ruta real dentro del área | Permitir (regla de lectura, **supuesto pendiente de confirmación del PO**) |
| Riesgo bajo | incluye `path` fuera del área, o sin área configurada | Preguntar |
| Riesgo bajo | no incluye `path` | Preguntar (ninguna regla coincide, AC-01) |
| Riesgo alto, no registrada o sin riesgo declarado | cualquiera | Preguntar |

Las reglas de denegar y de preguntar de la configuración (`[permissions]`) tienen prioridad sobre las dos de permitir (AC-02).

## 3. Qué debe hacer HU-01-03

1. Llamar `path` al argumento de ruta de `leer`, `escribir`, `listar` y `buscar` (en `buscar`, la carpeta o el archivo donde se busca) y declararlo en el esquema como texto.
2. Declarar el riesgo: `escribir` medio; `leer`, `listar` y `buscar` bajo.
3. No leer ni escribir fuera de lo que la política evaluó: la herramienta calcula la ruta real con el mismo componente de área y comprueba otra vez la contención antes de actuar (defensa en profundidad; la política no sustituye esa comprobación).
4. No añadir otros argumentos que sean rutas sin pasar por esta convención.

## 4. Qué NO cambia

El puerto `Tool`, el bucle y los demás puertos. La convención es un contrato entre HU-01-03 y HU-05-01; si más adelante se prefiere un metadato en el puerto de herramienta, es un cambio de puerto que exige el acuerdo de A, B y C.
