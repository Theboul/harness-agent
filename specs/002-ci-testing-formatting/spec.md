# Feature Specification: HU-00-02 — Integración continua con pruebas, tipado y formato

**Feature Branch**: `002-ci-testing-formatting`

**Created**: 2026-10-17

**Status**: Draft

## Clarifications

### Session 2026-10-17

- Q: ¿Cuál es la plataforma remota del repositorio y el motor de ejecución de integración continua? → A: GitHub (`https://github.com/Theboul/harness-agent.git`) como plataforma remota y GitHub Actions como motor de CI, mediante workflows declarativos bajo `.github/workflows/ci.yml`.
- Q: ¿Cómo se implementa y verifica la exigencia de checks obligatorios antes del merge (AC-01)? → A: Mediante doble mecanismo: (1) a nivel de pipeline, el workflow emite código de salida no cero (`exit code != 0`) ante cualquier fallo de pruebas, tipado o formato; y (2) a nivel de gobernanza de repositorio, se documenta la configuración administrativa de reglas de protección de rama (*Branch Protection Rules*) en GitHub sobre `main` requiriendo los checks de la matriz para habilitar el merge.
- Q: ¿Cuál es la estrategia de versionado y fijación de dependencias para reproducibilidad (Sp1-06)? → A: Enfoque dual estándar: `pyproject.toml` preserva restricciones mínimas (`>=`) para empaquetado, mientras que `requirements-dev.txt` fija versiones exactas (`==`) de las herramientas dev (`pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`) garantizando instalaciones deterministas en CI.
- Q: ¿Qué versión de Python y matriz de sistemas operativos deben verificarse (AC-02)? → A: Python 3.12 (mandatario por Principio III de la Constitución y `pyproject.toml`), evaluado en matriz obligatoria paralela sobre ejecutores `ubuntu-latest` (Linux) y `windows-latest` (Windows).
- Q: ¿Qué herramientas concretas ejecutan pruebas, cobertura, tipado y formato (Sp1-05)? → A: `pytest` con `pytest-asyncio` para la suite de pruebas, `pytest-cov` para el informe de cobertura en terminal, `mypy` en modo estricto (`--strict`) para verificación estática de tipos, y `ruff` (`ruff format --check` y `ruff check`) para inspección no modificatoria de formato y linting (Principio IV de la Constitución).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Validación automatizada de calidad y bloqueo ante defectos (Priority: P1) [AC-01]

Como equipo de desarrollo (A, B y C), quiero que cada cambio propuesto en el repositorio sea validado automáticamente por un pipeline que ejecute pruebas, comprobación estricta de tipos y verificación de formato, para detectar errores tempranamente y bloquear la integración de código defectuoso antes de que llegue a la rama principal.

**Why this priority**: Es el núcleo de la historia y el salvaguarda de calidad (AC-01 / RNF-14 / RNF-20). Sin validación automatizada obligatoria, el desarrollo en paralelo de los tres integrantes corre el riesgo constante de integrar regresiones en los contratos e implementaciones.

**Independent Test**: Puede probarse de forma independiente introduciendo intencionalmente una prueba fallida, un error de tipos o una discrepancia de formato en una rama de propuesta; el pipeline debe fallar de manera no negociable y emitir un estado de fallo que impida la integración.

**Acceptance Scenarios**:

1. **Given** una propuesta de cambio con una prueba unitaria o de contrato fallida, **When** el pipeline de CI se ejecuta automáticamente, **Then** el trabajo reporta fallo y el cambio queda bloqueado para integración.
2. **Given** una propuesta de cambio con inconsistencias o errores de tipado estático, **When** el pipeline de CI se ejecuta, **Then** el paso de verificación de tipos finaliza con código de error y el cambio queda bloqueado para integración.
3. **Given** una propuesta de cambio con código que no cumple las reglas de formato establecidas, **When** el pipeline de CI se ejecuta, **Then** la comprobación de formato falla en modo de solo lectura (sin modificar automáticamente los archivos en el entorno de CI) e impide la fusión.
4. **Given** una propuesta de cambio con pruebas pasando al 100 %, tipado estricto sin errores y formato verificado, **When** el pipeline de CI se ejecuta, **Then** todos los pasos concluyen en verde y se emite un estado de éxito para la propuesta.

