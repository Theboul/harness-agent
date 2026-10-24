# Hallazgos de SPK-01: traducir herramientas entre OpenAI y Anthropic con LiteLLM

**Fecha**: 2026-10-24  
**Estado**: **Parcial.** AC-01 se verificó sin red (LiteLLM real, transporte sustituido); falta una corrida con claves reales, que depende de D-IA.  
**Autor**: Integrante B — Estado (Sp1-46 y Sp1-47)  
**Trazabilidad**: [SPK-01](../04d-historias-conexiones.md#spk-01) · AC-01 · alimenta [HU-07-01](../04d-historias-conexiones.md#hu-07-01) y HU-07-02  
**Código y pruebas**: [tests/spikes/test_litellm_tool_translation_spike.py](../../tests/spikes/test_litellm_tool_translation_spike.py) · [specs/016-litellm-tool-translation-spike/](../../specs/016-litellm-tool-translation-spike/)

---

## 1. Qué se hizo y qué no

LiteLLM 1.106.2 construye la petición HTTP real para cada proveedor. Se sustituyó solo el transporte: la petición se captura y se devuelve una respuesta **nativa de cada proveedor escrita a mano** según su formato documentado. Un guardia de red hace fallar la prueba si algo intenta resolver un nombre o abrir una conexión.

| Comprobado | No comprobado |
|---|---|
| Qué envía LiteLLM a cada proveedor para la misma herramienta | Que un modelo real decida llamar a la herramienta |
| Cómo normaliza LiteLLM llamadas, identificadores, motivo de parada y consumo | Calidad de los argumentos que genera cada modelo |
| Cómo viaja el resultado de vuelta (incluido uno con error) | Errores, límites de tasa y tiempos de espera reales |
| Llamadas paralelas (dos en una respuesta) y texto junto a las llamadas | *Streaming*, `tool_choice` y esquemas con características avanzadas |

Las respuestas simuladas son **supuestos nuestros** sobre el formato de cada API, no capturas. Por eso AC-01 queda parcial: «llamadas equivalentes» está probado para la traducción de LiteLLM, no para el comportamiento de los modelos. Para cerrarlo hace falta una corrida real de pocos tokens (decisión D-IA abierta).

## 2. Diferencias que afectan al formato interno

| # | Tema | OpenAI | Anthropic | Consecuencia para el formato interno |
|---|---|---|---|---|
| 1 | Definición de herramienta | `{"type": "function", "function": {name, description, parameters}}`, sin cambios | `{name, description, input_schema, type: "custom"}`; el esquema JSON pasa intacto | Un solo esquema canónico basta: LiteLLM hace la traducción |
| 2 | Argumentos de una llamada | Cadena JSON (`function.arguments`) | Objeto en el proveedor; LiteLLM lo devuelve **también como cadena JSON** | Ya llegan como cadena en ambos: el adaptador debe `json.loads` y tratar el JSON inválido como `[invalid_arguments]` (no probado aquí) |
| 3 | Identificador de llamada | `call_…` | `toolu_…` | Tratar el id como opaco: no validar prefijo ni longitud. Se conserva y vuelve sin cambios en el resultado |
| 4 | Motivo de parada | `tool_calls` / `stop` | `tool_use` / `end_turn`, normalizados por LiteLLM a `tool_calls` / `stop` | Sin diferencia visible tras LiteLLM |
| 5 | Consumo | `prompt_tokens`, `completion_tokens` | `input_tokens`, `output_tokens`, normalizados | Sin diferencia visible tras LiteLLM |
| 6 | Texto junto a las llamadas | `content` con texto y `tool_calls` | Bloque `text` más bloques `tool_use` | Ambos devuelven el texto en `content`; conservarlo en el mensaje del asistente |
| 7 | Resultados de varias llamadas | Un mensaje `role: tool` por resultado | **Un solo mensaje `user`** con un bloque `tool_result` por llamada (LiteLLM los fusiona) | Un `ToolResult` por mensaje `TOOL` en el formato canónico sirve para ambos |
| 8 | **Error de herramienta** | Sin campo estándar; LiteLLM reenvía `is_error` como campo extra sin tipo | LiteLLM **descarta** `is_error`: el `tool_result` solo lleva el texto | `ToolResult.is_error` **no viaja** por LiteLLM. Hay que codificar el error en el contenido (p. ej. con las etiquetas `[…]` que ya usa el bucle) o aceptar que el modelo no lo distingue |
| 9 | `max_tokens` | Opcional | LiteLLM lo rellena con **64 000** si no se indica | Fijarlo siempre desde la configuración; si no, cada llamada a Anthropic pide un máximo enorme |
| 10 | Numeración de llamadas | Sin `index` | LiteLLM añade `index` 1, 2… (empieza en 1 cuando hay texto antes) | Ignorar `index`; usar el orden de la lista |
| 11 | Campos extra en mensajes de LiteLLM | `provider_specific_fields: {"refusal": null}` aparece al volver a serializar un mensaje de respuesta y se reenvía | — | Construir cada petición desde los mensajes canónicos; **nunca** reenviar el objeto de respuesta de LiteLLM (`model_dump`) |

## 3. Costo y fricciones de la dependencia

Medido en un entorno limpio con Python 3.12.10 sobre Windows:

- Con `litellm`, `mcp` y las dependencias de desarrollo el entorno queda en 84 paquetes y unos 382 MB; `import litellm` tarda unos 3,8 s.
- `litellm.completion` importa `mcp` al llamar, pero `litellm` solo lo declara como extra (`litellm[mcp]`): con la instalación básica falla con `ModuleNotFoundError`.
- Con una ruta larga de entorno virtual en Windows, la instalación **omitió archivos sin avisar** (faltaba `litellm/llms/custom_httpx`). Con una ruta corta funciona. Es el mismo límite de 260 caracteres que afecta a `test_list_files`.
- Al importarse, LiteLLM intenta descargar su tabla de precios; `LITELLM_LOCAL_MODEL_COST_MAP=True` usa la copia incluida y evita la red.
- Con un cliente `openai` sin transporte sustituido, la prueba hizo una conexión real con una clave falsa: cualquier prueba de HU-07-02 debe inyectar el transporte.

El proyecto no tiene dependencias de ejecución (`dependencies = []`). Añadir `litellm` en HU-07-02 cambia `pyproject.toml`, los requisitos y la CI, y por tanto **requiere acuerdo de A, B y C** (skill `verificar-fronteras-hexagonales`). Este spike no lo añade a la CI: la prueba se omite si `litellm` no está instalado.

## 4. Recomendaciones

Para HU-07-01 (A): id opaco; sin `is_error` en la traducción (codificarlo en el contenido); un mensaje `TOOL` por resultado; argumentos como diccionario ya analizado.

Para HU-07-02 (B): fijar `max_tokens`; construir las peticiones desde el formato canónico; transporte inyectable en las pruebas; confirmar con el equipo la dependencia y sus extras (`mcp`) antes de añadirla.

## 5. Pendiente

1. Corrida con claves reales de pocos tokens para cerrar AC-01 (depende de D-IA: proveedores y presupuesto). Las claves irían solo como variables de entorno.
2. Revisión cruzada por A o C.
3. Probar el JSON de argumentos inválido, `tool_choice` y *streaming* si HU-07-02 los necesita.

## 6. Cómo reproducir

```bash
python -m venv C:/tmp/spk01v            # ruta corta en Windows
C:/tmp/spk01v/Scripts/python.exe -m pip install -r requirements-dev.txt litellm mcp
C:/tmp/spk01v/Scripts/python.exe -m pytest tests/spikes/test_litellm_tool_translation_spike.py --no-cov
```
