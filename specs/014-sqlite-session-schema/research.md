# Research: HU-03-01

Sin incógnitas abiertas; decisiones técnicas con sus alternativas.

| Tema | Decisión | Alternativas descartadas |
|---|---|---|
| Versión de esquema | `PRAGMA user_version` | Tabla `schema_meta` (más piezas sin necesidad); herramienta de migraciones externa (dependencia nueva) |
| Identificador | `uuid4` en texto, inyectable | Entero autoincremental (no es único entre bases); ULID (dependencia) |
| Fecha | ISO-8601 UTC con zona en `TEXT` | Epoch entero (menos legible al auditar); adaptadores de fecha de `sqlite3` (obsoletos en 3.12) |
| Estado | `CHECK (status IN ('active','completed','interrupted'))` | Tabla de estados (excesivo); texto libre (no falla cerrada) |
| Padre inexistente | Consulta previa más clave foránea | Solo clave foránea (el mensaje no distingue la causa) |
| Conexión | Una por almacén, escritura dentro de `with conn:` | Conexión por operación (no sirve para `:memory:`); pool (innecesario) |
| Herencia de `SessionStore` | Pospuesta a HU-03-02 | Métodos que lanzan `NotImplementedError` (violan el contrato en silencio) |
| `create_session` en el puerto | No; hallazgo para A, B y C | Ampliar el puerto ahora (contrato protegido) |
| Modo WAL y `synchronous` | Fuera; HU-03-02 | Activarlos aquí (adelanta la historia siguiente) |
