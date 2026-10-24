# Research: HU-03-02

Sin incógnitas abiertas; decisiones técnicas con alternativas.

| Tema | Decisión | Alternativas descartadas |
|---|---|---|
| Durabilidad | Diario de reversión por defecto con `synchronous = FULL` y un commit por evento | WAL con `synchronous = NORMAL` (puede perder el último commit ante un corte de energía; rompe la regla 1); WAL con FULL (archivos extra `-wal`/`-shm` y limpieza; sin necesidad medida) |
| Bloqueo de escritura | `BEGIN IMMEDIATE` al empezar | `BEGIN` diferido (dos procesos podrían leer el mismo `MAX(seq)` y chocar con `UNIQUE`); autoincremental global (no da orden por sesión) |
| Orden | `seq` por sesión asignado dentro de la transacción | Ordenar por fecha (se repite); `rowid` (no es por sesión ni sobrevive a limpiezas) |
| Contenido | JSON con `ensure_ascii=False` y `allow_nan=False` | `pickle` (inseguro y opaco); `repr` (no reversible); aceptar NaN (JSON inválido) |
| Sesión inexistente | Error de dominio (falla cerrada) | Crearla al vuelo como el doble (oculta errores de la raíz de composición) |
| Id repetido | Error de dominio tras comprobar dentro del bloqueo | Ignorar en silencio (idempotente pero oculta fallos); sobrescribir (viola la regla 1) |
| Prueba de corte | Proceso hijo con `os._exit`; para AC-02, un proxy de la conexión que sale en `commit` | Señales (`SIGKILL`) no existen en Windows; simular con excepciones (no corta el proceso) |
| Suscripción | Función `attach_event_recorder(bus, store)` sobre los puertos | Subclase del bus (acopla); decorador del bucle (toca `core/loop.py`, protegido) |
| Errores del recorder | Se propagan por el bus (`EventDeliveryError`) | Silenciarlos (perdería eventos sin avisar) |
