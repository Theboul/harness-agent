# Contrato: sección `## Comandos` del archivo de la tarea

Ampliación **aditiva** del formato de `specs/021-task-protected-criteria/contracts/task_format.md`. Una tarea sin esta sección se analiza exactamente igual que antes.

```markdown
## Objetivo
El formulario de registro debe exigir el correo.

## Criterios de aceptación
- El correo es obligatorio
  - comando: python -m pytest tests/test_email.py
  - espera: codigo_salida == 0

## Comandos                       <!-- opcional; una vez; ≥ 1 comando si aparece -->
- pruebas: python -m pytest -q    <!-- columna 0; texto exacto que se permitirá -->
  - tiempo: 300                   <!-- opcional, con sangría; entero 1–600; por defecto 300 -->
- lint: python -m ruff check .
```

## Reglas del analizador

1. El nombre `Comandos` se compara sin distinguir mayúsculas ni espacios sobrantes, como el resto de secciones; repetido → `seccion_repetida`.
2. Un comando empieza con `- ` o `* ` en la columna 0, seguido de `pruebas:` o `lint:` (la clave no distingue mayúsculas) y un texto no vacío. El texto se guarda sin los espacios exteriores, con un máximo de 2 000 caracteres (más → `texto_demasiado_largo`).
3. `tiempo:` va con sangría bajo su comando (también como `- tiempo:`) y como mucho una vez por comando. Es un entero decimal de 1 a 600, sin signo ni decimales.
4. Con código `comando_no_valido` se rechaza: una clave distinta de `pruebas`/`lint`, una clave repetida, un comando vacío, un `tiempo:` sin comando o no válido, cualquier otra línea no vacía y una sección sin comandos.
5. Los mensajes son fijos y no incluyen el texto recibido. El mensaje de `seccion_desconocida` pasa a nombrar también «Comandos».
6. Los comandos de los criterios (`comando:` dentro de `## Criterios de aceptación`) **no** son comandos de esta sección y no se permiten automáticamente (FR-008a).

## Resultado

`TaskDefinition.commands`: tupla de `TaskCommand` en el orden del archivo, como mucho uno por tipo; `()` sin la sección.
