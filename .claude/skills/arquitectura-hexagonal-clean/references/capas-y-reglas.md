# Idea central

- **Hexagonal (puertos y adaptadores):** el núcleo define interfaces (puertos) de lo que necesita; el mundo externo (modelo, base de datos, terminal, MCP) las implementa como adaptadores.
- **Clean Architecture:** las capas se ordenan por estabilidad y las dependencias solo apuntan hacia adentro. Lo que cambia más seguido (UI, proveedor) depende de lo que cambia menos (reglas).
- Los puertos son la frontera que hace cumplir la regla de dependencia.

# Capas del harness

| Capa Clean | En el harness | Puede importar |
|---|---|---|
| Entidades | `core/entities.py`, `core/events.py`; errores de dominio en el `errors.py` de cada subpaquete (`core/tools/errors.py`) | biblioteca estándar |
| Puertos | `core/interfaces/` (`provider.py`, `tool.py`, `security.py`, `storage.py`, `context.py`, `system.py`, `connections.py`, `event_bus.py`) | entidades |
| Casos de uso y reglas | `core/loop.py`, `core/tools/`, `core/permissions/`, `core/in_memory_event_bus.py`; planeados: `core/limits.py`, `core/context/`, `core/subagents/` | entidades, puertos y otros módulos de `harness_agent.core` |
| Adaptadores | `adapters/` (`converters/`, `providers/`, `storage/`, `tools/`, `system/`, `mcp/` hoy), `observability/` (planeado) | núcleo (API pública) y bibliotecas externas |
| Configuración | `config.py` | biblioteca estándar y API pública del núcleo (p. ej. `PermissionRules`) |
| Interfaz | `cli/` | biblioteca estándar y API pública del núcleo (`from harness_agent.core import ...`) |
| Raíz de composición | `bootstrap.py` (planeado) | todo: único lugar que conecta |

```
cli ──┐                   config.py ──▶ core
      ├──▶ core ◀── adapters
bootstrap ──▶ (todos)
```

# Cómo diseñar un buen puerto

- Clase `ABC` en `core/interfaces/<dominio>.py`, reexportada en `core/interfaces/__init__.py` y `core/__init__.py`.
- Nombrarlo por el rol en inglés (`Provider`, `SessionStore`, `Approver`), no por la tecnología.
- Solo tipos del dominio en su firma; nunca tipos ni excepciones de un SDK.
- Pequeño y enfocado; si crece, partirlo.
- Documentar qué errores de dominio puede lanzar (por ejemplo, `ToolRegistry` declara `ValueError` y `core/tools/errors.py` los especializa).
- `async` si hace E/S que puede tardar o cancelarse (D-01).
- Si no se puede falsear fácil con un doble en `tests/doubles/`, la interfaz está mal.
- Cambiarlo exige acuerdo de A, B y C (contratos de HU-00-01).

# Reglas específicas del harness

- **Eventos:** el núcleo emite al `EventBus` (17 tipos de `core/events.py`); la CLI (y mañana la web) se suscribe. Las cargas no incluyen argumentos ni contenido sensible.
- **Aprobación humana:** el núcleo pide la decisión al puerto `Approver` y espera; la CLI lo implementará (HU-05-03). Hasta entonces `AgentLoop` resuelve «preguntar» como denegado con motivo. La política vive en el núcleo (`core/permissions/`) y se aplica en el harness, no en el prompt.
- **Herramientas:** `Tool` y `ToolRegistry` en `core/interfaces/tool.py`, registro y validación en `core/tools/`; las concretas en `adapters/tools/`. Las MCP se traducen a `Tool` y pasan por la misma política.
- **Permisos:** denegar > preguntar > permitir; todo «permitir» pasa por `AuthorizedArea.contains(path)`; la configuración solo puede endurecer (`deny`, `ask`), nunca permitir.
- **Sesión:** cada evento se guarda al ocurrir vía `SessionStore`; compactar nunca borra el historial original.
- **Errores:** los adaptadores traducen errores externos a errores de dominio; los mensajes de error no reproducen valores recibidos.
- **Contenido externo** (archivos, resultados de MCP): entra al contexto con `is_external=True` y nunca amplía permisos.
- **Subagentes:** otro caso de uso del núcleo; reciben solo el contexto pasado y devuelven un resultado estructurado (`SubagentResult`).
- **Concurrencia:** asyncio con cancelación limpia (D-01); `CancelledError` y `KeyboardInterrupt` nunca se tragan.
- **Tiempo, azar, entorno y configuración:** se inyectan; `core/` no lee archivos ni variables de entorno.

# Antipatrones

- `import litellm` (u otro SDK) dentro de `core/`.
- `print()`, `input()` o `sys.stdout` en el núcleo.
- `from harness_agent.config import ...` u `os.environ` dentro de `core/`.
- Importar un submódulo del núcleo desde `cli/` (`harness_agent.core.loop`) en vez de la API pública.
- Un puerto que devuelve el objeto crudo del SDK.
- Un adaptador con reglas de negocio (permisos, límites, compactación).
- Un adaptador que importa de otro adaptador: coordinarlos es del núcleo o de `bootstrap.py`.
- Construir dependencias dentro de clases del núcleo (`self.db = sqlite3.connect(...)`).
- Una «utilidad» en `core/` que toca disco o red.
- Excepciones de implementación (`sqlite3.OperationalError`) que cruzan al núcleo.
- Cambiar un puerto, una entidad o el catálogo de eventos sin acuerdo de A, B y C.
- Saltarse el puerto «por esta vez» porque el plazo aprieta.

# Lista de comprobación por implementación

- [ ] ¿La regla de negocio está en `core/` y no en un adaptador?
- [ ] ¿Todo lo externo pasa por un puerto de `core/interfaces/` con tipos del dominio?
- [ ] ¿Los puertos, entidades y eventos siguen sin cambios (o el cambio tiene acuerdo de A, B y C)?
- [ ] ¿Los errores externos se traducen a errores de dominio, sin reproducir valores recibidos?
- [ ] ¿Las dependencias se inyectan por constructor y se conectan solo en `bootstrap.py` (o en la prueba de integración)?
- [ ] ¿El núcleo se probó con dobles, sin red, disco ni claves?
- [ ] ¿El adaptador real tiene prueba de contrato en `tests/contracts/`?
- [ ] ¿Pasa `pytest tests/architecture` (y la guarda nueva del módulo) en Windows y Linux?
- [ ] ¿El núcleo emite eventos en lugar de imprimir?
- [ ] ¿Lo público está exportado en `core/__init__.py` y los consumidores importan de `harness_agent.core`?
- [ ] ¿Se respetan las decisiones de diseño (falla cerrada, historial intacto al compactar, secretos redactados)?
- [ ] ¿Otro integrante revisó el cambio?

# Cuándo se permite relajar la regla

Nunca dentro de `core/`. Si algo parece imposible sin romperla, falta un puerto: diseñarlo, no esquivarlo. La excepción razonable es `bootstrap.py`, que existe para conocer todos los lados.
