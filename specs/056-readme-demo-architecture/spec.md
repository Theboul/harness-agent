# Especificación: HU-00-06 — README, guion de demostración y documento de arquitectura

**Rama**: `gustavo` (sin PR) · **Responsable**: B — Estado · **Sprint**: 3 · **PHU**: 3  
**Requisitos**: RNF-11 · **Depende de**: [HU-00-04](../../docs/04a-historias-fundacion.md#hu-00-04) · **Ficha**: [HU-00-06](../../docs/04a-historias-fundacion.md#hu-00-06)  
**Tareas del plan de sprints**: Sp3-12 (2,5 h, README), Sp3-13 (1,5 h, guion), Sp3-14 (3 h, arquitectura)  
**Modo**: rápido (solo `spec.md`, `plan.md` y `tasks.md`; sin `research`, `data-model`, `contracts`, `quickstart` ni checklists; sin `/speckit-clarify` ni `/speckit-analyze`; las dudas pequeñas se deciden en «Decisiones»).

## Naturaleza de la historia

**Documentación, más una guarda de pruebas pequeña. No se cambia ningún archivo de `src/`.** El código ya hace casi todo lo que el README debería contar, pero el README está desfasado: dice «en desarrollo (Sprint 1)», «aún no hay … punto de entrada ejecutable», «el uso de la CLI se documentará», y nombra una carpeta `observability/` que no existe. Esta historia lo reescribe a partir de lo que el comando `harness` hace **hoy**, añade el guion de la demostración y un documento de arquitectura «tal como está construida», y deja una prueba que impide que esos documentos vuelvan a desfasarse del CLI real.

Esta fase (`/speckit-specify`) solo deja escritos `spec.md`, `plan.md` y `tasks.md`; el README, el guion y los diagramas se escriben en la fase de implementación. Si al implementar apareciera algo que obligue a tocar código protegido, se detiene y se pregunta.

## Criterios de aceptación y reglas de la ficha (literales)

**Descripción.** Una persona ajena al equipo puede instalar y ejecutar el sistema solo con el README y recorrer la demostración de 10 a 15 minutos.

**Flujo general**

1. El equipo redacta el README con instalación, configuración y primeros pasos.
2. Se escribe el guion de demostración.
3. Se documenta la arquitectura con los diagramas del análisis.
4. Una persona ajena sigue el README en una máquina limpia.

**Reglas de negocio**

1. El README no asume pasos que no estén escritos.
2. El guion de Sprint 3 recorre los criterios obligatorios comprometidos hasta Sprint 3; los de MCP y demás historias diferidas tienen guion adicional para Sprint 4 condicionado a PD-01. Ninguna funcionalidad diferida se declara completada.

**Criterios de aceptación**

- **AC-01 — Instalación solo con el README.** Dado una máquina limpia, cuando una persona ajena sigue el README, entonces instala y ejecuta una tarea sin ayuda del equipo.
- **AC-02 — Guion de demostración completo.** Dado el guion de Sprint 3, cuando se sigue, entonces demuestra en 10 a 15 minutos el flujo ticket → pruebas → aprobación → Pull Request y sus controles indispensables, sin afirmar que las historias pospuestas para Sprint 4 estén terminadas.

**Límite de lo que Claude puede cerrar.** AC-01 exige una persona **ajena** en una máquina **limpia**; eso no lo puede hacer quien escribe el README. Lo que sí se hace aquí es un ensayo honesto (T010: entorno virtual nuevo fuera del repo, README seguido al pie de la letra, cada paso que faltaba o falló anotado y corregido) y la prueba `pytest -m install`. El criterio queda **pendiente de la tarea humana H01**; la historia no pasa de `En revisión`.

## Inventario de lo que existe hoy (fuente: código y `docs/PROGRESO.md` del 2026-11-05)

Se verificó contra el código: argumentos de `main()` (`--tarea RUTA`, `--issue NÚMERO|URL`, `--solo-lectura`; `USAGE` en `bootstrap.py`), comandos de la consola (los que registra `run_session` y los que añade `run_cli`), secciones de `config.example.toml`, extras de `pyproject.toml` y los pasos de `.github/workflows/ci.yml`. El inventario se **vuelve a verificar con un script en T002**, porque `PROGRESO.md` cambia a diario.

### Superficie del comando (verificada)

| Elemento | Valor real hoy |
|---|---|
| Comando | `harness` (entrada `harness_agent.bootstrap:entry`) o `python -m harness_agent`; hay que reinstalar con `pip install -e .` si cambió el punto de entrada |
| Opciones | `--solo-lectura`, `--tarea RUTA`, `--issue NÚMERO\|URL` (también `--opción=valor`; `--tarea` e `--issue` a la vez es un error) |
| Comandos `/` | `/ayuda`, `/salir`, `/sesiones`, `/nueva`, `/compactar`, `/plan`, `/implementar`, `/criterios` (solo con tarea), `/reanudar <id>`, `/model [alias]`, `/auditoria [id]`, `/trazas [id]` (**12**). **No existen** `/memoria` ni `/mcp` |
| Secciones de `config.toml` | `[limits]`, `[paths]`, `[permissions]`, `[mcp_servers.<nombre>]`, `[context]` y `[context.windows]`, `[retries]`, `[subagents]`, `[memory]`, `[traces]`, `[models]`, `[failover]`, y el campo `model` |
| Claves | Solo variables de entorno o `.env` junto al `config.toml` (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`; `ollama` no necesita) |
| Extras de instalación | `dev`, `litellm` (`litellm[mcp]` fijado) y `mcp` (`mcp` fijado); el núcleo no tiene dependencias de ejecución |
| Proveedor simulado | `fake/test` **no se puede usar con el comando** (`TEST_ONLY_PROVIDERS`): da «No se pudo iniciar: …» y salida 2. Solo existe para pruebas |

### Las tres categorías

Ninguna historia está `Hecha` (HU-00-01 no está ratificada). Por eso, en todo el contenido nuevo, lo implementado se llama **«En revisión»**, nunca «terminado», «completado» ni «hecho».

**Categoría 1 — Implementado y probado.** Está en `main`, tiene pruebas automáticas en la suite verde, se alcanza desde el comando `harness` y su única reserva es la genérica (revisión cruzada, CI remota, ratificación de HU-00-01). Estado en `PROGRESO.md`: `En revisión`.

| Capacidad | Historias |
|---|---|
| Arranque, configuración, `.env`, instalación limpia | HU-00-04, HU-00-07, HU-00-08, HU-00-08.1 |
| Bucle del agente, registro y herramientas de archivos, bus de eventos | HU-01-01, HU-01-02, HU-01-03, HU-01-05 |
| Sesiones en SQLite, eventos que sobreviven a un corte, reanudar | HU-03-01, HU-03-02, HU-03-04 |
| Contexto: estimación y prefijo, compactación automática, contexto esencial de la tarea, recorte de salidas | HU-02-01, HU-02-02, HU-02-03, HU-02-06.1 |
| Permisos: política, lista de denegados del shell, aprobación y rechazo con motivo, solo lectura, auditoría | HU-05-01, HU-05-02, HU-05-03, HU-05-04, HU-05-05, HU-05-07 |
| Consola: eventos en tiempo real, preguntas con opciones | HU-06-01, HU-06-02 |
| Reintentos del proveedor, trazas, redacción de secretos | HU-07-04, HU-10-01, HU-10-02 |
| Flujo del ticket: tarea y criterios protegidos, progreso del ticket con puntos de control | HU-11-01, HU-11-08.1 |
| Pruebas de fallos del núcleo (proceso matado, proveedor caído, herramienta que lanza, tiempo propio) | HU-00-05.1, HU-00-05.2 |

**Categoría 2 — Implementado «En revisión», con reservas que el guion dice en voz alta.**

| Capacidad | Historias | Reserva anotada en `PROGRESO.md` |
|---|---|---|
| Adaptador LiteLLM y varios proveedores | HU-07-02 | Prueba con modelo real del equipo (Sp1-45) pendiente; lista de proveedores por ratificar |
| Shell y comandos de la tarea | HU-01-04, HU-11-03 | Sin entorno aislado (PD-06): las pruebas ejecutan código editable por el agente (R-21) |
| Reglas de git | HU-11-02 | Tabla de git y supuesto Q3 pendientes del PO |
| Verificación de criterios | HU-11-04.1 | La regla «no avanzar mientras falle» se cumple por instrucción, no por bloqueo |
| Revisión del diff, commit y Pull Request | HU-11-05, HU-11-06 | Una confirmación no se invalida si el agente cambia el código después; el PR necesita `gh`, red y un remoto |
| Rutina de arranque al reanudar un ticket | HU-11-08.2 | Igual que arriba (por instrucción) |
| Cambio de modelo, `/plan`, pulido de uso | HU-06-05, HU-06-06, HU-06-07 | Historias propuestas (ID provisional); el historial entre proveedores no se probó con claves reales |
| Comandos de sesión | HU-02-04, HU-06-04 | Cerradas en papel el 2026-11-04; «tokens liberados» se lee como la pareja «antes → después» |
| MCP por stdio (cliente, herramientas, permisos, servidor caído) | HU-08-01, HU-08-02, HU-08-03, HU-08-04 | Extra `mcp` opcional; sin reconexión de un servidor caído (decisión por ratificar por el PO) |
| Opcionales **apagados por defecto** | HU-09-01, HU-09-03, HU-09-04 (subagentes), HU-07-05 (conmutación), HU-04-01, HU-04-02 (memoria) | Se activan en `config.toml`; subagentes sin perfiles; memoria sin inspección ni edición |
| Datos externos no confiables | HU-05-08 | **Solo AC-02** |
| Contratos y CI | HU-00-01, HU-00-02, SPK-01 | HU-00-01 pendiente de aprobación técnica de A, B y C; HU-00-02 sin evidencia de la protección de rama; SPK-01 `En curso` |

**Categoría 3 — Diferido o no implementado** (el guion lo lista en «Lo que NO se demuestra» y **no** lo afirma):

| Estado | Historias |
|---|---|
| `Pendiente`, Sprint 3 | HU-01-07, HU-01-08, HU-02-06.2, HU-03-05, HU-05-06, HU-06-03, HU-07-03, HU-09-02, HU-09-05, HU-09-06, HU-11-04.2, HU-11-07 |
| `Pendiente`, Sprint 4 | HU-03-03, HU-04-03, HU-04-04, HU-04-05 |
| `Pendiente`, Backlog | HU-02-05, HU-02-07, HU-03-06, HU-07-06, HU-08-05, HU-08-06, HU-09-07, HU-10-03, HU-IN-01 a HU-IN-04 |

### Los siete criterios de demostración del Sprint 3 frente al estado real

| # | Criterio (resumen de `docs/03-plan-sprints.md`) | ¿Se puede demostrar hoy? |
|---|---|---|
| 1 | Flujo completo hasta un Pull Request con enlace visible | **Sí** (HU-11-06, HU-11-05, HU-11-04.1, HU-11-02); necesita `gh`, red y un remoto; plan B: el texto del PR listo para copiar |
| 2 | Un criterio semántico recibe el informe del subagente verificador y queda pendiente hasta que el usuario lo confirma | **Solo la mitad**: el criterio semántico queda pendiente de confirmación humana (`4 N` / `5 N`, HU-11-05). El **informe del subagente verificador no existe** (HU-11-04.2, HU-09-06 y HU-09-02 `Pendiente`) |
| 3 | Punto de control del ticket tras cierre del proceso; al reanudar se leen progreso, log de git y prueba básica | **Sí** (HU-11-08.1, HU-11-08.2, HU-03-04) |
| 4 | Push y PR siempre piden aprobación; cada decisión queda en la auditoría | **Sí** (HU-05-01, HU-05-03, HU-11-06, HU-05-05) |
| 5 | Error elegible del proveedor causa conmutación sin bucle, con evento mínimo y aviso en pantalla | **Sí** con alias de `[models]` y `[failover]` (HU-07-05, HU-06-06); la historia «segundo proveedor por configuración» (HU-07-03) sigue `Pendiente` |
| 6 | Tras tres compactaciones el agente respeta el rechazo con motivo y conoce el objetivo | **Solo el objetivo** (contexto esencial, HU-02-06.1). Las decisiones acumuladas (HU-02-06.2) están `Pendiente`: **no se afirma** que el rechazo sobreviva |
| 7 | Pruebas de fallos del núcleo en CI y redacción de argumentos sensibles antes de persistir | **Sí** (HU-00-05.1, HU-05-05, HU-10-02) |

## Escenarios y entregables

### E1 — README (AC-01) · `README.md`

Se **reestructura, no se duplica**: se conservan las secciones útiles que ya existen (subagentes, varios modelos, conmutación, memoria, auditoría y trazas) y se mueven bajo «Funciones opcionales»; se eliminan o corrigen las afirmaciones obsoletas. Contenido, en este orden:

1. Qué es y estado real (la tabla de las tres categorías, en pocas líneas, con enlace a `docs/PROGRESO.md`).
2. Requisitos y **instalación en una máquina limpia**, en Windows (PowerShell) y en Linux (bash): Python 3.12, entorno virtual, `pip install -e ".[litellm]"` (y `[mcp]` si se quiere MCP), comprobación de que `harness` existe.
3. **Configuración mínima**: copiar `config.example.toml` a `config.toml`, cambiar `model` (el ejemplo trae `fake/test`, que el comando rechaza), definir `[paths] workspace_root`; claves **solo** en variables de entorno o `.env`, con marcadores `<TU_CLAVE>`.
4. **Primer paso con un modelo real**: sin clave (Ollama: instalar, bajar un modelo, `model = "ollama/<modelo>"`) y con clave (Gemini u otro: variable de entorno y `model = "gemini/<modelo>"`).
5. **Cómo arrancar una tarea**: formato del archivo de tarea, `--tarea RUTA`, `--issue NÚMERO|URL` (necesita `gh`), `--solo-lectura`.
6. **Qué hace cada comando `/`** (los 12).
7. **Funciones opcionales** (`[subagents]`, `[failover]`, `[memory]`, `[traces]`, MCP) con su ejemplo de configuración.
8. **Solución de problemas** con los mensajes reales de arranque.
9. **Cómo correr las pruebas** (las cuatro puertas, `pytest -m install`, `pytest tests/architecture`).
10. Documentación (enlaces al guion, a la arquitectura implementada y a `docs/00-indice.md`).

Regla transversal: **cada comando se puede copiar y pegar**, dice en qué shell y carpeta se ejecuta y qué se espera ver. Ningún valor de clave: solo `<TU_CLAVE>` y nombres de variables.

### E2 — Guion de demostración (AC-02) · `docs/guion-demostracion.md`

Flujo **ticket → agente → modificación → pruebas → verificación de criterios → revisión y aprobación del diff → commit → Pull Request**, de 10 a 15 minutos, con los controles indispensables: permisos y aprobación/rechazo con motivo, lista de denegados, solo lectura/`/plan`, compactación, reanudación, auditoría y trazas; conmutación y memoria como tramos opcionales si sobra tiempo. Estructura:

- **Antes de empezar (no cuenta en los 10–15 minutos)**: entorno, configuración, repositorio de demostración (se crea con comandos copiables en un directorio temporal) y una sesión de respaldo ya grabada.
- **Pasos numerados**, cada uno con **tiempo**, **comando exacto**, **salida esperada** y **plan B** (qué decir y qué mostrar si el modelo o la red fallan). La suma de los tiempos de los pasos obligatorios está entre 10 y 15 minutos.
- **Lo que NO se demuestra**: la categoría 3 y las reservas de la categoría 2, incluidos los dos criterios del Sprint 3 que solo se cumplen a medias (verificador subagente y decisiones tras tres compactaciones). Sin afirmar que estén terminadas.
- **Anexo corto de MCP** (unos 3 minutos, aparte de los 10–15): MCP **sí está en `main`** (HU-08-01 a HU-08-04), con el servidor de demostración `tests/spikes/mcp_demo_server.py`; se presenta como «En revisión» con su reserva.

### E3 — Arquitectura implementada · `docs/arquitectura-implementada.md`

Documento nuevo (ver D-01) con diagramas Mermaid **fieles al código**, cada nombre de clase y módulo comprobado con `grep` antes de dibujarlo:

1. Capas hexagonales y reglas de dependencia (`cli`, `core`, `adapters`, `config`, `bootstrap`).
2. Bucle del agente y cadena de permisos (la cadena real de `compose()`).
3. Flujo de una petición: contexto → compactación → bloques esencial y de memoria → proveedor (trazas, conmutación, reintentos) → herramientas → eventos → almacén.
4. Esquema SQLite v7 (tablas y relaciones).
5. Sesiones hijas de los subagentes (`sessions.parent_id`).

Más una tabla «diseñado (`02-arquitectura.md`) frente a construido» para las diferencias conocidas. `docs/02-arquitectura.md` recibe solo un puntero (D-01).

### E4 — Guarda de pruebas de la documentación · `tests/unit/test_docs_match_cli.py`

Una prueba, sin tocar `src/`, sin red ni proveedor, que lee `README.md`, `docs/guion-demostracion.md` y `docs/arquitectura-implementada.md` y comprueba contra el sistema **real**, nunca contra listas copiadas:

- **G1 Comandos.** Cada comando `/` citado (en código en línea o en bloques de código) existe en la salida real de `/ayuda` de una composición con tarea.
- **G2 Opciones.** Cada `--opción` de una línea de comando que empieza por `harness` o `python -m harness_agent` es aceptada por `parse_arguments` (las opciones de `pytest`, `pip`, `git` o `gh` no se miran).
- **G3 Configuración.** Cada `[sección]` de un bloque `toml` citado existe en `config.example.toml` (activa o comentada).
- **G4 Honestidad.** Ninguna línea que cite un ID de historia dice «terminad», «completad» o «hech» (solo «En revisión»); toda línea que cite un ID `Pendiente` de `PROGRESO.md` lleva una marca de diferido («pendiente», «diferid», «no se demuestra», «no existe», «aún no»); ninguna frase obsoleta de la lista de F-01.
- **G5 Guion.** Cada paso del guion tiene tiempo, comando, salida esperada y plan B; la suma de los tiempos obligatorios está entre 10 y 15 minutos; existe la sección «Lo que NO se demuestra».
- **G6 Enlaces.** Los enlaces relativos de los tres documentos apuntan a archivos que existen.

Más autopruebas de los extractores sobre fragmentos sintéticos. **Mutación manual obligatoria**: un comando inventado en el README hace fallar G1 (y de la misma forma una opción inventada, una sección inexistente, un ID `Pendiente` declarado «terminado» y un paso sin plan B).

### E5 — Seguimiento limpio (evidencia para AC-01, sin sustituir a H01) · tarea T010

(a) `pytest -m install --no-cov tests/install` (HU-00-07). (b) En un directorio **nuevo fuera del repo** (carpeta temporal del sistema), crear un entorno virtual limpio y seguir el README **al pie de la letra** hasta ejecutar una tarea con un modelo real local (Ollama está instalado en esta máquina; se comprueba con `ollama list`). El proveedor simulado no sirve para esto (D-03). Cada paso que faltaba o falló se anota, se corrige en el README y se repite hasta que el recorrido pase sin correcciones.

## Requisitos funcionales

- **FR-001** El contenido nuevo se redacta a partir del inventario verificado (código real y `PROGRESO.md`), no de memoria, y distingue las tres categorías con los nombres de arriba.
- **FR-002** El README se reestructura sin duplicar y elimina las afirmaciones obsoletas (F-01).
- **FR-003** El README explica la instalación en una máquina limpia en Windows y en Linux (Python 3.12, entorno virtual, extras).
- **FR-004** El README explica la configuración mínima y que las claves van **solo** en el entorno o en `.env`, con marcadores `<TU_CLAVE>`.
- **FR-005** El README guía un primer paso con un modelo real sin clave (Ollama) y con clave (Gemini u otro).
- **FR-006** El README explica cómo arrancar una tarea con `--tarea` e `--issue`, incluido el formato del archivo de tarea.
- **FR-007** El README explica los 12 comandos `/` y las tres opciones del comando.
- **FR-008** El README explica cómo activar lo opcional (`[subagents]`, `[failover]`, `[memory]`, `[traces]`, MCP).
- **FR-009** El README incluye una sección de solución de problemas con los mensajes reales de arranque.
- **FR-010** El README explica cómo correr las pruebas y la prueba de instalación limpia.
- **FR-011** Cada comando del README y del guion se puede copiar y pegar; no hay pasos implícitos.
- **FR-012** El guion cumple la estructura de E2 (pasos con tiempo, comando, salida esperada y plan B; suma de 10 a 15 minutos; «Lo que NO se demuestra»).
- **FR-013** El guion no afirma como terminada ninguna historia diferida ni `En revisión`; los dos criterios del Sprint 3 que solo se cumplen a medias se dicen como tales.
- **FR-014** El anexo de MCP existe porque MCP está en `main`, y dice su estado y su reserva.
- **FR-015** El documento de arquitectura incluye los cinco diagramas de E3, con nombres comprobados con `grep`.
- **FR-016** La guarda de E4 existe con G1 a G6, autopruebas de los extractores y la mutación obligatoria.
- **FR-017** Ningún documento contiene valores de clave ni URLs con credenciales.
- **FR-018** `docs/PROGRESO.md`: la fila de HU-00-06 pasa de `Pendiente` a `En curso` y, al cerrar, a `En revisión` (nunca `Hecha`); no se reescriben otras filas ni la tabla *Resumen*.
- **FR-019** `src/`, `pyproject.toml`, `.github/` y `tests/doubles/` no cambian.

## Criterios de éxito

- **SC-001** G1 a G3 pasan: el 100 % de los comandos, opciones y secciones de configuración citados existen en el sistema real.
- **SC-002** La suma de los tiempos de los pasos obligatorios del guion está entre 10 y 15 minutos, y el 100 % de los pasos tiene comando, salida esperada y plan B (G5).
- **SC-003** El seguimiento literal del README en un entorno virtual limpio fuera del repo termina ejecutando una tarea; los pasos que fallaron o faltaban quedan listados y corregidos, y la repetición final no necesita correcciones.
- **SC-004** Las seis mutaciones de control (comando, opción, sección, ID `Pendiente` declarado terminado, paso sin plan B, enlace roto) son detectadas por la guarda.
- **SC-005** Las cuatro puertas de calidad, `pytest tests/architecture` (tras `git add -N .`) y la suite completa dan exit 0 sin bajar la cobertura; el diff de `src/` contra `main` está vacío.
- **SC-006** *(humano, H01)* Una persona ajena instala y ejecuta una tarea siguiendo solo el README.

## Decisiones (modo rápido, sin clarify)

- **D-01 Arquitectura en un archivo nuevo.** `docs/02-arquitectura.md` es la fuente de los **contratos** (§4: puertos, eventos, modelo de datos) y lo citan `CLAUDE.md`, las skills y muchas specs por sección; reescribirlo arriesga romper esas referencias y mezclaría lo diseñado con lo construido. Se crea `docs/arquitectura-implementada.md` («tal como está construida»), y `02-arquitectura.md` recibe solo una línea de puntero; `docs/00-indice.md` añade su fila.
- **D-02 Nombre y sitio del guion.** `docs/guion-demostracion.md`.
- **D-03 El proveedor simulado no se promete en el README.** El comando rechaza `fake/…` (`TEST_ONLY_PROVIDERS`). La instalación se comprueba con `pytest -m install` y la ejecución real con Ollama (sin clave) o con una clave en el entorno. Si en T010 no hubiera ningún modelo local, el recorrido se detiene en «arranca y falla cerrado con un mensaje claro» y se anota; la ejecución de una tarea queda para H01.
- **D-04 Sin claves ni URLs con credenciales.** Marcadores `<TU_CLAVE>` y nombres de variables; ningún valor, ni de ejemplo.
- **D-05 Repositorio de demostración.** No se añaden carpetas de ejemplo al repo. El guion trae, en un anexo, los comandos (PowerShell y bash) que crean en un directorio temporal un proyecto Python mínimo con `pytest`, un repositorio git y un archivo de tarea con tres criterios (dos con comando y uno semántico).
- **D-06 La guarda mira solo líneas de comando de `harness`.** Las opciones de otras herramientas no se validan; las rutas absolutas (`/tmp/...`) no son comandos `/` (el comando es una palabra en minúsculas sin segunda barra).
- **D-07 Dónde vive la guarda.** `tests/unit/test_docs_match_cli.py`, con el precedente `tests/unit/test_litellm_quickstart_docs.py`. Los comandos reales salen de ejecutar `/ayuda` con `run_session` sobre una composición de prueba con tarea; las opciones, de `parse_arguments`; las secciones, de `config.example.toml`. No hay listas copiadas.
- **D-08 Vocabulario.** «En revisión» para lo implementado; «Pendiente» o «diferido» para lo demás. Nunca «terminado», «completado» ni «hecho» junto a un ID (G4).
- **D-09 Plan B del guion.** Todo paso que dependa del modelo o de la red lleva (1) una frase para el público, (2) un recurso local: una **sesión de respaldo** grabada antes (`/sesiones`, `/reanudar <id>`, `/auditoria`) y una prueba que reproduce el paso con el proveedor simulado (`pytest <archivo> -q`, sin red).
- **D-10 Pull Request.** El paso del PR necesita `gh` autenticado y un remoto de GitHub. Nada de esta historia hace push ni crea un PR real; el ensayo se hace sin salir del equipo y el PR real queda para H02.
- **D-11 CLAUDE.md.** Se añaden a «Fuentes de verdad» los tres documentos nuevos y una frase sobre la guarda; las skills no cambian (la estructura de carpetas no cambia).
- **D-12 `.env.example` y `config.example.toml`.** El encabezado de `.env.example` dice que HARNESS no lee un archivo `.env`, y desde HU-00-08.1 sí lo lee (F-02). Se corrige el comentario en T005 si la edición está permitida; si no, queda como hallazgo y el README dice lo cierto. **Resultado al implementar:** no se pudo, porque la prueba existente `tests/unit/test_config_templates.py::TestEnvExample::test_it_explains_how_to_load_the_variables_and_that_dotenv_is_not_read` exige el texto «no lee» y la historia no cambia pruebas existentes; queda como hallazgo F-02. El `model = "fake/test"` de `config.example.toml` no se cambia (lo cargan pruebas de plantillas): el README manda cambiarlo (F-03).
- **D-13 Tiempos.** Los 10–15 minutos son los del tramo demostrativo; la preparación se hace antes. Los tramos opcionales (conmutación, memoria) no cuentan en la suma obligatoria.

## Hallazgos (propuestas para decidir; NO se arreglan aquí salvo lo indicado)

- **F-01 README obsoleto.** «Estado: en desarrollo (Sprint 1) … aún no hay adaptador de proveedor real, SQLite, raíz de composición ni punto de entrada ejecutable»; «El uso de la CLI se documentará cuando exista un punto de entrada ejecutable»; la fila `src/harness_agent/observability/` (esa carpeta no existe: la auditoría, las trazas y la redacción están en `core/`). Se corrigen aquí; la guarda G4 lleva esas frases como prohibidas.
- **F-02 `.env.example`** con el comentario «HARNESS no lee un archivo .env» (ver D-12).
- **F-03 `model = "fake/test"`** es el modelo activo de `config.example.toml` y el comando lo rechaza: copiar la plantilla tal cual falla al arrancar. Propuesta para B/C: que la plantilla traiga `ollama/...` comentado y `fake/test` solo en las pruebas.
- **F-04 Dos criterios de demostración del Sprint 3 no se pueden cumplir** (verificador subagente y decisiones tras tres compactaciones): se dicen en «Lo que NO se demuestra». Decisión del PO: reprogramar o aceptar la demostración parcial.
- **F-05 Estado cambiante.** Hoy es el penúltimo día del Sprint 3; las historias `Pendiente` pueden pasar a `En revisión` antes de la demostración. T002 y T013 vuelven a calcular el inventario.

## Alcance excluido

Cambiar `src/`, `pyproject.toml`, `ci.yml` o `tests/doubles/`; implementar historias pendientes; hacer push o crear un Pull Request real; la prueba con una persona ajena (H01); un vídeo o capturas; traducir; documentación de API generada.

## Supuestos

- Las cifras y estados salen de `PROGRESO.md` del 2026-11-05 y se recalculan al cerrar.
- Ollama está instalado en la máquina del equipo que ensaya (`ollama` en el `PATH`); si no hay ningún modelo bajado, T010 lo documenta y no inventa uno.
- La persona ajena de H01 tiene Python 3.12 y acceso a red para `pip`.
- El archivo de tarea (`## Objetivo`, `## Criterios de aceptación`, `## Comandos` opcional) es el formato de HU-11-01 y HU-11-03; T005 lo toma de `core/tasks/` sin cambiarlo.
