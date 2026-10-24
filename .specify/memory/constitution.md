<!--
Sync Impact Report (1.1.0, 2026-10-17):
- Version change: 1.0.0 -> 1.1.0 (MINOR: se acota la versión soportada de Python).
- Modified principle: Principio III. «Python 3.12+» pasa a «Python 3.12.x» como único estándar obligatorio (PD-07, aprobada por el Product Owner el 2026-10-17). Se descarta la compatibilidad con Python 3.11; no es obligatorio dar soporte a 3.13 o superior.
- Templates/artefactos alineados: pyproject.toml (`requires-python = ">=3.12,<3.13"`), .github/workflows/ci.yml (matriz Windows y Linux con 3.12), requirements-dev.txt, specs de HU-00-01, HU-00-02 y SPK-02, docs/ vigentes.
- Follow-up TODOs: ninguno.

Sync Impact Report (1.0.0):
- Version change: Initial scaffold -> 1.0.0
- List of modified principles: Replaced template placeholders with 10 ratified core principles:
  - Principio I: Una historia de usuario por especificación
  - Principio II: Microtareas acotadas de 15 a 40 minutos
  - Principio III: Código modular, reutilizable y tipado en Python 3.12.x (acotado por PD-07 en la versión 1.1.0)
  - Principio IV: Pruebas automatizadas, calidad y CI multiplataforma
  - Principio V: Inmutabilidad de criterios de aceptación y prioridades
  - Principio VI: Disciplina de sprints y entrega por fases
  - Principio VII: Consulta documental quirúrgica y contexto relevante
  - Principio VIII: Registro obligatorio y sincronización de docs/PROGRESO.md
  - Principio IX: Definition of Done estricta y verificación humana
  - Principio X: Inmutabilidad histórica en docs/archivo/
- Added sections:
  - Restricciones Arquitectónicas y División de Responsabilidades (HARNESS v2.5)
  - Flujo de Desarrollo, Pruebas y Puertas de Calidad
  - Governance
- Removed sections: Template placeholder comments and example sections.
- Follow-up TODOs: None (all governance items and principles defined).
-->

# HARNESS Constitution

## Core Principles

### Principio I: Una historia de usuario por especificación
Cada especificación funcional generada mediante Spec Kit DEBE abordar exclusivamente una Historia de Usuario (HU) identificable del backlog activo. Se prohíbe agrupar múltiples historias en una sola especificación, salvo incrementos pequeños y fuertemente cohesionados debidamente justificados en el documento de especificación y aprobados previamente.
*Razón de ser:* Garantiza trazabilidad bidireccional estricta (1:1) con los requisitos (`RF-*`, `RNF-*`), acota el contexto operativo y previene desbordamientos de alcance.

### Principio II: Microtareas acotadas de 15 a 40 minutos
Toda tarea de implementación generada en los planes de trabajo DEBE descomponerse en unidades atómicas estimadas para completarse en un rango de 15 a 40 minutos. El límite máximo absoluto por microtarea es de 60 minutos, debiendo incluir en dicho lapso la codificación, las pruebas automatizadas y el registro de progreso. Si una tarea supera o amenaza con superar los 60 minutos, DEBE dividirse de inmediato.
*Razón de ser:* Mitiga la fatiga contextual del agente y del desarrollador, asegura puntos de control frecuentes y mantiene una cadencia de verificación predecible.

### Principio III: Código modular, reutilizable y tipado en Python 3.12.x
Todo el código del proyecto DEBE implementarse en Python 3.12.x (única versión soportada oficialmente; sin compatibilidad obligatoria con 3.11 ni con 3.13 o superior, decisión PD-07 del Product Owner, 2026-10-17) bajo los principios de Arquitectura Hexagonal (Puertos y Adaptadores). El código DEBE ser modular, fuertemente tipado con type hints exhaustivos, altamente desacoplado y comprobable mediante inversión de dependencias. El núcleo (`src/harness_agent/core/`) NUNCA debe importar librerías de interfaz de usuario (CLI o web), SDKs propietarios de proveedores LLM ni librerías de infraestructura externa.
*Razón de ser:* Permite que el núcleo permanezca puro, reutilizable y agnóstico a la interfaz y a los proveedores, facilitando la evolución técnica y la portabilidad.

