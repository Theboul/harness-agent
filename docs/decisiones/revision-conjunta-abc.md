# Paquete de revisión conjunta A, B y C — HU-00-01 (T016 / Sp1-03) y SPK-02 (D-01)

**Preparado**: 2026-10-17  
**Estado**: **PENDIENTE DE REVISIÓN HUMANA.** Este documento no registra ninguna aprobación. Las casillas y tablas de firma están vacías a propósito: solo cada integrante puede completarlas.  
**Alcance**: preparar una única reunión para (1) aprobar los contratos de HU-00-01, (2) revisar la evidencia de SPK-02 y (3) ratificar o rechazar D-01. No modifica firmas de producción.

---

> **Decisión comunicada por el equipo (2026-10-18)**: el equipo comunicó, a través del Product Owner, la decisión de cerrar las historias pendientes y de usar nomenclatura en inglés para `AuthorizedArea` y los 17 eventos del bus. Es una decisión colectiva relayada: **no hay aprobaciones individuales de A, B y C documentadas** (sin Pull Request, comentarios ni actas), así que las tablas de §7 siguen en «Pendiente».

**Rutas legítimas para cerrar las historias** (ninguna se ejecutó ni se solicitó hasta ahora):

1. **Aprobaciones individuales**: A, B y C registran su propia aprobación (por ejemplo, como aprobaciones del Pull Request o en un acta firmada por cada uno). Con eso se puede completar T016 y ratificar D-01.
2. **Excepción formal a la Definition of Done**: si el equipo decide cerrar una historia sin cumplir algún requisito, debe registrarse expresamente como excepción, con responsable nominal y la deuda pendiente (CI remota de la matriz nueva, revisión por otra área, demostración del sprint). Una excepción no equivale a una prueba aprobada.

## 1. Orden de la revisión

La decisión D-01 ratifica firmas que HU-00-01 todavía no aprobó, así que el orden importa:

1. **Contratos de HU-00-01** (T016 / Sp1-03). Sin esto, D-01 no puede ratificar nada.
2. **Evidencia de SPK-02** (solo lectura de resultados ya obtenidos; no hace falta repetir experimentos).
3. **D-01**: ratificar, ratificar con cambios o rechazar.

Revisor sugerido: la Definition of Done exige que revise un integrante de **otra área**. Como A es dueño de ambas historias, la revisión sustantiva corresponde a B y C; A responde dudas.

---

## 2. Parte 1 — Contratos de HU-00-01

Fuentes: `src/harness_agent/core/interfaces/`, `docs/02-arquitectura.md` §4, `docs/guia-contratos-desarrollo.md`, `specs/001-repo-skeleton-interfaces/contracts/core_interfaces.md`.

| # | Punto a revisar | A | B | C |
|---|---|:-:|:-:|:-:|
| 1 | Las interfaces de `core/interfaces/` (14 contratos según `docs/02` §4) cubren lo que cada área necesita para trabajar en paralelo | ☐ | ☐ | ☐ |
| 2 | Firmas de `Provider.complete(messages, tools) -> ProviderResponse`, `Tool.run(args) -> ToolResult` y `Approver.request(call, details) -> ApprovalResult` | ☐ | ☐ | ☐ |
| 3 | Convención de nombres en inglés para métodos y atributos (decisión del 2026-10-17) | ☐ | ☐ | ☐ |
| 4 | **Resuelta (decisión comunicada el 2026-10-18)**: `AreaAutorizada` pasó a `AuthorizedArea` y los 17 valores de `EventType` pasaron a inglés (catálogo canónico en `src/harness_agent/core/events.py`). Revisar que el catálogo refleje lo acordado | ☐ | ☐ | ☐ |
| 5 | El núcleo no importa SDKs externos (AC-02 de HU-00-01) | ☐ | ☐ | ☐ |
| 6 | Los dobles de prueba permiten que cada área avance sin esperar a las demás | ☐ | ☐ | ☐ |

Evidencia ya disponible (no hace falta repetirla): pytest, mypy estricto y ruff limpios en Windows (Python 3.12.10) y en WSL2 Ubuntu (Python 3.12.15); resultados en `docs/PROGRESO.md`.

**Resultado de T016**: _Pendiente de la reunión._ La tarea no se marca como completada hasta que los tres integrantes aprueben (ver §6).

---

## 3. Parte 2 — Evidencia experimental de SPK-02

Qué se comprobó, dónde y qué no. Detalle y mediciones en `docs/decisiones/D-01-asyncio-cancelacion.md` §2 y `specs/003-async-cancellation-spike/research.md`.

| Afirmación | Windows local | WSL2 Ubuntu local | GitHub Actions |
|---|:-:|:-:|:-:|
| AC-01: la cancelación devuelve el control en menos de 500 ms y el PID desaparece | Ejecutado | Ejecutado | **No ejecutado** |
| Casos límite (cancelar antes de iniciar, terminar justo antes, segunda cancelación durante la limpieza) | Ejecutado (con dobles para el escalamiento) | Ejecutado | **No ejecutado** |
| Un hijo real que ignora `SIGTERM` escala a `SIGKILL` (código de salida -9) | No aplica (en Windows `terminate()` equivale a `kill()`) | Ejecutado | **No ejecutado** |
| Comparación de asyncio, hilos y procesos con mediciones | Ejecutado | Ejecutado | **No ejecutado** |
| Árboles de procesos (nietos) | No verificado | No verificado | No verificado |

