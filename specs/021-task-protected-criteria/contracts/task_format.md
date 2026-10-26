# Contrato: formato de la tarea (Markdown)

```markdown
# TAREA-14: Validar el correo         <!-- opcional; un solo «# » -->

## Objetivo                           <!-- obligatoria, con texto -->
El formulario de registro debe exigir el correo.

## Contexto                           <!-- opcional -->
Formulario en `src/forms/signup.py`.

## Reglas                             <!-- opcional -->
- No cambiar la API pública.

## Criterios de aceptación            <!-- obligatoria (alias: «## Criterios»), ≥ 1 criterio -->
- El correo es obligatorio
  - comando: pytest tests/test_email.py
  - espera: codigo_salida == 0
- El mensaje de error es claro
```

## Reglas del analizador (`parse_task(text) -> TaskDefinition`)

1. Los nombres de sección se comparan sin distinguir mayúsculas ni espacios sobrantes; cada una puede aparecer una vez; otra `## ` distinta de las cuatro (más el alias) se rechaza.
2. Un criterio empieza con `- ` o `* ` en la columna 0. Sus líneas `comando:` y `espera:` van con sangría (también como `- comando:`). Cualquier otra línea no vacía dentro de la sección de criterios se rechaza.
3. `comando:` y `espera:` van juntos o ninguno; repetidos se rechazan. Sin comando, el criterio es semántico.
4. El texto antes del primer encabezado se ignora solo si está en blanco; si no, se rechaza.
5. Se rechazan caracteres de control (salvo `\n`, `\t`, `\r`), texto vacío o mayor que el límite, más de 100 criterios, campos de más de 2 000 caracteres.
6. Los mensajes de error son fijos y no incluyen el texto recibido.
