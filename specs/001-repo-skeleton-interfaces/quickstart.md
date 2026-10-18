# Guía de Validación Rápida: HU-00-01 (Quickstart)

**Feature**: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)  
**Date**: 2026-10-17  

Esta guía describe los escenarios ejecutables para comprobar que los contratos e interfaces del repositorio están correctamente instalados, son importables mediante dobles de prueba y cumplen las reglas de aislamiento arquitectónico.

---

## 1. Prerrequisitos y Configuración de Entorno

- **Python**: 3.12.x (única versión soportada; actualizado por PD-07, 2026-10-17).
- **Sistemas Operativos**: Windows (PowerShell) o Linux (Bash).
- **Herramientas de desarrollo**: `pytest` y `mypy` (o `pyright`).

### Instalación en modo desarrollo
Desde la raíz del repositorio:
```bash
# En Windows (PowerShell) o Linux (Bash)
pip install -e .
```

---

## 2. Escenario 1: Validación de Importación y Dobles de Prueba (AC-01)

### Propósito
Demostrar que los integrantes A, B y C pueden importar cualquier contrato del núcleo (`src/harness_agent/core/`) e instanciar dobles de prueba sin dependencias de infraestructura ni de red.

### Ejecución
```bash
pytest tests/contracts/test_contracts.py -v
```

### Resultados esperados
- El test importa los contratos (`Provider`, `Tool`, `SessionStore`, `Approver`, etc.) y sus entidades canónicas (`Message`, `Event`).
- Se instancian las clases de prueba en memoria (`DummyProvider`, `DummyTool`, `InMemorySessionStore`, `RecordingEventBus`).
- Las corutinas de `Provider.complete` y `Tool.run` se invocan mediante `pytest.mark.asyncio` y devuelven respuestas válidas sin excepciones de tipo.
- **Resultado**: 100 % passing en menos de 2 segundos.

---

## 3. Escenario 2: Comprobación de Pureza del Núcleo y Aislamiento de SDKs (AC-02)

### Propósito
Garantizar mediante análisis estático automatizado (AST) que ningún archivo dentro de `src/harness_agent/core/` importa SDKs propietarios de proveedores LLM (`litellm`, `openai`, `anthropic`, `google-genai`).

### Ejecución
```bash
pytest tests/architecture/test_core_boundaries.py -v
```

### Resultados esperados
- La prueba inspecciona sintácticamente todos los archivos `.py` bajo `src/harness_agent/core/`.
- Se auditan todas las sentencias `import <x>` y `from <x> import <y>`.
- Si se detecta cualquier importación prohibida, el test falla informando el archivo exacto y la línea infractora.
- **Resultado**: 0 importaciones prohibidas detectadas (`PASSED`).

---

## 4. Escenario 3: Verificación Estática de Tipos

### Propósito
Asegurar que todas las firmas abstractas y modelos de datos cumplen el tipado estricto sin anotaciones `Any` ambiguas ni violaciones de firma.

### Ejecución
```bash
mypy src/harness_agent/ tests/
```

### Resultados esperados
- `Success: no issues found in X source files`.
