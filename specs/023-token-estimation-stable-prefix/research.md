# Research: HU-02-01

Sin `NEEDS CLARIFICATION` pendientes. Decisiones de diseño:

## D1. Heurística de estimación

- **Decision**: `ceil(len(texto) / 4)`; el mensaje suma contenido, nombre y argumentos serializados (JSON con claves ordenadas) de cada llamada, contenido del resultado de herramienta, más una constante fija por mensaje (4 tokens de sobrecarga de rol) para no subestimar historiales de muchos mensajes cortos.
- **Rationale**: Es la regla práctica habitual (≈4 caracteres por token en inglés y código), barata y determinista; el factor de calibración absorbe el error del modelo concreto. El núcleo no puede usar un tokenizador de terceros.
- **Alternatives**: `tiktoken` (dependencia y descarga de datos, prohibido en `core/`); palabras × 1,3 (peor con código); sin sobrecarga por mensaje (subestima).

## D2. Corrección con el consumo real

- **Decision**: factor por sesión = `reportado_entrada / crudo_enviado`, acotado a [0,25 ; 4,0]; la estimación calibrada es `ceil(crudo × factor)`. Se usa la última observación (no un promedio).
- **Rationale**: AC-02 pide que la estimación «se corrija con ese valor»: con la última observación, la misma entrada vuelve a estimarse igual al consumo real. El tope evita que un informe anómalo (caché, cero, error) vuelva inútil la estimación.
- **Alternatives**: media móvil exponencial (converge más despacio y el AC pide corregir con el valor); anclar en el consumo y sumar solo lo nuevo (más preciso, pero exige conocer qué parte del historial era cubierta por el informe; queda como mejora para HU-02-03).

## D3. Qué entra en el prefijo y dónde

- **Decision**: un mensaje `SYSTEM` con secciones en orden fijo (instrucciones, reglas, entorno: sistema operativo e intérprete) y las definiciones en el argumento `tools`, ordenadas por nombre. La descripción de herramientas **no** se duplica en el texto del mensaje.
- **Rationale**: Los proveedores reciben las herramientas aparte; duplicarlas gastaría tokens. El orden determinista asegura prefijo idéntico aunque el registro cambie de orden.
- **Alternatives**: volcar las herramientas en el texto (doble costo); varios mensajes de sistema (más superficie para variar).

## D4. Congelar el prefijo

- **Decision**: el primer `assemble` de una sesión construye y guarda el prefijo; los siguientes lo reutilizan aunque cambien las fuentes. Una sesión nueva toma lo vigente.
- **Rationale**: Regla 2 («no cambia dentro de la sesión»).
- **Alternatives**: recalcular siempre y comparar huellas (no cumple la regla si la herramienta cambia).

## D5. Qué no se implementa

- `ContextManager` completo, compactación, memoria, bloque esencial, archivo de instrucciones y umbral por modelo, por dependencias de HU-02-03, HU-02-06.1, HU-02-07 y del acuerdo sobre el puerto (SPK-03 §6).
