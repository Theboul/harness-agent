# Quality Checklist: Requisitos de SPK-02 — Modelo Asíncrono y Cancelación

**Purpose**: Validar la completitud, claridad y calidad de los requisitos de investigación de SPK-02 antes de la descomposición en microtareas  
**Created**: 2026-10-17  
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md)  

**Review Ownership**: Este checklist es un artefacto de revisión de calidad de requisitos propiedad del revisor humano / equipo técnico. Marcar `[x]` solo cuando la revisión confirme que el criterio de calidad está plenamente satisfecho en la documentación.  
**Marker Semantics**: `[x]` indica que el requisito documental está claramente especificado y libre de ambigüedades. No indica que el código esté implementado.  

---

## 1. Definición del Problema y Alcance del Experimento

- [ ] **CHK001**: ¿La especificación delimita con precisión el problema técnico investigado (adopción formal de `asyncio` frente a hilos/síncrono y mecanismo de interrupción de herramientas) distinguiéndolo del bucle definitivo de producción?
- [ ] **CHK002**: ¿Están explícitamente excluidas del alcance del spike las historias futuras (HU-01-01 bucle completo, HU-01-04 shell, HU-05-03 aprobación interactiva, MCP y subagentes)?
- [ ] **CHK003**: ¿Se define un tiempo neto de investigación acotado (~3 horas F5) estructurado en microtareas atómicas de menos de 60 minutos?

## 2. Control, Simulación y Mecanismo de Cancelación

- [ ] **CHK004**: ¿Se define de forma determinista y reproducible la operación prolongada controlada mediante `sys.executable` y `asyncio.create_subprocess_exec` sin recurrir a comandos arbitrarios de shell (`shell=False`)?
- [ ] **CHK005**: ¿Está especificado el protocolo de solicitud de cancelación asíncrona, diferenciando la cancelación voluntaria del usuario del disparo automático por tiempo agotado (timeout)?
- [ ] **CHK006**: ¿Se define un protocolo de parada de dos fases con tiempo de gracia (señal de terminación suave $\rightarrow$ gracia de 100 a 200 ms, 150 ms en el prototipo $\rightarrow$ terminación forzada `kill`) para garantizar que la operación no quede en ejecución?
- [ ] **CHK007**: ¿Están establecidos los criterios objetivos para verificar la terminación real del proceso (`returncode is not None` y ausencia comprobable del PID en el sistema operativo)?

## 3. Retorno del Control y Evidencia para Decisión

- [ ] **CHK008**: ¿Se cuantifica operativamente qué significa «recuperar el control del bucle» (captura de `CancelledError`/`TimeoutError` en $< 500\text{ ms}$ y disponibilidad inmediata para el siguiente turno)?
- [ ] **CHK009**: ¿Se incluye un escenario de validación que demuestre que el bucle puede ejecutar con éxito una operación subsiguiente inmediatamente después de la cancelación?
- [ ] **CHK010**: ¿Se definen las métricas y evidencias concretas que debe aportar el prototipo para resolver de forma concluyente la decisión Sp1-49 sobre el modelo de concurrencia?

## 4. Limitaciones de Plataforma e Impacto en Contratos

- [ ] **CHK011**: ¿Se documentan las particularidades y limitaciones reales de terminación de procesos en Windows (`ProactorEventLoop` / `TerminateProcess`) y en Linux (señales POSIX)?
- [ ] **CHK012**: ¿Se declara explícitamente la limitación de que matar un subproceso directo no garantiza eliminar árboles de procesos nietos, consignando la necesidad de grupos de procesos/Job Objects para HU-01-04?
- [ ] **CHK013**: ¿Se analiza el impacto de la adopción de `asyncio` sobre los contratos existentes de HU-00-01 (`Provider.complete`, `Tool.run`, `Approver.request`), ratificando o rectificando su carácter provisional?
- [ ] **CHK014**: ¿Se justifica técnicamente mantener síncrono el componente `SessionStore` (SQLite local) evitando asincronía innecesaria en operaciones de microsegundos?

---

## Notes

- Marcar los ítems con `[x]` a medida que la revisión técnica corrobore que cada requisito está adecuadamente formulado en `spec.md` y `plan.md`.
- No alterar los contratos de interfaces de `src/harness_agent/core/interfaces/` durante la ejecución del spike.
- Este checklist valida la calidad de la especificación técnica; la verificación empírica de código se realizará durante la ejecución de las microtareas de `tasks.md`.
