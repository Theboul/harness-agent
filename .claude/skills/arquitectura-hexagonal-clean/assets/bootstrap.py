# bootstrap.py (único lugar que une todo)
def crear_agente(cfg):
    proveedor = LiteLLMProvider(cfg.modelo)
    almacen = SqliteSessionStore(cfg.ruta_db)
    bus = EventBus()
    return Agente(proveedor=proveedor, almacen=almacen, bus=bus, politica=PoliticaPermisos(cfg.reglas))