---

### User Story 2 - Matriz de ejecución multiplataforma homogénea en Linux y Windows (Priority: P2) [AC-02]

Como equipo de desarrollo que colabora en entornos heterogéneos (integrantes en Windows y Linux Arch), quiero que el pipeline ejecute la suite de verificación completa en ambos sistemas operativos para garantizar que el código, las rutas y las herramientas sean plenamente portables.

**Why this priority**: Cumple directamente AC-02, RNF-15 y el Principio IV de la Constitución. Garantiza que discrepancias de plataforma (separadores de ruta, saltos de línea, intérpretes de shell) se identifiquen inmediatamente en CI antes de afectar a los desarrolladores.

**Independent Test**: Puede probarse ejecutando el pipeline sobre una confirmación estándar y verificando en la interfaz de CI que se ejecutan y completan los trabajos correspondientes tanto a Linux como a Windows.

**Acceptance Scenarios**:

1. **Given** un cambio propuesto en el repositorio, **When** se desencadena el pipeline de CI, **Then** se inician y ejecutan trabajos de validación independientes tanto en un entorno Linux como en un entorno Windows.
2. **Given** un cambio con comportamiento o dependencias incompatibles con Windows (e.g. rutas con barras duras o supuestos específicos de POSIX), **When** el pipeline corre en la matriz, **Then** el trabajo de Windows falla y el pipeline general reporta fallo, bloqueando la integración.
3. **Given** un cambio que satisface todos los requisitos en ambas plataformas, **When** el pipeline concluye, **Then** ambos entornos reportan éxito de manera consistente.

---

### User Story 3 - Dependencias reproducibles e informe de cobertura (Priority: P3) [Sp1-05, Sp1-06]

Como desarrollador y revisor técnico, quiero que la instalación de dependencias en CI sea determinista y reproducible mediante versiones fijadas, y que la ejecución de pruebas genere un informe consolidado de cobertura de código, para asegurar estabilidad a largo plazo y visibilidad sobre el alcance de las pruebas.

**Why this priority**: Responde a las tareas Sp1-05 y Sp1-06 de la planificación, asegurando que el pipeline no se rompa por actualizaciones inesperadas de librerías de terceros (dev) y proporcionando métricas claras para la Definition of Done.

**Independent Test**: Puede probarse ejecutando la instalación en un entorno limpio sin caché y verificando que las versiones instaladas coinciden exactamente con las fijadas, y que tras las pruebas se emite el resumen de cobertura en los registros del pipeline.

**Acceptance Scenarios**:

1. **Given** un ejecutor de CI recién aprovisionado, **When** se ejecutan las tareas de instalación de dependencias, **Then** se instalan versiones estrictamente fijadas sin resolver rangos flotantes no controlados.
2. **Given** la ejecución exitosa de la suite de pruebas en el pipeline, **When** finaliza el paso de pruebas, **Then** se produce un resumen de cobertura indicando el porcentaje de código evaluado en `src/harness_agent/`.

---

### Edge Cases

