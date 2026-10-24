# PD-07 — Python 3.12.x como única versión soportada

**Route**: delegated direct (single writer). **TDD**: off (config/governance change), runner `.venv/Scripts/python.exe -m pytest`.
**Authority**: decisión expresa del Product Owner, 2026-10-17. Sin commits (instrucción del usuario).

## Checklist
- [x] T1 pyproject.toml, CI, requirements-dev.txt a 3.12
- [x] T2 Constitución (Principio III, versión 1.1.0)
- [x] T3 Docs vigentes y PROGRESO (PD-07 resuelta)
- [x] T4 Specs 001/002/003 y odd de SPK-02
- [x] T5 Validación (pytest, mypy, ruff, YAML/TOML) y grep de "3.11"

## Evidencia
- Entorno: Windows 10, Python 3.12.10 (.venv). pip check sin conflictos; pines de requirements-dev.txt (pytest 8.3.4, pytest-asyncio 0.25.3, pytest-cov 6.0.0, mypy 1.14.1, ruff 0.9.6) coinciden con lo instalado.
- pytest: 35 passed (26 del spike); mypy src tests: sin errores (29 archivos); ruff format --check: 29 archivos formateados; ruff check: limpio.
- pyproject.toml parsea con tomllib (>=3.12,<3.13 / mypy 3.12 / ruff py312); ci.yml parsea como YAML (os ubuntu+windows, python-version ["3.12"]).
- Pendiente: ejecucion de la CI nueva en remoto (nada subido); prueba real en Linux; aprobacion humana de D-01.
- Excepcion ODD: sin commits por instruccion expresa del usuario.
