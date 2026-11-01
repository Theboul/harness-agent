# Tareas: HU-00-07 — Cobertura mínima y prueba de instalación

Presupuesto: Sp3 (2 PHU). Cada tarea: prueba primero cuando hay código de prueba.

- [x] T001 Medir la cobertura real (suite completa en 5 fragmentos con `COVERAGE_FILE` propio y `coverage combine`): paquete 99 %, `core/` 100 %. → umbral 95 % (ver spec).
- [x] T002 `tests/unit/test_ci_quality_gates.py`; visto fallar (3 de 4) con `ci.yml` sin cambios; ahora pasan las 4.
- [x] T003 `.github/workflows/ci.yml`: `--cov-fail-under=95`, paso de núcleo ≥ 60 %, paso de instalación limpia.
- [x] T004 `tests/install/test_clean_install.py` + marca `install` en `pyproject.toml` (excluida por defecto). 4 pasan en ~32 s con `HARNESS_INSTALL_ROOT=C:\tmp\hi`.
- [x] T005 README (instalación y cobertura), `CLAUDE.md` y `arbol.md` (ambas copias).
- [x] T006 Verificación de fronteras (`verificar-fronteras-hexagonales`): `pytest tests/architecture` en verde; sin dependencias nuevas.
- [x] T007 Cuatro puertas de calidad: `ruff format --check`, `ruff check`, `mypy src tests` en 0; suite completa en fragmentos (evidencia en PROGRESO).
- [x] T008 `docs/PROGRESO.md`: HU-00-07 → En revisión.
- [ ] H01 Revisión cruzada (persona de otra área).
- [ ] H02 CI remota en Ubuntu y Windows (los pasos nuevos incluidos; no verificable desde esta sesión).
- [ ] H03 Persona ajena al equipo instala siguiendo el README y anota problemas (AC-02); corregirlos antes de la entrega.
