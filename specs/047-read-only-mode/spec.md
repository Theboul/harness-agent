# Especificación: HU-05-07 — Modo de solo lectura

**Rama**: `claude/hu-05-07-read-only-20dfd9` · **Responsable**: C — Control y conexiones · **Sprint**: 4 (cierre adelantado al 6-nov-2026) · **PHU**: 1
**Requisitos**: RF-5.9 · **Depende de**: [HU-05-01](../../docs/04c-historias-control.md#hu-05-01) · **Ficha**: [HU-05-07](../../docs/04c-historias-control.md#hu-05-07)
**Reutiliza**: `GitPolicy`/`git_table` (HU-11-02) para decidir qué comandos de git son lecturas; `OpenToolsPolicy` (HU-06-02) como patrón de política envolvente.

## Resumen

La persona activa un modo de solo lectura para explorar un proyecto sin riesgo. En ese modo la política deniega toda herramienta que escribe, todo comando del shell que no sea una lectura entendida y toda herramienta desconocida (incluidas las de MCP). Solo se pueden usar herramientas de lectura (leer, listar, buscar), `preguntar_usuario` y las lecturas de git.

## Clarificaciones

### Sesión 2026-10-31

Sin preguntas al PO: el criterio es explícito y las decisiones de diseño se fijan aquí.

- Q: ¿Cómo se activa? → A: la opción más simple alcanzable desde `harness`: la bandera `--solo-lectura` **o** `[permissions] read_only = true` en `config.toml`. Basta una de las dos; ninguna puede desactivar a la otra (fallar cerrado).
- Q: ¿Qué comandos del shell son «de lectura»? → A: solo los que la tabla de git de HU-11-02 clasifica como lectura (`git status`, `diff`, `log`…), y solo si **todo** el comando son lecturas y se entendió. No se inventa otra tabla: `ls`, `cat`, `pytest`, etc. se **deniegan** en este modo (queda como observación: una futura tabla de lecturas del shell los ampliaría).
- Q: ¿Las lecturas fuera del área? → A: no cambia: la política por defecto las pregunta. El modo solo **restringe**; nunca concede.
- Q: ¿Los comandos declarados por una tarea (`## Comandos`)? → A: se deniegan salvo que sean lecturas de git; el modo prevalece sobre `ExactCallPolicy`.
- Q: ¿Subagentes? → A: la regla de negocio «el modo se aplica también a los subagentes» **no aplica todavía** (no hay subagentes). Observación para HU-09-xx: el subagente debe recibir la misma política envolvente.
- Q: ¿Se puede salir del modo en caliente? → A: no. Se decide al arrancar; reiniciar sin la opción lo desactiva.

## Escenarios

1. **Escritura denegada** (AC-01): `escribir_archivo` en solo lectura → `[permission_denied]`, el archivo no se crea ni se pregunta a la persona.
2. **Comando de escritura denegado** (AC-01): `shell` con `git commit`, `git push`, `rm x`, `echo a > f` → denegado sin preguntar.
3. **Lectura permitida**: `leer_archivo`, `listar_archivos`, `buscar_texto` dentro del área y `shell` con `git status`/`git log` siguen su curso normal.
4. **Herramienta desconocida o MCP**: denegada.
5. **`preguntar_usuario`** sigue disponible.
6. **Comando no entendido** (variables, `eval`, `$( )`, redirección): denegado.
7. **Aviso al arrancar**: línea fija en español «Modo de solo lectura activo…».
8. **`/model`** muestra la línea del modo.
9. **Sin el modo** todo es como antes (la cadena de políticas no se envuelve).

## Requisitos funcionales

- **FR-001**: `ReadOnlyPolicy(inner, read_tools, *, command_tool=None, command_argument=None, is_read_command=None)` en `core/permissions/read_only.py`: si el nombre está en `read_tools` devuelve la decisión de `inner`; si es la herramienta de comandos y `is_read_command(texto)` es `True` devuelve la de `inner`; **todo lo demás es `DENY`**. Nunca devuelve `ALLOW` por sí misma.
- **FR-002**: Falla cerrado: llamada que no es `ToolCall`, argumento ausente o no textual, clasificador que lanza o devuelve algo distinto de `True`, política envuelta que lanza o devuelve algo que no es `PermissionDecision` → `DENY`.
- **FR-003**: La política es genérica: no conoce el shell ni nombres de herramientas; la composición le pasa los nombres y el clasificador.
- **FR-004**: `only_git_reads(command, dialect)` en `core/permissions/git_reads.py` comparte la lógica de `GitPolicy` (sin tabla nueva) y devuelve `True` solo si todas las partes son lecturas de git entendidas.
- **FR-005**: `compose(…, read_only=False)` y `[permissions] read_only` activan el modo; la política queda **fuera y primera** de la cadena. Los nombres permitidos salen de las herramientas de lectura registradas y de `preguntar_usuario`.
- **FR-006**: `main()` acepta `--solo-lectura` (sin valor); repetirla es error; se admite junto a `--tarea`/`--issue`.
- **FR-007**: Aviso fijo al arrancar (`Composition.notices`) y línea en `/model` (`ModelView.read_only`).
- **FR-008**: No cambian `core/interfaces/`, `core/events.py`, `core/loop.py` ni `tests/doubles/`.

## Fuera de alcance

Subagentes; tabla de lecturas del shell más allá de git; conmutar el modo en caliente (`/modo`); el modo `/plan` multi-modelo (usará esta política).

## Criterios de éxito

- **SC-001**: AC-01 pasa con el bucle real y la cadena de políticas real.
- **SC-002**: Cuatro puertas de calidad y `pytest tests/architecture` en exit 0; 100 % de líneas y ramas de `read_only.py`.
- **SC-003**: Diff de archivos protegidos vacío.
