# Feature Specification: HU-01-03 — Herramientas de archivos: leer, escribir, listar y buscar

**Feature Branch**: `feat/hu-01-03-file-tools` (el directorio de la spec es `013-file-tools`; el nombre del directorio no dicta la rama)

**Created**: 2026-10-23

**Status**: En revisión (ver docs/PROGRESO.md)

**Proyecto**: HARNESS v2.5 | **Sprint**: 1 | **Responsable**: C — Control y conexiones | **Tareas de referencia**: Sp1-18, Sp1-19, Sp1-20, Sp1-21, Sp1-22 | **Requisitos**: RF-1.2 | **Depende de**: HU-01-02 (registro de herramientas, ya integrada) y, para la decisión de permisos, HU-05-01 (política, ya integrada)

**Input**: User description: "HU-01-03 — Herramientas de archivos: leer, escribir, listar y buscar (docs/04a-historias-fundacion.md#hu-01-03). Decisiones del responsable: cuatro herramientas nativas con nombres en español (`leer_archivo`, `escribir_archivo`, `listar_archivos`, `buscar_texto`); `editar_archivo` queda fuera. Rama `feat/hu-01-03-file-tools`; commits sin coautor y en el estilo del proyecto."

## Clarifications

### Session 2026-10-23

Decisiones del responsable y propuestas por defecto. Las marcadas **(por confirmar)** son la recomendación del análisis previo y no tienen respuesta explícita todavía; se aplican mientras tanto y se registran en `PROGRESO.md`.

- Q: ¿Qué herramientas entran? → A: Las cuatro de la historia: `leer_archivo`, `escribir_archivo`, `listar_archivos` y `buscar_texto`. `editar_archivo` (que `docs/02-arquitectura.md` asigna a esta historia) queda fuera: no figura en el título, los criterios de aceptación ni las tareas Sp1-18 a Sp1-22.
- Q: ¿Qué nombres ve el modelo? → A: Los de arriba, en español (coinciden con `docs/02-arquitectura.md`, la constitución y la guía). Las clases y los identificadores van en inglés (`ReadFileTool`, `WriteFileTool`, `ListFilesTool`, `SearchTextTool`, `WorkspaceArea`).
- Q: ¿Dónde viven? → A: Las herramientas en `src/harness_agent/adapters/tools/` y el área real en `src/harness_agent/adapters/system/` (la propuesta de `arbol.md` queda confirmada). El puerto `AuthorizedArea` y el puerto `Tool` no cambian.
- Q: ¿Cómo sabe la política dónde actúa una herramienta? → A: Por la convención `path` de HU-05-01 (`specs/007-permission-policy/contracts/path_argument_convention.md`): un único argumento `path`, texto no vacío; riesgo medio para escribir y bajo para leer, listar y buscar.
- Q: ¿Qué recibe el modelo cuando una escritura queda fuera del área? → A: **(por confirmar)** El texto genérico que el bucle de A ya redacta para una acción que se pregunta y no se puede aprobar (HU-05-01, Q3 = A). La causa específica llega con la interfaz de aprobación (HU-05-03). La herramienta, además, rechaza por sí misma toda ruta cuya ruta real salga del área, con un motivo claro, si llegara a ejecutarse.
- Q: ¿Qué significa «sin área configurada» (AC-04)? → A: **(por confirmar)** Que `workspace_root` es `None`: no hay área, ninguna herramienta actúa y la política pregunta, que en el Sprint 1 equivale a denegar. «La carpeta de la sesión» de la redacción no existe aún (llega con HU-03-01) y no se implementa.
- Q: ¿Cuándo se lee dentro del área? → A: La política permite leer con una herramienta de riesgo bajo que trae `path` dentro del área; es un supuesto de HU-05-01 pendiente de confirmación del PO y se apaga con `allow_reads_in_area=False`. Las pruebas de integración cubren las dos configuraciones.
- Q: ¿Qué semántica tienen las herramientas (los criterios de aceptación no la fijan)? → A: Texto UTF-8; límites fijos y documentados; resultados acotados; búsqueda de texto literal sensible a mayúsculas; listado no recursivo. Detalle en los requisitos y en `research.md`.
- Q: ¿Cómo se prueban los casos de Windows? → A: Con una clasificación de rutas pura e inyectable (`windows=True` en pruebas sintéticas que corren en Linux y en Windows) y con pruebas reales marcadas por plataforma que corren en `windows-latest`.

