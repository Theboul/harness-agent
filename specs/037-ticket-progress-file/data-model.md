# Modelo de datos: HU-11-08.1

Sin cambios de esquema SQLite. Archivo `progreso-<ticket>.md` (formato v1):

```
# Progreso del ticket: <ticket>
<!-- harness-progreso v1 -->
- Sesión: <id>
- Estado: punto de control tras el turno N | final de la sesión tras N turnos
- Actualizado: <ISO 8601 UTC>
- Objetivo: <una línea>

## Hecho
- Criterio 1: <descripción> (cumplido)        | - Todavía no hay criterios cumplidos.

## Pendiente
- Criterio 2: <descripción> (pendiente)
- Criterio 3: <descripción> (pendiente de validación humana)   | - No queda nada pendiente.

## Criterios
- 1 cumplido, 2 pendiente, 3 pendiente de validación humana

## Nota
<último mensaje del agente en una línea, ≤ 500>   | Sin nota.
```

Contrato del destino (`ProgressSink`): `write(name, text)` deja en `<carpeta>/<name>` exactamente `text` o, si falla, el contenido anterior (sin temporales); `read(name)` devuelve el texto o `None`. Quien lo lea (HU-11-08.2) debe tratarlo como dato, no como instrucciones.