Puntos para que los revisores cuestionen:

- ☐ La comparación de alternativas es suficiente para sostener la decisión (no prueba rendimiento; prueba que asyncio ofrece una única primitiva para esperar, poner *timeout* y cancelar).
- ☐ Las afirmaciones sobre el SDK de MCP, el streaming de proveedores y SQLite están marcadas como **supuestos**, no como evidencia. ¿Se aceptan como supuestos?
- ☐ Absorber `CancelledError` es válido solo en el prototipo; en producción debe re-lanzarse.

---

## 4. Parte 3 — Decisión D-01

**Propuesta** (Integrante A): adoptar `asyncio` como modelo de concurrencia del núcleo y ratificar `async def` en `Provider.complete`, `Tool.run` y `Approver.request`; `SessionStore` permanece síncrono.

Compatibilidad con las firmas existentes (comprobada contra el código): las tres firmas del documento coinciden con las del código bajo `src/harness_agent/core/interfaces/`. D-01 no propone cambiar ninguna.

Riesgos residuales y trabajo diferido:

| Tema | Estado | Dónde se resuelve |
|---|---|---|
| Árboles de procesos: el protocolo mata el subproceso directo, no a sus nietos | Sin evidencia en el spike | **HU-01-04** (grupos de procesos en POSIX, Job Objects en Windows) |
| Captura de `SIGINT` / Ctrl+C y persistencia del evento de interrupción | Fuera del spike | **HU-06-03** (Sprint 3) |
| Cliente MCP, streaming de proveedores y rendimiento de SQLite | Supuestos sin verificar | Historias de conexión y de estado de los sprints 2 a 4 |
| Nombres en español de `AreaAutorizada` y `EventType` | **Resuelto** el 2026-10-18 (renombrados a inglés; sin datos persistidos que migrar) | Cerrado |

---

## 5. Definition of Done: qué se cumple y qué falta

Fuente: Principio IX y sección «Definition of Done» de la constitución. Nota: en el repositorio versionado rige la constitución v1.0.0; la v1.1.0 (PD-07, Python 3.12.x) y la corrección propuesta v1.1.1 (`AuthorizedArea`) están sin commitear a la espera de la aprobación unánime del equipo y la ratificación del Product Owner. El texto de la Definition of Done es el mismo en todas las versiones.

| # | Requisito | HU-00-01 | SPK-02 |
|---|---|---|---|
| 1 | Código integrado y CI aprobada en Windows y Linux | Parcial: hubo una corrida remota de CI (Run 39087285626, matriz original de 4 jobs). Los cambios posteriores (nombres en inglés, PD-07) **no han corrido en CI** | **Falta**: nada de SPK-02 está commiteado ni subido |
| 2 | Pruebas pasando al 100 % | Cumplido en local (Windows y WSL2) | Cumplido en local (Windows y WSL2) |
| 3 | Criterios de aceptación verificados | Cumplido (AC-01 y AC-02) con aprobación expresa del Product Owner | Cumplido para AC-01 en Windows y Linux locales |
| 4 | Tipado y formato limpios | Cumplido en local | Cumplido en local |
| 5 | Ausencia de secretos | Un barrido de patrones comunes de secretos (claves, tokens, contraseñas) en `src`, `tests`, `specs`, `docs`, `.github` y configuración no halló coincidencias; **falta la confirmación del revisor humano** | Mismo barrido, mismo resultado; falta la confirmación del revisor humano |
| 6 | Revisión por un integrante de otra área | **Falta** (T016) | **Falta** |
| 7 | Comprobación contra los criterios de la demostración del sprint | **Falta** | **Falta** |

**Conclusión: no se cumplen las condiciones de cierre.** Por eso HU-00-01 sigue en «Pendiente de aprobación técnica» y SPK-02 en «En revisión». No corresponde marcar ninguna como `Completada`.

---

## 6. Qué falta exactamente para cerrar

Para HU-00-01 (T016 / Sp1-03):

1. Reunión de revisión con A, B y C.
2. Aprobación explícita de cada integrante, registrada por ellos (por ejemplo, en el Pull Request).
3. ~~Decisión sobre el renombrado de `AreaAutorizada` y `EventType`~~ (resuelta el 2026-10-18; ver §2, punto 4).

Para SPK-02 y D-01:

1. Lo anterior (T016) como prerrequisito.
2. Commitear y subir los cambios, y que la matriz de CI (Linux y Windows con Python 3.12) pase en un runner de GitHub Actions. **Todavía no se ejecutó.**
3. Revisión de B y C sobre la evidencia y D-01, y su ratificación explícita.
4. Validación contra los criterios de demostración del Sprint 1.

---

## 7. Registro de aprobaciones (a completar por cada integrante)

### 7.1 HU-00-01 — contratos (T016 / Sp1-03)

| Integrante | Rol | Decisión | Fecha | Observaciones |
|---|---|---|---|---|
| A | Núcleo | _Pendiente_ | — | |
| B | Estado | _Pendiente_ | — | |
| C | Control y conexiones | _Pendiente_ | — | |

### 7.2 D-01 — decisión sobre asyncio

| Integrante | Rol | Decisión | Fecha | Observaciones |
|---|---|---|---|---|
| A | Núcleo | _Pendiente_ | — | |
| B | Estado | _Pendiente_ | — | |
| C | Control y conexiones | _Pendiente_ | — | |

Valores permitidos: `Aprobada`, `Aprobada con cambios` (indicar cuáles) o `Rechazada`.
