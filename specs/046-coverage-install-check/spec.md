# Especificación: HU-00-07 — Cobertura mínima y prueba de instalación

**Rama**: `claude/hu-00-07-coverage-install-cab9bc` · **Responsable**: C — Control y conexiones · **Sprint**: 3 (cierre adelantado al 6-nov-2026) · **PHU**: 2  
**Requisitos**: RNF-11, RNF-14 · **Depende de**: HU-00-02, HU-00-06 · **Ficha**: [HU-00-07](../../docs/04a-historias-fundacion.md#hu-00-07)  
**Tipo**: historia de **calidad** (CI, pruebas y documentación). No cambia código de producción, puertos ni eventos.

## Clarificaciones

### Sesión 2026-10-31

Sin preguntas al PO: la regla de negocio (≥ 60 % en el núcleo) y los criterios son explícitos.

- Q: ¿Qué número exige la CI sobre el paquete completo? → A: **95 %** (líneas y ramas, `--cov-fail-under=95`). Medido sobre el estado real: **99 %** del paquete (9 934 sentencias, 2 864 ramas) y **100 %** de `core/` (4 807 sentencias). El margen de 4 puntos absorbe las diferencias entre Ubuntu y Windows (cada sistema omite pruebas distintas) sin dejar pasar una regresión grande.
- Q: ¿Dónde vive el umbral? → A: solo en `.github/workflows/ci.yml`. Un `fail_under` en `pyproject.toml` haría fallar también cada ejecución parcial local (`pytest ruta -k nombre`).
- Q: ¿Cómo se garantiza el 60 % del **núcleo** (AC-01) aparte del total? → A: un paso de CI `coverage report --include="*/harness_agent/core/*" --fail-under=60` sobre los mismos datos.
- Q: ¿Prueba de instalación dentro de la suite normal? → A: no. Necesita la red una vez (pip descarga `setuptools` para construir) y tarda ~30 s. Va marcada `@pytest.mark.install`, excluida por defecto (`-m 'not install'`), y la CI la corre como paso aparte en Ubuntu y Windows.
- Q: ¿Cómo evitar el límite de 260 caracteres de Windows? → A: el venv se crea bajo una ruta corta (`HARNESS_INSTALL_ROOT` o el temporal del sistema) y con nombre `v`.
- Q: ¿Y la «persona ajena» del AC-02? → A: la automatización cubre lo comprobable (instalar, arrancar sin configuración, importar en frío); la instalación por una persona externa siguiendo el README sigue siendo una tarea **humana** (H03).

## Escenarios

1. **CI exige cobertura.** Si el paquete cae por debajo de 95 % o el núcleo por debajo de 60 %, la CI falla.
2. **Instalación limpia.** En un venv nuevo, `pip install --no-deps <checkout>` termina bien.
3. **Arranque sin configuración.** `harness` y `python -m harness_agent`, sin `config.toml`, terminan con salida 2, una línea «No se pudo iniciar: …» y sin traza.
4. **Importación en frío.** Importar `harness_agent` y `harness_agent.bootstrap` no carga `litellm`, `mcp`, `openai` ni `anthropic`.
5. **Suite normal intacta.** `pytest` sin argumentos no ejecuta `tests/install`.

## Requisitos funcionales

- **FR-001**: la CI MUST fallar bajo `--cov-fail-under=95` del paquete y bajo 60 % de `core/` (AC-01).
- **FR-002**: `tests/install/` MUST cubrir los escenarios 2–4 y MUST NOT usar la red fuera de la instalación de pip.
- **FR-003**: las pruebas marcadas MUST estar excluidas por defecto y la CI MUST correrlas en `ubuntu-latest` y `windows-latest`, solo Python 3.12.
- **FR-004**: README y `CLAUDE.md` MUST documentar el comando local `pytest -m install --no-cov tests/install`.
- **FR-005**: `bootstrap.py`, `config.py`, `core/` y los archivos protegidos MUST NOT cambiar.