### Principio IV: Pruebas automatizadas, calidad y CI multiplataforma
Toda funcionalidad DEBE incorporar pruebas unitarias y de integración automáticas ejecutables con `pytest` sin depender de red externa ni cuotas reales de API, apoyándose en dobles de prueba y en el proveedor simulado (`FakeProvider`). El código DEBE superar la verificación estricta de tipos (`mypy`/`pyright`), formateo y reglas de análisis estático (`ruff`). El pipeline de Integración Continua (CI) DEBE ejecutarse y pasar de forma obligatoria tanto en Windows como en Linux.
*Razón de ser:* El equipo trabaja en entornos heterogéneos (Windows y Linux Arch); la calidad verificable sin dependencias de red garantiza estabilidad e integridad en cada confirmación.

### Principio V: Inmutabilidad de criterios de aceptación y prioridades
Los criterios de aceptación (AC) de las historias de usuario y sus prioridades asignadas NO DEBEN alterarse, relajarse ni omitirse bajo ninguna circunstancia sin la autorización expresa del Product Owner (Brad). En el Coding Harness, la tabla `criterios` de SQLite es la única fuente de verdad; las copias JSON son de solo lectura y cualquier intento de modificación no autorizado por parte de herramientas o shell DEBE ser denegado, registrado y restaurado.
*Razón de ser:* Previene el antipatrón de «victoria prematura», asegurando que el agente o desarrollador no modifique la meta para ajustarla a un comportamiento erróneo o incompleto.

### Principio VI: Disciplina de sprints y entrega por fases
Está ESTRICTAMENTE PROHIBIDO implementar código, herramientas o dependencias correspondientes a sprints futuros. El desarrollo DEBE circunscribirse estrictamente a las historias y tareas asignadas al sprint activo y a los criterios de demostración ratificados para la iteración en curso.
*Razón de ser:* Preserva la capacidad real del equipo, evita la dispersión de esfuerzos y asegura la entrega de incrementos verticales completamente funcionales en cada sprint.

### Principio VII: Consulta documental quirúrgica y contexto relevante
Para la resolución de cualquier microtarea o historia, el agente o desarrollador DEBE consultar ÚNICAMENTE los documentos activos pertinentes a su alcance inmediato (`00-indice.md`, contratos en `02-arquitectura.md`, fichas de historia en `04a`–`04e` y estado en `PROGRESO.md`). Queda prohibida la carga masiva e indiscriminada de documentación irrelevante en la ventana de trabajo.
*Razón de ser:* Optimiza el uso de la ventana de contexto, reduce la degradación de atención y previene alucinaciones o confusiones de requerimientos.

### Principio VIII: Registro obligatorio y sincronización de docs/PROGRESO.md
Inmediatamente después de concluir la implementación de una historia o tarea, DEBE actualizarse `docs/PROGRESO.md`. El registro DEBE documentar el estado, commit/PR, rutas de archivos modificados bajo `src/harness_agent/` o `tests/`, y la evidencia verificable (comando ejecutado y resultado obtenido).
*Razón de ser:* `docs/PROGRESO.md` constituye la única fuente de verdad del avance del proyecto; su sincronización garantiza el relevo efectivo entre sesiones y la auditoría continua.

### Principio IX: Definition of Done estricta y verificación humana
Ninguna historia puede transicionar al estado `Hecha` sin satisfacer la Definition of Done (DoD) completa: (a) código integrado con CI aprobada en Windows y Linux, (b) pruebas unitarias y de integración passing, (c) criterios de aceptación 100 % verificados, (d) tipado y formateo limpios, (e) ausencia de secretos en código y trazas, (f) revisión por pares de otro integrante del equipo, y (g) validación para la demostración del sprint. Las operaciones críticas (push, merge, aprobación de diff) y los criterios semánticos REQUIEREN obligatoriamente confirmación humana.
*Razón de ser:* Garantiza estándares no negociables de calidad, seguridad y supervisión humana efectiva (*Human-in-the-Loop*).