## User Scenarios & Testing *(mandatory)*

### Criterios de aceptación, reglas de negocio y prototipo de la historia (inmutables)

Copiados tal cual de `docs/04a-historias-fundacion.md` (HU-01-03). No se reescriben ni se amplían (Principio V de la constitución); los escenarios de abajo los desarrollan sin sustituirlos.

**Flujo general**

1. El modelo solicita una herramienta de archivos.
2. La herramienta calcula la ruta real (normaliza, sigue enlaces simbólicos y comprueba unidad y ruta UNC en Windows).
3. La política de permisos evalúa la llamada con esa ruta real.
4. Si está dentro del área autorizada se ejecuta; si no, se pregunta o se deniega.
5. El resultado o un error claro vuelve al modelo.

**Reglas de negocio**

1. Las lecturas se clasifican como bajo riesgo; las escrituras solo se permiten dentro del área autorizada.
2. La contención se comprueba sobre la ruta real, nunca sobre el texto de la ruta recibida.
3. No existe una autorización global para escribir en cualquier ubicación.
4. Una ruta inexistente devuelve un error claro, no una excepción.

**Prototipo**

```
Área autorizada: ~/proyecto-demo
  escribir ~/proyecto-demo/notas.txt          permitido
  escribir ~/proyecto-demo/../.bashrc          rechazado: sale del área
  escribir /etc/hosts                          rechazado: fuera del área
  escribir enlace-a-/tmp/x (enlace simbólico)  rechazado: la ruta real sale del área
```

**Criterios de aceptación**

- **AC-01 — Lectura y error de ruta inexistente.** Dado una ruta existente dentro del área de trabajo, cuando el agente la lee, entonces recibe su contenido; si no existe, recibe un error claro.
- **AC-02 — Escritura dentro del área autorizada.** Dado una escritura cuya ruta real queda dentro del área de trabajo autorizada, cuando la política la evalúa, entonces se permite y la decisión queda registrada; dado una escritura fuera del área, entonces es una acción que requiere permiso.
- **AC-03 — Intentos de escapar del área.** Dado una ruta con «..», una ruta absoluta, un enlace simbólico o, en Windows, otra unidad, una ruta UNC o un flujo alterno, cuando se resuelve, entonces se calcula la ruta real y, si el destino queda fuera del área, se rechaza antes de escribir y el modelo recibe el motivo.
- **AC-04 — Sin área configurada.** Dado que no hay un área de trabajo configurada, cuando el agente intenta escribir, entonces toda escritura requiere permiso: no existe un área por defecto fuera de la carpeta de la sesión.

### Lo que ya existe y lo que cambia

- **Existe y no se toca**: el bucle de A (`core/loop.py`), el puerto `Tool` y el registro (HU-01-02), el puerto `AuthorizedArea` y la política de permisos (HU-05-01, que ya llama a `AuthorizedArea.contains(path)` con el `path` de la llamada sin modificar), el bus, la CLI, la configuración (`HarnessConfig.paths.workspace_root`, `None` si no se configura) y todos los dobles de `tests/doubles/`.
- **Se añade**: `adapters/system/` con el área real (`WorkspaceArea`), `adapters/tools/` con las cuatro herramientas, sus pruebas (unitarias, de contrato, de integración y de arquitectura) y una sección de la guía.
- **No se añade**: la conexión de las piezas en `bootstrap.py` (no existe todavía); las pruebas de integración hacen esa composición y el plan anota qué deberá conectar `bootstrap.py`.

### User Story 1 - Leer, listar y buscar dentro del área (Priority: P1) [AC-01]

