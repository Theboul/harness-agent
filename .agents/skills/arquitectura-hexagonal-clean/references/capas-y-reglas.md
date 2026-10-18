# Idea central

- **Hexagonal (puertos y adaptadores):** el núcleo define interfaces (puertos) de lo que necesita; el mundo externo (modelo, base de datos, terminal, MCP) las implementa como adaptadores.
- **Clean Architecture:** las capas se ordenan por estabilidad y las dependencias solo apuntan hacia adentro. Lo que cambia más seguido (UI, proveedor) depende de lo que cambia menos (reglas).
- Los puertos son la frontera que hace cumplir la regla de dependencia.

# Capas del harness

| Capa Clean | En el harness | Puede importar |
|---|---|---|
| Entidades | `core/messages.py`, `core/events.py`, `core/errors.py` | nada del proyecto |
| Casos de uso | `core/loop.py`, `core/context/`, `core/permissions/`, `core/subagents/`, `core/limits.py` | entidades y puertos |
| Puertos | `core/ports.py`, interfaz `Tool` en `core/tools/` | entidades |
| Adaptadores | `adapters/`, `observability/` | núcleo (para implementar sus puertos) y bibliotecas externas |
| Interfaz | `cli/` | núcleo y su API pública |
| Raíz de composición | `bootstrap.py` | todo: único lugar que conecta |

```
cli ──┐
      ├──▶ core ◀── adapters
bootstrap ──▶ (ambos)
```

# Cómo diseñar un buen puerto

- Nombrarlo por el rol (`Provider`, `SessionStore`, `Approver`), no por la tecnología.
- Solo tipos del dominio en su firma; nunca tipos ni excepciones de un SDK.
- Pequeño y enfocado; si crece, partirlo.
- Documentar qué errores de dominio puede lanzar (`CuotaAgotada`, `TiempoAgotado`).
- Si no se puede falsear fácil, la interfaz está mal.

# Reglas específicas del harness

- **Eventos:** el núcleo emite al `EventBus`; la CLI (y mañana la web) se suscribe.
- **Aprobación humana:** el núcleo pide la decisión al puerto `Approver` y espera; la CLI lo implementa. La política vive en el núcleo y se aplica en el harness, no en el prompt.
- **Herramientas:** `Tool` y `ToolRegistry` en el núcleo; las concretas en `adapters/tools/`. Las MCP se traducen a `Tool` y pasan por la misma política.
- **Sesión:** cada evento se guarda al ocurrir vía `SessionStore`; compactar nunca borra el historial original.
- **Errores:** los adaptadores traducen errores externos a errores de dominio.
- **Contenido externo** (archivos, resultados de MCP): entra al contexto marcado como dato externo y nunca amplía permisos.
- **Subagentes:** otro caso de uso del núcleo; reciben solo el contexto pasado y devuelven un resultado estructurado.
- **Concurrencia:** si el núcleo es asíncrono, los puertos exponen `async` desde el diseño; no mezclar sin diseñarlo.
- **Tiempo, azar y entorno:** reloj, identificadores y variables de entorno se inyectan.

# Antipatrones

- `import litellm` (u otro SDK) dentro de `core/`.
- `print()` o `input()` en el núcleo.
- Un puerto que devuelve el objeto crudo del SDK.
- Un adaptador con reglas de negocio (permisos, límites, compactación).
- Un adaptador que importa de otro adaptador: coordinarlos es del núcleo o de `bootstrap.py`.
- Construir dependencias dentro de clases del núcleo (`self.db = sqlite3.connect(...)`).
- Una «utilidad» en `core/` que toca disco o red.
- Excepciones de implementación (`sqlite3.OperationalError`) que cruzan al núcleo.
- Saltarse el puerto «por esta vez» porque el plazo aprieta.

# Lista de comprobación por implementación

- [ ] ¿La regla de negocio está en `core/` y no en un adaptador?
- [ ] ¿Todo lo externo pasa por un puerto con tipos del dominio?
- [ ] ¿Los errores externos se traducen a errores de dominio?
- [ ] ¿Las dependencias se inyectan por constructor y se conectan solo en `bootstrap.py`?
- [ ] ¿El núcleo se probó con un adaptador falso, sin red ni disco?
- [ ] ¿El adaptador real tiene prueba de contrato?
- [ ] ¿Pasan `lint-imports` y el test de fronteras en Windows y Linux?
- [ ] ¿El núcleo emite eventos en lugar de imprimir?
- [ ] ¿Se respetan las decisiones de diseño del análisis (falla cerrada, historial intacto al compactar, secretos redactados)?
- [ ] ¿Otro integrante revisó el cambio?

# Cuándo se permite relajar la regla

Nunca dentro de `core/`. Si algo parece imposible sin romperla, falta un puerto: diseñarlo, no esquivarlo. La excepción razonable es `bootstrap.py`, que existe para conocer ambos lados.