### Principio X: Inmutabilidad histórica en docs/archivo/
Los documentos ubicados en `docs/archivo/` (`CONTEXTO_HARNESS_v1.md`, `CONTEXTO_HARNESS_v2.md`, `CONTEXTO_HARNESS_v2.5.md`) son piezas históricas inalterables que reflejan el estado del análisis en momentos específicos. NUNCA deben modificarse ni sobreescribirse. Toda evolución técnica, ajuste de diseño o refinamiento de planificación DEBE registrarse exclusivamente en la documentación activa (`01` a `06` y `PROGRESO.md`).
*Razón de ser:* Protege la trazabilidad histórica del proyecto, las razones detrás de las decisiones pasadas y la validez de las auditorías de planificación.

## Restricciones Arquitectónicas y División de Responsabilidades (HARNESS v2.5)

### División de Responsabilidades por Área
El equipo de 3 personas mantiene dueños claros por subsistema, aplicando siempre revisión cruzada:
1. **Área A — Núcleo (Core):** Responsable del bucle agéntico principal (`core/agent`), límites de turnos/tiempo/costo, contratos e interfaces primarias (`Provider`, `Tool`), pruebas de fallos del núcleo, orquestación de subagentes y flujo general del Coding Harness.
2. **Área B — Estado (State):** Responsable de la persistencia transaccional en SQLite (`SessionStore`), gestión de contexto (`ContextManager`, prefijo estable, umbrales de compactación y protección de `contexto_esencial`), almacén de memoria (`MemoryStore`), proveedor simulado (`FakeProvider`) y adaptador LiteLLM para proveedores de modelos.
3. **Área C — Control y Conexiones (Control & Connections):** Responsable de la política de permisos con falla cerrada (`PermissionPolicy`: denegar > preguntar > permitir), interfaz de aprobación humana asíncrona (`Approver`), interfaz CLI con eventos en tiempo real, herramienta `Shell` portable multiplataforma, componente `AreaAutorizada` (validación de rutas reales y prevención de escapes), cliente MCP por stdio y perfil de subagente verificador.

### Decisiones de Diseño No Negociables (V-01 a V-17)
- **V-01 (Aprobación bidireccional):** El núcleo no imprime ni bloquea en terminal; espera una decisión asíncrona a través de la interfaz `Approver`.
- **V-02 (Prioridad de denegación):** La política de permisos falla cerrada; una regla de denegación SIEMPRE prevalece sobre cualquier aprobación previa de sesión.
- **V-03 (Compactación no destructiva):** La compactación nunca elimina eventos de SQLite; añade un resumen y referencia los eventos cubiertos en la base de datos.
- **V-04 (Contexto esencial inmutable):** El objetivo, instrucciones, reglas, ticket, referencia a criterios y decisiones acumuladas residen en `contexto_esencial` y se inyectan en el prefijo; NUNCA se compactan ni resumen.
- **V-05 (Relevancia de memoria):** Definida como recencia dentro de un presupuesto de tokens asignado. Los embeddings quedan relegados a la fase de innovación.
- **V-06 (Contrato de subagentes):** Entrada tipada `{objetivo, contexto_minimo, formato_salida, perfil}`; salida estructurada `{resultado, hallazgos_clave, fuentes, error}`. Las aprobaciones de permisos escalan obligatoriamente al usuario.
- **V-07 (Métricas de latencia):** Se mide el tiempo propio del harness por turno con `FakeProvider`, aislando la latencia externa del LLM.
- **V-08 (Shell portable):** Implementación dual (`PowerShell` en Windows, `bash` en Linux) detrás de la interfaz `Shell`; el prefijo informa el SO e intérprete activo; CI obligatoria en ambas plataformas.
- **V-09 (Conteo de tokens):** Estimación heurística inicial corregida turno a turno con el reporte real de consumo de la API.
- **V-10 (Umbral dinámico de compactación):** El umbral depende del tamaño de ventana del modelo activo y se recalcula automáticamente ante una conmutación de proveedor.
- **V-11 (Cancelación limpia de herramientas):** La interrupción (Ctrl+C) cancela la ejecución, emite evento de interrupción y devuelve el resultado correspondiente al modelo en el siguiente turno.
- **V-12 (Instrucciones del proyecto):** El prefijo estable del contexto soporta la carga de instrucciones del proyecto.
- **V-13 (Alcance de detección de secretos):** Búsqueda de patrones conocidos y de valores de variables de entorno cargadas; redacción obligatoria antes de persistir en auditoría o trazas.
- **V-14 (Proveedor simulado):** `FakeProvider` con capacidad de reproducir guiones y simular fallos (cuota, tiempo, errores) es la base de las pruebas automatizadas.
- **V-15 (Protección contra victoria prematura):** Criterios protegidos en SQLite (tabla `criterios`). Solo el harness actualiza `passes`: criterios objetivos mediante comandos automatizados; criterios semánticos exclusivamente con confirmación humana.
- **V-16 (Relevo y continuidad por ticket):** Rutina de arranque determinista al reanudar un ticket (leer archivo de progreso, consultar log de git, ejecutar prueba básica de sanidad y corregir fallos antes de avanzar).
- **V-17 (Comandos encadenados y permisos críticos):** Comandos compuestos (`&&`, `|`, `;`) se descomponen y evalúan por partes bajo la regla más restrictiva. Operaciones `git push`, `merge` y `deploy` exigen SIEMPRE aprobación humana.