Como usuario operador, quiero que el agente lea archivos, liste carpetas y busque texto dentro del área de trabajo, y que una ruta que no existe devuelva un error claro, para que trabaje sobre mi proyecto sin excepciones ni resultados confusos.

**Why this priority**: Es el criterio AC-01 y lo que hace útil al agente en el Sprint 1 (el objetivo del sprint lee, escribe y relee un archivo). Las lecturas son de riesgo bajo y la política ya las permite dentro del área.

**Independent Test**: Con un área real sobre una carpeta temporal con archivos de texto, se llama a cada herramienta: `leer_archivo` devuelve el contenido, `listar_archivos` las entradas, `buscar_texto` las coincidencias con ruta y línea, y una ruta inexistente devuelve un resultado de error con causa y sugerencia, sin lanzar excepciones.

**Acceptance Scenarios**:

1. **Given** un archivo de texto dentro del área, **When** el agente llama a `leer_archivo` con su ruta (relativa o absoluta), **Then** recibe su contenido completo.
2. **Given** una ruta que no existe, **When** el agente la lee, la lista o la busca, **Then** recibe un resultado de error que dice qué ruta no existe y qué hacer (por ejemplo, usar `listar_archivos`), no una excepción.
3. **Given** una carpeta dentro del área, **When** el agente llama a `listar_archivos`, **Then** recibe sus entradas ordenadas, distinguiendo archivos y carpetas, y se indica si la lista se recortó.
4. **Given** texto que aparece en varios archivos del área, **When** el agente llama a `buscar_texto` con una carpeta y un texto, **Then** recibe las coincidencias con archivo (relativo al área), número de línea y la línea, en un orden estable y acotado.
5. **Given** un archivo demasiado grande, binario o que no es UTF-8, **When** el agente lo lee, **Then** recibe un error claro (tamaño máximo, «no parece texto» o «no es UTF-8») y no se carga en memoria sin límite.
6. **Given** una ruta que es una carpeta, **When** se llama a `leer_archivo`, o un archivo cuando se llama a `listar_archivos`, **Then** recibe un error claro que indica la herramienta adecuada.

---

### User Story 2 - Escribir solo dentro del área autorizada (Priority: P1) [AC-02]

Como usuario operador, quiero que el agente cree o reemplace archivos solo dentro del área autorizada y que la decisión quede registrada, para que no pueda escribir en otra parte de mi equipo.

**Why this priority**: Es el criterio AC-02 y la regla de negocio 1 y 3. Es la barrera de seguridad central de la historia.

**Independent Test**: Con el bucle real, la política real y un área real, una escritura con ruta real dentro del área se ejecuta y se publica la decisión «permitir»; una escritura fuera del área se pregunta, se resuelve como denegada (en el Sprint 1 no hay aprobador) y el archivo no se crea.

**Acceptance Scenarios**:

1. **Given** una ruta cuya ruta real queda dentro del área, **When** la política evalúa `escribir_archivo`, **Then** se permite, el archivo se crea o se reemplaza con el contenido recibido y la decisión queda publicada como evento de decisión de permiso.
2. **Given** una ruta fuera del área, **When** la política la evalúa, **Then** es una acción que requiere permiso (se pregunta) y, sin aprobador, se resuelve como denegada y no se escribe nada.
3. **Given** una escritura permitida cuya carpeta padre no existe, **When** se ejecuta, **Then** se crean las carpetas intermedias, siempre dentro del área, y se escribe el archivo.
4. **Given** una ruta que es una carpeta existente, **When** se escribe, **Then** se devuelve un error claro y no se cambia nada.
5. **Given** un contenido que supera el máximo documentado, **When** se escribe, **Then** se rechaza con un error claro antes de tocar el disco.
6. **Given** que escribir no puede completarse (permisos del sistema, disco), **When** ocurre, **Then** el modelo recibe un error claro y no una excepción ni una traza.

---

### User Story 3 - Los intentos de escapar del área se rechazan antes de escribir (Priority: P1) [AC-03]

