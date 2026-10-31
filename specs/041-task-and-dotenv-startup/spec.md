# Especificación: HU-00-08.1 — Arrancar una tarea desde el comando y leer `.env` (propuesta)

**Estado**: propuesta (área C), pendiente de aprobación del PO. Sigue el precedente de HU-06-05 y HU-00-08. No altera criterios de otras historias: solo hace **alcanzable** desde `harness` lo que ya existe (HU-11-01, 11-03, 11-04.1, 11-05, 11-08.1, 11-08.2, 02-06.1).
**Rama**: `claude/wire-task-and-dotenv-a8b914` · **Fecha**: 2026-10-31

## Problema

El flujo de tickets solo se alcanza con `compose(task=…)` en código; `main()` no carga tareas. Además, la persona tiene que exportar a mano las claves de los proveedores.

## Historias de usuario

- **US1 — Arrancar con una tarea.** `harness --tarea RUTA` lee el archivo, lo valida y arranca la sesión con esa tarea (criterios, verificación, progreso, arranque al reanudar, revisión del diff). `harness --issue N` (o la URL `https://github.com/<dueño>/<repo>/issues/N`) lee el issue con `gh`. Sin argumentos, todo funciona exactamente como hoy.
- **US2 — Claves desde `.env`.** `main()` lee `.env` junto al `config.toml` resuelto y rellena el entorno **solo** para los nombres no definidos.

## Requisitos funcionales

- **FR-001** Argumentos: `--tarea RUTA` | `--issue N|URL` (también `--opcion=valor`). Ambos a la vez, un argumento desconocido, un valor ausente o un issue que no es número ni URL de issue de github.com → «No se pudo iniciar: …» (texto fijo, **sin reproducir el argumento**) y salida 2.
- **FR-002** Archivo ausente, ilegible, no UTF-8, demasiado grande o con formato inválido → «No se pudo iniciar: <mensaje fijo>» y salida 2; nunca se reproduce su contenido ni la ruta. Los mensajes son los de `TaskSourceError`/`TaskFormatError`.
- **FR-003** `--issue` usa `load_github_issue` con `gh` inyectable. Si `gh` no está instalado o falla → mensaje claro en español y salida 2. `gh` se ejecuta sin shell, con argumentos validados (ya así en `run_gh`).
- **FR-004** La tarea se pasa a `compose(task=…)`. Sin argumentos, `compose` recibe `task=None`.
- **FR-005** `.env`: líneas `NOMBRE=valor`; `#` de comentario (línea entera o tras espacio en un valor sin comillas); líneas vacías; comillas simples o dobles opcionales; prefijo `export ` admitido; **sin expansión** de variables ni ejecución. Valores vacíos no se aplican.
- **FR-006** Precedencia: el entorno real manda; el `.env` solo rellena nombres **ausentes**.
- **FR-007** Ubicación: la carpeta del `config.toml` resuelto (parámetro, `HARNESS_CONFIG` o `config.toml` en el directorio actual). Sin `.env` no hay aviso.
- **FR-008** Un `.env` ilegible (permisos, no UTF-8, > 64 KiB) o con líneas no válidas **no tumba el arranque**: aviso fijo por `error` sin el contenido; solo se aplican las líneas válidas.
- **FR-009** Los valores del `.env` nunca se imprimen ni van a eventos, avisos ni errores. No se modifica `os.environ`: el entorno combinado se pasa por parámetro a `load_config` y `compose`.
- **FR-010** `core/` no cambia; puertos, eventos y archivos protegidos sin cambios. Lectura de archivos y entorno solo en adaptadores y por parámetro.
- **FR-011** El comando `harness` y `python -m harness_agent` usan `entry()` (que pasa `sys.argv[1:]`); `main(argv=None)` no lee `sys.argv` (las pruebas existentes no cambian).

## Criterios de éxito

- Prueba de extremo a extremo con `FakeProvider`: `main(argv=["--tarea", …])` verifica criterios y llega a la revisión del diff con entrada simulada.
- Pruebas del cargador con valor centinela que nunca aparece en salida ni errores.
- Cuatro puertas de calidad y `pytest tests/architecture` en exit 0.

## Fuera de alcance

Cambiar de tarea en caliente, `--repo` aparte, escribir `.env`, expandir variables, cargar `.env` de otras carpetas.

## Supuestos pendientes del PO

El nombre de las opciones (`--tarea`, `--issue`); que el `.env` solo se busque junto al `config.toml`.