### Conjunto Mínimo de Herramientas
El modelo opera con un número reducido de herramientas generales: `shell`, `leer_archivo`, `escribir_archivo`, `editar_archivo`, `preguntar_usuario` y `delegar_subagente`. Operaciones de Git, pruebas unitarias y linters se ejecutan a través de `shell` bajo la política de permisos. Memoria persistente y clientes MCP se integran como complementos al `ToolRegistry`.

## Flujo de Desarrollo, Pruebas y Puertas de Calidad

### Definition of Done (DoD)
Para que cualquier historia de usuario se considere completada, DEBE satisfacer:
1. Código integrado en rama correspondiente y pasando el pipeline de CI en Windows y Linux.
2. Pruebas automatizadas (unitarias y de integración) escritas y pasando al 100 % con `FakeProvider`.
3. Criterios de aceptación de la historia formalmente verificados.
4. Verificación de tipos estática y formateo sin advertencias ni errores.
5. Ausencia total de secretos en código fuente, configuraciones y registros de auditoría.
6. Revisión y aprobación por un integrante de otra área de responsabilidad.
7. Comprobación satisfactoria contra los criterios de demostración del sprint.

### Protocolo de Puertas de Calidad (Quality Gates)
- **TDD y Dobles de Prueba:** Los contratos de interfaces (`HU-00-01`) se implementan primero con dobles de prueba para desbloquear el desarrollo concurrente entre A, B y C.
- **Manejo de Errores y Aislamiento:** Las herramientas externas y servidores MCP DEBEN aislar sus fallos; la caída de un servidor MCP o error de proveedor no debe quebrar la sesión del agente.
- **Falla Cerrada:** Todo comando, acceso fuera de `AreaAutorizada` o llamada ambigua no autorizada explícitamente se clasifica como denegada o sujeta a confirmación humana inmediata.

## Governance

### Autoridad y Cumplimiento
Esta constitución representa el marco de gobernanza supremo para el desarrollo de HARNESS. Prevalece sobre cualquier sugerencia de herramientas de asistencia, código preliminar o atajos de implementación. Todas las revisiones de código y solicitudes de extracción (PR) DEBEN certificar el cumplimiento de los principios y restricciones aquí establecidos.

### Procedimiento de Enmienda
Cualquier modificación a esta constitución requiere:
1. Justificación técnica documentada del cambio propuesto.
2. Elaboración de un informe de impacto (Sync Impact Report) detallando adiciones, modificaciones o eliminaciones.
3. Aprobación unánime del equipo y ratificación formal del Product Owner (Brad).
4. Actualización del número de versión siguiendo las reglas de versionado semántico.

### Política de Versionado
El número de versión de la constitución sigue la convención SemVer (`MAJOR.MINOR.PATCH`):
- **MAJOR:** Modificación, reinterpretación o remoción de principios fundamentales, responsabilidades clave o contratos arquitectónicos no negociables.
- **MINOR:** Adición de nuevos principios, secciones organizativas o ampliación de directrices de desarrollo sin romper compatibilidad con los principios existentes.
- **PATCH:** Correcciones de redacción, resolución de erratas tipográficas o aclaraciones no semánticas.

**Version**: 1.1.0 | **Ratified**: 2026-10-17 | **Last Amended**: 2026-10-17
