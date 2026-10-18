# Quickstart: HU-07-01 — Interfaz Provider y formato interno de mensajes

**Feature**: `specs/004-provider-interface-message-format/spec.md`  
**Status**: Ready for Validation  
**Date**: 2026-10-18  
**Responsable**: A — Núcleo  

Guía de ejecución y comprobación técnica reproducible para verificar los criterios de aceptación AC-01 y AC-02 de HU-07-01 de forma completamente local y determinista (sin red ni claves comerciales).

---

## 1. Prerrequisitos

- Python 3.12.x instalado y activado en el entorno virtual `.venv`.
- Dependencias de desarrollo instaladas (`pytest`, `mypy`, `ruff` fijadas en `requirements-dev.txt`).
- Repositorio limpio y alineado con los contratos de `HU-00-01`.

```powershell
# Verificación de entorno
.venv\Scripts\python.exe --version
# Salida esperada: Python 3.12.x
```

---

## 2. Escenario de Validación 1: Conversión Bidireccional Sin Pérdida (AC-01)

Verifica que cualquier mensaje o herramienta canónica puede ser convertido al esquema de OpenAI o Anthropic y reconstruido de vuelta a formato canónico con fidelidad del 100% (cero campos perdidos, cero mutaciones silenciosas).

```powershell
# Ejecución de la suite de pruebas de conversión
.venv\Scripts\pytest.exe tests/adapters/test_converters.py -v
```

### Casos de prueba verificados:
- `test_roundtrip_system_message`: Conversión y reconstrucción de directivas de sistema.
- `test_roundtrip_user_message_with_external_flag`: Mensaje de usuario preservando metadatos locales.
- `test_roundtrip_assistant_parallel_tool_calls`: Asistente emitiendo múltiples llamadas a herramientas con argumentos JSON estructurados.
- `test_roundtrip_tool_result_success_and_error`: Resultado de herramienta con contenido y bandera `is_error=True`.
- `test_roundtrip_token_usage`: Normalización de métricas de tokens (`prompt_tokens`/`completion_tokens` $\to$ `input_tokens`/`output_tokens`).
- `test_fail_closed_on_invalid_json`: Lanzamiento estricto de `ValueError` ante argumentos JSON malformados (falla cerrada).

---

## 3. Escenario de Validación 2: Intercambiabilidad del Proveedor en el Consumidor (AC-02)

Verifica que un consumidor de prueba desacoplado (`TestAgentConsumer`) que utiliza únicamente la abstracción `Provider.complete(messages, tools)` puede alternar entre dos proveedores distintos (`FakeScriptedProvider` y `AlternativeMockProvider`) sin modificar una sola línea de código en el consumidor.

```powershell
# Ejecución de la prueba de intercambiabilidad
.venv\Scripts\pytest.exe tests/contracts/test_provider_interchangeability.py -v
```

### Comprobaciones del arnés:
1. El consumidor ejecuta un turno completo con el Proveedor A y procesa la respuesta.
2. La instancia se reemplaza por inyección con el Proveedor B.
3. El consumidor ejecuta el mismo turno sin alteraciones de código ni adaptaciones especiales.
4. Se verifica el cumplimiento del Principio de Sustitución de Liskov (LSP).

---

## 4. Escenario de Validación 3: Calidad Estática y Pureza Hexagonal

Garantiza que el código no introduce imports de SDKs externos en `core/` y cumple con tipado estricto.

```powershell
# 1. Verificación estricta de tipos
.venv\Scripts\mypy.exe src/harness_agent/core/ tests/

# 2. Análisis estático y formato
.venv\Scripts\ruff.exe check src/ tests/
.venv\Scripts\ruff.exe format --check src/ tests/

# 3. Test de fronteras arquitectónicas (Hexagonal)
.venv\Scripts\pytest.exe tests/architecture/test_core_boundaries.py -v
```