- **Tiempo de espera o caída de red durante instalación de dependencias**: El pipeline debe tener configurados tiempos máximos (timeouts) por trabajo para no quedar en espera indefinida en caso de indisponibilidad externa.
- **Divergencia de saltos de línea (CRLF vs LF) entre plataformas**: La herramienta de formato y el pipeline deben evaluar el formato de manera consistente sin generar falsos positivos por la conversión de fin de línea propia de Git en Windows.
- **Ejecución no interactiva**: Todas las herramientas invocadas en el pipeline deben operar estrictamente en modo por lotes/no interactivo, fallando inmediatamente ante cualquier requerimiento de entrada manual de usuario.
- **Diferenciación entre fallo de workflow y protección de rama remota**: En un entorno local o repositorio sin rama protegida en el servidor remoto, el workflow emite el código de salida fallido (`exit code != 0`), pero la regla de protección que bloquea físicamente el botón de merge en la plataforma remota requiere configuración administrativa del repositorio (ver sección de Supuestos y Gobernanza).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema de integración continua DEBE desencadenar automáticamente la ejecución del pipeline ante cada propuesta de cambio (pull request) y confirmación dirigida a las ramas principales de integración.
- **FR-002**: El pipeline DEBE ejecutar la suite automatizada de pruebas unitarias y de contratos, fallando de forma inmediata si cualquier prueba resulta fallida o genera un error de ejecución.
- **FR-003**: El pipeline DEBE realizar la verificación estricta de tipos estáticos sobre todo el código fuente bajo `src/` y las pruebas bajo `tests/`, finalizando con código de error si se detecta alguna discrepancia o fallo de tipado.
- **FR-004**: El pipeline DEBE verificar el cumplimiento del formateo de código y estilo en modo inspección (`check` / no modificatorio), fallando si existen archivos que no cumplen con el formato estándar, sin modificar código automáticamente durante la ejecución en CI.
- **FR-005**: El pipeline DEBE calcular y generar un informe/resumen de cobertura de pruebas sobre el paquete principal de la aplicación.
- **FR-006**: El pipeline DEBE instalar las dependencias de desarrollo y ejecución a partir de especificaciones con versiones fijadas, garantizando compilaciones y entornos deterministas.
- **FR-007**: El pipeline DEBE ejecutar las tareas de verificación en una matriz que incluya obligatoriamente entornos Linux y Windows.
- **FR-008**: Cada paso fallido del pipeline DEBE retornar un código de salida distinto de cero (`exit code != 0`) para notificar formalmente el estado de fallo al sistema de control de versiones.
- **FR-009**: La documentación del pipeline y la planificación de tareas DEBEN distinguir explícitamente entre la creación del archivo de definición de workflow ejecutable y la configuración de reglas de protección de rama en el servidor de Git (requerimiento administrativo de gobernanza).

### Key Entities *(include if feature involves data)*

- **Configuración de Pipeline (Workflow)**: Declaración estructurada de automatización que especifica eventos de disparo, matriz de sistemas operativos (Linux y Windows), versión de intérprete (Python 3.12), pasos de preparación de entorno, instalación de dependencias fijadas y comandos de verificación de calidad.
- **Manifiesto de Dependencias Fijadas**: Registro determinista de dependencias de desarrollo (herramientas de prueba, tipado, formato y cobertura) con números de versión precisos para evitar variaciones entre entornos locales y CI.
- **Informe de Calidad y Coberura**: Resultado agregado emitido en los registros de CI que resume el estado de las pruebas (pasadas, fallidas), errores de tipado, archivos con discrepancias de formato y el porcentaje de cobertura de código alcanzado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las propuestas de cambio desencadenan automáticamente la verificación en ambas plataformas (Linux y Windows).
- **SC-002**: Cualquier cambio con una prueba fallida, un error de tipos o un defecto de formato genera un resultado de pipeline fallido en menos de 5 minutos de tiempo de ejecución.
- **SC-003**: El pipeline reporta 100 % de éxito cuando todas las verificaciones pasan limpiamente en ambas plataformas.
- **SC-004**: La instalación de dependencias en CI se realiza de forma 100 % determinista a partir de versiones fijadas, sin recurrir a resoluciones flotantes.
- **SC-005**: Se emite métrica de cobertura de pruebas accesible en los registros de cada ejecución exitosa del pipeline.
- **SC-006**: Ningún cambio con pruebas o tipos rotos puede fusionarse cuando las verificaciones de CI son requeridas en la rama destino.

## Assumptions

- El repositorio utiliza GitHub Actions como motor estándar de integración continua mediante archivos de workflow ubicados bajo `.github/workflows/`.
- Los entornos de ejecución son ejecutores estándar multiplataforma (`ubuntu-latest` y `windows-latest`) con Python 3.12 instalado.
- La configuración de reglas de protección de rama (*branch protection rules*) en el repositorio remoto de GitHub para exigir que los chequeos de CI pasen antes del merge es una acción administrativa que requiere permisos de propietario del repositorio, y se documenta como paso de gobernanza con evidencia verificable.
- Las herramientas de prueba (`pytest`), tipado (`mypy`), formato/linter y cobertura se integran reutilizando la configuración base ya iniciada en `pyproject.toml` en HU-00-01, sin introducir dependencias no relacionadas con CI.
