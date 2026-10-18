# Technical Research & Architectural Decisions: HU-00-01

**Feature**: Esqueleto del Repositorio e Interfaces Acordadas (HU-00-01)  
**Date**: 2026-10-17  
**Status**: Completed  

---

## 1. Technical Context & Packaging Architecture

### Decision: Layout de paquetes basado en `src/` y empaquetado estándar `pyproject.toml`
- **Decisión**: Estructurar el código bajo el directorio `src/harness_agent/` con submódulos independientes:
  - `src/harness_agent/core/`: Entidades de dominio, modelos canónicos, tipos e interfaces abstractas del núcleo. Sin dependencias externas.
  - `src/harness_agent/adapters/`: Paquetes preparados para las implementaciones concretas futuras (proveedores, SQLite, shell, MCP).
  - `src/harness_agent/cli/`: Interfaz de usuario de terminal y adaptador de consola.
  - `tests/`: Pruebas de contratos (`tests/contracts/`), dobles de prueba (`tests/doubles/`) y verificación de fronteras (`tests/architecture/`).
  - `pyproject.toml`: Configuración declarativa estándar (PEP 518/PEP 621) fijando `requires-python = ">=3.11"`.
- **Razón de ser**: El layout `src/` evita la importación accidental de código fuente no instalado durante la ejecución de pruebas y aísla el entorno de desarrollo tanto en Windows como en Linux.
- **Alternativas descartadas**:
  - *Layout plano en la raíz (`harness_agent/`)*: Rechazado porque genera ambigüedades de resolución de módulos entre `sys.path` local y el paquete empaquetado.

---

## 2. Abstraction Mechanism: Protocols vs. Abstract Base Classes (ABCs)

### Decision: Clases Base Abstractas (`abc.ABC` con `@abstractmethod`) combinadas con `typing.Protocol`
- **Decisión**: Implementar los contratos centrales como clases base abstractas explícitas (`abc.ABC`) con decoradores `@abstractmethod` y type hints estrictos. Para interfaces consumidoras donde se favorezca el tipado estructural en dobles de prueba, habilitar `@runtime_checkable` Protocols.
- **Razón de ser**: Las ABCs proporcionan validación estricta en tiempo de instanciación en Python (impidiendo instanciar una subclase o doble que olvide implementar un método abstracto), asegurando que los desarrolladores A, B y C cumplan 100 % el contrato acordado.
- **Alternativas descartadas**:
  - *Duck typing puro sin clases base*: Rechazado por carecer de validación estática temprana y violar el Principio III (código fuertemente tipado).
  - *Solo Protocols*: Si bien son flexibles, no previenen instanciaciones directas erróneas si no se complementan con comprobaciones estáticas continuas.

---

## 3. Concurrency & Asynchrony Model (Provisional Status: SPK-02)

### Decision: Asincronía provisional focalizada (`async def`) para operaciones de E/S externa
- **Decisión**: Declarar con firmas asíncronas (`async def`) las operaciones intrínsecamente ligadas a E/S externa y latencia:
  - `Provider.complete(mensajes, herramientas) -> ProviderResponse`
  - `Tool.run(args) -> ToolResult`
  - `Approver.request(call, details) -> ApprovalResult` (obligatorio por V-01)
  - `SubagentRunner.execute(...) -> SubagentResult`
  - `McpClient.connect()`, `McpClient.call_tool(...)`
  Mantener como síncronas (`def`) las interfaces locales y de almacenamiento transaccional:
  - `SessionStore`, `MemoryStore`, `AuthorizedArea`, `TaskCriteria`, `PermissionPolicy`, `EventBus`.
- **Estado de provisionalidad**:
  > **[PROVISIONAL - SPK-02]**: Este modelo de asincronía es provisional. No se implementa lógica de concurrencia avanzada, tareas paralelas ni manejo de cancelación hasta que el spike `SPK-02` (Sprint 1) determine formalmente las garantías de `asyncio` y cancelación de herramientas.
- **Razón de ser**: Permite a B y C escribir adaptadores y dobles de prueba sin bloquearse, satisfaciendo V-01 (aprobación asíncrona bidireccional) sin sobre-complejizar los almacenes de datos.

---

## 4. Message Format & Event Catalog (Provisional Status: SPK-01 / Sp1-03)

### Decision: Dataclasses inmutables para mensajes y enumerados estrictos para eventos
- **Decisión**:
  - Modelo de mensajes: `@dataclass(frozen=True)` para `Message`, `ToolCall`, `ToolResult` y `TokenUsage`, garantizando inmutabilidad dentro del bucle.
  - Catálogo de eventos: `Enum` canónico para los 17 eventos de bus especificados en `docs/02-arquitectura.md`.
- **Estado de provisionalidad**:
  > **[PROVISIONAL - SPK-01 / Sp1-03]**: Las estructuras exactas de traducción entre llamadas de herramientas (OpenAI vs. Anthropic) dependen del spike `SPK-01`. La aprobación formal del catálogo y formatos queda sujeta a la reunión de consenso de los tres integrantes (`Sp1-03`). Ninguna decisión de formato se considera ratificada definitivamente hasta entonces.

---

## 5. Verification Strategy: AC-01 and AC-02

### Decision: Pruebas unitarias de conformidad de contratos y prueba estática de fronteras (AST)
- **AC-01 (Contratos importables con dobles)**:
  - Se proveen dobles de prueba canónicos en `tests/doubles/` (`DummyProvider`, `DummyTool`, `DummyApprover`, `InMemorySessionStore`, `RecordingEventBus`).
  - Una suite de pruebas unitarias (`tests/contracts/test_contracts.py`) verifica que se pueden instanciar, heredar e invocar respetando las firmas asíncronas y síncronas sin necesidad de red ni dependencias pesadas.
- **AC-02 (Cero SDKs de proveedores en el núcleo)**:
  - Se implementa una prueba automatizada basada en el módulo `ast` de la biblioteca estándar de Python (`tests/architecture/test_core_boundaries.py`).
  - La prueba analiza todos los nodos `Import` e `ImportFrom` en el árbol de archivos `src/harness_agent/core/` y falla si detecta cualquier módulo prohibido (`litellm`, `openai`, `anthropic`, `google-genai`, etc.).
- **Razón de ser**: Garantiza cumplimiento 100 % automatizado de los dos criterios de aceptación obligatorios desde el primer commit, integrable en cualquier pipeline de CI futuro.
