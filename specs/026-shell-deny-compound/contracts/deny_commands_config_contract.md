# Contrato: `[permissions] deny_commands` en `config.toml`

Ampliación **aditiva** del esquema de HU-00-04 y HU-05-01 (`specs/007-permission-policy/contracts/permissions_config_contract.md`). Dueño de `config.py`: B. Requiere su visto bueno (tarea humana).

```toml
[permissions]
deny = []                 # nombres de herramienta (HU-05-01, sin cambios)
ask = []                  # nombres de herramienta (HU-05-01, sin cambios)
# Comandos del shell que se añaden a la lista base de denegados de la plataforma. Solo añaden:
# la lista base no se puede quitar ni vaciar. Se escriben como el comando real.
# deny_commands = ["terraform destroy", "kubectl delete namespace"]
```

## Reglas

1. **Opcional**: sin el campo, o con `[]`, la lista en uso es exactamente la base (AC-01).
2. **Valor**: una lista de textos, cada uno no vacío, de hasta 500 caracteres y sin caracteres de control. Los duplicados se descartan conservando el orden. Si algo falla: `ConfigProblem("permissions.deny_commands", "debe ser una lista de comandos no vacíos, de hasta 500 caracteres y sin caracteres de control.")`. El mensaje no repite el valor.
3. **Solo añade**: no existe ningún campo para quitar, vaciar o sustituir la base. `allow_commands`, `replace`, `base`, `deny_commands_base` o cualquier otro nombre son campos desconocidos y detienen el arranque, como hoy (`campo desconocido en el esquema.`).
4. **Resultado**: `HarnessConfig.deny_commands: tuple[str, ...]` (por defecto `()`). **No** se guarda en `PermissionRules`, que sigue con `deny` y `ask` de nombres de herramienta.
5. **Compilación en el arranque**: `bootstrap.py` compila cada entrada con el dialecto del intérprete elegido. Si alguna no se entiende (una sustitución, varias partes, una regla con objetivo sin objetivo completo), el arranque se detiene con una línea en español que no repite el texto: `No se pudo iniciar: una entrada de permissions.deny_commands no se entiende para <bash|powershell>.`
6. **Coincidencia**: la misma que la base (FR-005). Una sola palabra coincide solo en la posición del programa; varias palabras, por programa y argumentos.
7. **Secretos**: el campo no tiene aspecto de clave. Un valor con aspecto de clave sigue la regla existente de `SecretInConfigFileError`.

## `config.example.toml`

Lleva la línea `# deny_commands = []` comentada bajo `[permissions]`, con dos líneas de explicación: «solo añade comandos a la lista base» y «se escriben como el comando real».
