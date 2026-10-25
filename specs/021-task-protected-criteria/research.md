# Research: HU-11-01

Decisiones técnicas. Cada una: decisión, motivo, alternativas.

## R1. Formato de la tarea
**Decisión**: Markdown con secciones `# Título`, `## Objetivo`, `## Contexto`, `## Reglas`, `## Criterios de aceptación` (alias `## Criterios`); criterios como elementos de lista con sublista `comando:` / `espera:`. Contrato en `contracts/task_format.md`.
**Motivo**: es lo que ya escribe una persona en un issue de GitHub; un analizador sirve a archivo e issue; solo stdlib.
**Alternativas**: TOML/JSON (incómodo para texto largo y para un issue); YAML (dependencia).

## R2. Condición esperada
**Decisión**: texto libre no vacío (≤ 500 caracteres). La gramática (`codigo_salida == 0`) la fija HU-11-04.1.
**Alternativa**: gramática ya aquí: adelanta trabajo de otra historia.

## R3. Alta atómica
**Decisión**: `SqliteTaskStore.start_task` abre `BEGIN IMMEDIATE`, inserta sesión, criterios y sello, escribe la copia (archivo temporal + reemplazo) y hace `COMMIT`. Fallo previo al commit → `ROLLBACK` y se borra el archivo creado; fallo del commit → se borra el archivo.
**Motivo**: AC-01/SC-001 («o queda todo o no queda nada»).
**Alternativas**: dos pasos con compensación (ventanas de inconsistencia).

## R4. Sello y huella
**Decisión**: `canonical_export(session_id, rows) -> bytes` (JSON con claves ordenadas, `indent=2`, UTF-8, salto final). Su SHA-256 es (a) la huella que se compara con el archivo y (b) el sello guardado en `criterios_sello` por sesión, actualizado en cada `mark_passes`. `load_criteria` recalcula y compara; si no coincide, o una fila viola las reglas (tipo/comando/condición/passes sin evidencia), lanza `CriteriaIntegrityError` y publica `criteria_tampered`.
**Motivo**: regla 4 («cualquier indicio de alteración») con una sola función; detecta ediciones ingenuas de la base.
**Límite honesto**: sin clave secreta; quien pueda reescribir base y sello a la vez no es detectado (PD-06 / HU-IN-02).
**Alternativas**: HMAC con clave (gestión de secretos fuera de alcance); triggers de SQLite (se pueden borrar igual).

## R5. Restauración de la copia
**Decisión**: si el archivo no existe, no es un archivo regular o su SHA-256 difiere, se elimina lo que haya (archivo, enlace o carpeta vacía o no, solo en la ruta exacta de la copia), se escribe de nuevo (temporal + `os.replace`) y se marca de solo lectura (`chmod 0o444`; en Windows activa el atributo de solo lectura). Antes de reemplazar un archivo de solo lectura se le quita la marca.
**Motivo**: en Windows `os.replace` sobre un archivo de solo lectura falla.

## R6. Protección de archivos y shell
**Decisión**: `ProtectedPolicy(inner, area, shell_markers)` decide primero: `path` (cadena) con `area.contains(path)` verdadero → DENY, para cualquier herramienta; herramienta `shell` con `command` que contenga un marcador (minúsculas, `\` → `/`) → DENY; cualquier excepción → DENY; si no, delega. `ProtectedPaths` (adaptador) implementa `AuthorizedArea` sobre rutas reales: archivos (base y sus `-wal`, `-shm`, `-journal`) y carpetas (la carpeta del harness; si contiene al área de trabajo, solo `tareas/`).
**Motivo**: reutiliza el puerto `AuthorizedArea`; no cambia `DefaultPermissionPolicy` (HU-05-01, de C).
**Limitación (regla 6)**: no se interpretan comandos compuestos, variables, comodines ni ofuscación; es de HU-05-02. Un shell con los mismos privilegios puede esquivar la protección; AC-03 no afirma lo contrario.
**Alternativas**: modificar `DefaultPermissionPolicy` (archivo de C, acoplamiento); lista `deny` por nombre de herramienta (no mira rutas).

## R7. Fuente GitHub
**Decisión**: `fetch_issue_task(number, runner)`; `runner(args: Sequence[str]) -> str` por defecto ejecuta `subprocess.run(["gh", *args], shell=False, timeout=30, capture_output=True)`; el número debe ser entero positivo (`bool` no vale). Salida JSON con `title` y `body`; el título completa el de la tarea si el cuerpo no trae `# `.
**Motivo**: sin shell (sin inyección), inyectable (sin red en pruebas).

## R8. Sesión
**Decisión**: `sessions.goal` = objetivo de la tarea; `model` = el de la configuración. Reglas y contexto no se persisten aquí (HU-02-06.1).

## R9. Migración
**Decisión**: `ensure_schema` aplica `v1 → v2` dentro de una transacción (`CREATE TABLE criterios …`, `criterios_sello`, `PRAGMA user_version = 2`); una versión distinta de 1 y 2 se rechaza como hoy.

## R10. Identificadores de criterio
**Decisión**: `criterios.id` entero autoincremental; el puerto lo ve como `str(id)`; el JSON exporta el mismo valor. `mark_passes` con un id no numérico o inexistente → `CriteriaNotFound`.