Como usuario operador, quiero que una ruta con «..», una ruta absoluta, un enlace simbólico o, en Windows, otra unidad, una ruta UNC o un flujo alterno no pueda sacar al agente del área, para que ninguna triquiñuela de rutas escriba fuera.

**Why this priority**: Es el criterio AC-03 y la regla de negocio 2: la contención se decide sobre la ruta real, no sobre el texto.

**Independent Test**: Una batería de rutas hostiles contra un área real: ninguna llega a escribir fuera, los archivos de fuera quedan intactos, y el modelo recibe el motivo.

**Acceptance Scenarios**:

1. **Given** una ruta con «..» que sale del área, **When** se evalúa o se ejecuta, **Then** se rechaza: la ruta real queda fuera.
2. **Given** una ruta absoluta fuera del área, **When** se evalúa o se ejecuta, **Then** se rechaza.
3. **Given** un enlace simbólico dentro del área que apunta fuera (a un archivo o a una carpeta), **When** se escribe a través de él, **Then** se rechaza antes de escribir y el destino externo no cambia.
4. **Given** una ruta que parece estar dentro del área por su texto pero cuya ruta real sale (por ejemplo `carpeta-enlace/../x`), **When** se evalúa, **Then** manda la ruta real.
5. **Given** Windows, **When** la ruta usa otra unidad, una ruta UNC (`\\servidor\recurso`, `\\?\`) o un flujo alterno (`archivo.txt:flujo`), **Then** se rechaza antes de escribir. Lo mismo para nombres de dispositivo reservados y segmentos con punto o espacio final.
6. **Given** una ruta con un carácter nulo o que no se puede resolver, **When** se evalúa, **Then** se trata como fuera del área (falla cerrada), nunca como dentro.
7. **Given** cualquier rechazo, **When** el modelo recibe el resultado, **Then** el motivo no revela rutas reales de fuera del área ni el contenido de archivos externos.

---

### User Story 4 - Sin área configurada, nada se escribe (Priority: P2) [AC-04]

Como usuario operador, quiero que sin un área de trabajo configurada toda escritura requiera permiso, para que no exista una autorización implícita.

**Why this priority**: Es el criterio AC-04 y la regla 3. P2 porque la política ya falla cerrada; aquí se demuestra con las herramientas reales de extremo a extremo.

**Independent Test**: Con `workspace_root` ausente, el bucle real con las cuatro herramientas y la política sin área: cada llamada se pregunta, se deniega sin aprobador, y ningún archivo se toca.

**Acceptance Scenarios**:

1. **Given** que no hay área configurada, **When** el agente intenta escribir, **Then** la política pregunta y, sin aprobador, se deniega; no se escribe nada.
2. **Given** que no hay área configurada, **When** una herramienta llegara a ejecutarse, **Then** devuelve un error claro («no hay un área de trabajo configurada») y no actúa.
3. **Given** que no hay área configurada, **When** el agente lee, lista o busca, **Then** tampoco se ejecuta (la política pregunta cuando no hay área): no existe un área por defecto.
4. **Given** una configuración con `workspace_root`, **When** se construye el área, **Then** su raíz es la ruta real de esa carpeta; si no existe o no es una carpeta, se rechaza al construir.

---

### User Story 5 - Cada herramienta declara su riesgo y su ruta (Priority: P2)

Como equipo de desarrollo, quiero que cada herramienta declare su nivel de riesgo y use el argumento `path`, para que la política pueda clasificarlas sin conocer sus detalles.

**Why this priority**: Es la tarea Sp1-21 y el contrato con HU-05-01; sin él la política pregunta o deniega todo.

**Independent Test**: Se registran las cuatro herramientas en el registro real (que valida sus esquemas) y se comprueban riesgo, nombre, esquema y la decisión de la política real para cada una.

**Acceptance Scenarios**:

1. **Given** las cuatro herramientas, **When** se registran en `InMemoryToolRegistry`, **Then** todas pasan la validación de esquema, con nombres únicos.
2. **Given** `escribir_archivo`, **When** se consulta su riesgo, **Then** es medio; `leer_archivo`, `listar_archivos` y `buscar_texto` son bajo.
3. **Given** cada esquema, **When** se inspecciona, **Then** declara `path` como texto no vacío y no admite otros argumentos de ruta (`additionalProperties` falso).
4. **Given** una llamada sin `path` o con `path` no textual, **When** la política la evalúa, **Then** se deniega como llamada mal formada.

---

### Edge Cases

- **Ruta relativa**: se resuelve contra la raíz del área, no contra el directorio de trabajo del proceso.
- **La raíz del área**: cuenta como dentro del área (se puede listar y buscar en ella).
- **Mayúsculas y minúsculas**: en Windows la comparación ignora mayúsculas; en Linux las respeta.
- **Enlace simbólico roto o circular**: no lanza excepción; se resuelve sin exigir que exista y, si su destino sale del área o no se puede resolver, se rechaza.
- **Carrera entre la comprobación y el uso**: la herramienta vuelve a resolver y a comprobar justo antes de actuar (defensa en profundidad); queda una ventana mínima que la historia documenta y no pretende cerrar.
- **Archivo con nombre «extraño»**: nombres con espacios, acentos o `:` en Linux son válidos; solo en Windows el `:` fuera de la unidad es un flujo alterno y se rechaza.
- **Búsqueda sobre archivos grandes, binarios o fuera del área por enlace**: se omiten sin error; un enlace que salga del área no se sigue.
- **Resultado muy largo**: se recorta con un aviso; nunca se devuelve sin límite.
- **Contenido leído**: es dato, no instrucción; el bucle lo marca como externo.
- **El bucle y los eventos**: las cargas de los eventos no llevan argumentos ni contenido de archivos (FR-029 de HU-01-01); esta historia no cambia eso.
- **Argumentos con campos extra**: los rechaza el registro por el esquema antes de llegar a la herramienta.

## Requirements *(mandatory)*

### Functional Requirements

**Área autorizada real (Sp1-19)**

- **FR-001**: `WorkspaceArea` MUST implementar el puerto `AuthorizedArea` sin cambiarlo: `root` es la ruta real y absoluta de una carpeta existente; construirla con una ruta que no existe o no es carpeta MUST fallar con un error claro.
- **FR-002**: `contains(path)` MUST resolver la ruta recibida (texto o `Path`), relativa a `root` si no es absoluta, normalizando «..», siguiendo enlaces simbólicos y comparando la ruta real, y MUST devolver `True` solo si queda dentro de `root` (la propia raíz incluida).
- **FR-003**: `contains` MUST fallar cerrado: devuelve `False` ante un tipo inesperado, un carácter nulo, un error del sistema al resolver o cualquier excepción, y MUST NOT lanzar.
- **FR-004**: En Windows, `contains` MUST devolver `False` para rutas UNC y de dispositivo (`\\servidor\recurso`, `\\?\`, `\\.\`), para otra unidad que no sea la del área, para flujos alternos de datos (`:` fuera de la unidad), para nombres de dispositivo reservados (CON, PRN, AUX, NUL, COM1–9, LPT1–9, con o sin extensión) y para segmentos que terminan en punto o espacio, y MUST comparar sin distinguir mayúsculas.
- **FR-005**: La clasificación de rutas de Windows MUST poder ejercitarse en cualquier sistema mediante un parámetro inyectable, de modo que su prueba corra en Linux y en Windows; las pruebas con el disco real de Windows MUST quedar marcadas por plataforma.

**Herramientas (Sp1-18, Sp1-20, Sp1-21)**

- **FR-006**: MUST existir `leer_archivo`, `escribir_archivo`, `listar_archivos` y `buscar_texto`, cada una implementando el puerto `Tool` sin cambiarlo, con nombre único, descripción para el modelo y esquema que pasa la validación del registro.
- **FR-007**: Todas MUST usar `path` como único argumento de ruta, declarado como texto no vacío; `additionalProperties` MUST ser falso; `escribir_archivo` añade `content` (texto) y `buscar_texto` añade `query` (texto no vacío, con longitud máxima).
- **FR-008**: `escribir_archivo` MUST declarar riesgo medio; `leer_archivo`, `listar_archivos` y `buscar_texto`, riesgo bajo.
- **FR-009**: Antes de actuar, cada herramienta MUST calcular la ruta real y comprobar `AuthorizedArea.contains(<ruta real>)`; si es falso MUST devolver un resultado de error con el motivo y MUST NOT leer ni escribir. Esta comprobación es independiente de la de la política (defensa en profundidad).
- **FR-010**: Las herramientas MUST NOT lanzar por rutas inexistentes, permisos u otros errores del sistema: MUST devolver un `ToolResult` con `is_error=True` y un mensaje en español con causa y sugerencia, sin trazas ni rutas reales fuera del área.
- **FR-011**: `leer_archivo` MUST devolver el texto UTF-8 del archivo con un tamaño máximo documentado; MUST rechazar con error claro los archivos binarios, que no son UTF-8, demasiado grandes y las carpetas.
- **FR-012**: `escribir_archivo` MUST crear o reemplazar el archivo con el contenido recibido en UTF-8, crear las carpetas intermedias que falten dentro del área, rechazar una carpeta existente como destino y un contenido mayor que el máximo documentado, y MUST NOT tocar el disco si la comprobación de contención falla.
- **FR-013**: `listar_archivos` MUST listar las entradas de una carpeta (no recursivo), ordenadas, distinguiendo archivos y carpetas, con un máximo de entradas documentado y un aviso si se recortó.
- **FR-014**: `buscar_texto` MUST buscar el texto literal (sensible a mayúsculas) en un archivo o, de forma recursiva, en una carpeta; devolver archivo relativo al área, número de línea y la línea (acotada), en orden estable, con un máximo de coincidencias; omitir archivos binarios, demasiado grandes o cuyo enlace salga del área; y MUST NOT seguir enlaces simbólicos de carpetas fuera del área.
- **FR-015**: Sin área (`area=None`), cada herramienta MUST devolver un error claro («no hay un área de trabajo configurada») y MUST NOT actuar.
- **FR-016**: Las herramientas MUST NOT leer configuración, entorno ni la terminal: reciben el área por constructor.

**Calidad y fronteras**

- **FR-017**: `core/`, el bucle, los puertos, el registro, la política, la configuración y los dobles existentes MUST NOT modificarse; solo se añaden archivos (más los `__init__.py` de los paquetes nuevos y la documentación).
- **FR-018**: MUST existir una guarda de arquitectura con `ast` para `adapters/` que compruebe que no importa `cli`, que `adapters/tools/` y `adapters/system/` solo usan biblioteca estándar y `harness_agent.core` (sin `config`, sin otro adaptador, sin terceros), y que no imprimen ni leen la terminal; con autopruebas del detector.
- **FR-019**: MUST existir una prueba de contrato que corra la misma batería contra `DummyAuthorizedArea` y `WorkspaceArea` en lo que ambos deben cumplir.
- **FR-020**: MUST existir pruebas de integración con el bucle real, `DefaultPermissionPolicy`, el registro real y un área real que verifiquen AC-01 a AC-04, incluida la decisión de permiso publicada, con y sin la regla de lectura de HU-05-01.
- **FR-021**: Las pruebas MUST usar solo carpetas temporales, no tocar el repositorio ni el directorio personal, y no usar red.
- **FR-022**: `ruff format --check`, `ruff check`, `mypy src tests` y `pytest` MUST pasar con las versiones fijadas y los módulos nuevos MUST tener 100 % de cobertura de líneas y ramas salvo las ramas exclusivas de una plataforma, que se cubren con las pruebas sintéticas y las marcadas por plataforma.
- **FR-023**: Al cerrar, `docs/PROGRESO.md` MUST reflejar la historia (estado «En revisión», archivos y evidencia) según el Principio VIII, y las skills y `arbol.md` MUST actualizarse si cambian (en `.claude/skills/` y `.agents/skills/`).

### Key Entities

- **Área de trabajo (`WorkspaceArea`)**: carpeta real autorizada; sabe si una ruta, ya resuelta, queda dentro.
- **Ruta real**: la ruta absoluta, normalizada y sin enlaces simbólicos a la que apunta el argumento `path`.
- **Herramienta de archivos**: una de las cuatro; tiene nombre, riesgo y esquema con `path`.
- **Resultado de error**: `ToolResult` con `is_error=True`, causa y sugerencia en español.
- **Límites**: tamaño máximo de lectura y de escritura, máximo de entradas listadas, de coincidencias y de caracteres por línea (constantes documentadas en el plan).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de los casos de la batería de escape (al menos 15 rutas hostiles: «..», absolutas, enlaces a archivos y carpetas, enlace roto, enlace circular, carácter nulo y las variantes de Windows), ningún byte se escribe fuera del área y el archivo externo queda idéntico.
- **SC-002**: Las tres herramientas de lectura y la de escritura devuelven un resultado estructurado, no una excepción, en el 100 % de los casos de error probados (ruta inexistente, carpeta por archivo, archivo grande, binario, no UTF-8, sin área, permisos).
- **SC-003**: Con el bucle real, una escritura dentro del área publica la decisión de permitir y crea el archivo; una escritura fuera del área o sin área se resuelve como denegada y no crea nada, en el 100 % de los casos de prueba.
- **SC-004**: `WorkspaceArea.contains` y `DummyAuthorizedArea.contains` coinciden en la batería común de contrato, y `WorkspaceArea` es más estricto solo donde el doble es solo léxico (enlaces, Windows).
- **SC-005**: Los resultados de error y de búsqueda están acotados: ninguna respuesta supera el máximo documentado de caracteres, con un aviso cuando se recorta.
- **SC-006**: 0 pruebas existentes modificadas y 0 en rojo; la suite completa y la CI en Linux y Windows pasan.
- **SC-007**: Los módulos nuevos tienen 100 % de cobertura de líneas y ramas, y `ruff`, `mypy --strict` y `pytest` terminan con código 0.

## Assumptions

- **HU-00-01 sigue pendiente de aprobación técnica.** Esta historia no cambia ningún puerto, el bucle, el catálogo de eventos ni los dobles, así que no depende de esa ratificación para implementarse, pero debe producirse antes de pasar a «Hecha».
- La **regla de lectura** de HU-05-01 es un supuesto del PO aún sin confirmar; si se rechaza, las lecturas pasan a «preguntar» sin cambiar esta historia.
- El **motivo específico** de un rechazo por la política (fuera del área, sin área) no llega al modelo en el Sprint 1: el bucle redacta un texto genérico (hallazgo de HU-05-01). El motivo claro que pide AC-03 lo da la propia herramienta cuando se ejecuta y, para lo que la política deniega o pregunta, el texto genérico del bucle; la causa específica llega con HU-05-03.
- **`bootstrap.py` no existe**: la composición (área desde `HarnessConfig.paths.workspace_root`, herramientas, registro, política) se hace en las pruebas de integración y queda anotada para la historia que cree la raíz de composición.
- **Mejor esfuerzo contra la carrera de comprobación y uso**: se vuelve a resolver y comprobar justo antes de actuar; cerrar del todo la ventana exige descriptores de archivo y es una mejora posterior.
- **`FakeProvider` (HU-00-03) aún no está en `main`**; las pruebas de integración usan `ScriptedProvider` y podrán migrar cuando el PR #10 se integre.
- **`editar_archivo`**, la denegación de la base de datos y de la copia de criterios (HU-11-01), el shell (HU-01-04) y la carpeta de la sesión (HU-03-01) quedan fuera.
- **Nombres en inglés** para clases, métodos y atributos; los textos de usuario, los mensajes de error y la documentación van en español.
- Los **límites** son valores iniciales fijos de esta historia; hacerlos configurables es una mejora posterior.
- Estimación: las tareas Sp1-18 a Sp1-22 suman 13 h (780 min); las microtareas de esta historia suman unos 545 min (350 de las tareas F5 y 195 transversales: estado, integración, guarda, documentación y cierre), dentro del presupuesto.
