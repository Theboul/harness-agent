# Quickstart: validar HU-00-04 — Configuración por archivo y variables de entorno

**Fecha**: 2026-10-20 | **Plan**: [plan.md](plan.md) | **Contrato**: [contracts/config_loading_contract.md](contracts/config_loading_contract.md) | **Modelo**: [data-model.md](data-model.md)

Guía para comprobar que la historia funciona de punta a punta una vez implementada. No contiene código de implementación; el detalle por microtarea irá en `tasks.md`.

## Requisitos previos

- Python 3.12, única versión soportada (PD-07).
- Dependencias de desarrollo fijadas, desde la raíz del repositorio:

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e . --no-deps
```

- `git` instalado (lo usa la comprobación de AC-02).

No hacen falta red, claves de API ni proveedor real.

## 1. Ejecutar las pruebas de la historia

```bash
pytest tests/unit tests/architecture
```

Resultado esperado: todas pasan. Cada escenario del spec tiene una prueba:

| Escenario del spec | Archivo de prueba |
|---|---|
| US1 / AC-01 — otro modelo desde el archivo, límites y rutas, valores inválidos, campos desconocidos, inmutabilidad | `tests/unit/test_config_schema.py` |
| US1 — ubicación (`config.toml`, `HARNESS_CONFIG`, parámetro), archivo inexistente, ilegible o roto, UTF-8 y CRLF | `tests/unit/test_config_location.py` |
| US2 — clave solo del entorno, variable ausente, campo de clave en el archivo, centinela sin filtraciones | `tests/unit/test_config_keys.py` |
| US2 — `Secret` y textos de los errores sin valores | `tests/unit/test_config_secret.py` |
| US3 — plantillas sin secretos y sincronizadas con el esquema | `tests/unit/test_config_templates.py` |
| US3 / AC-02 — ningún secreto en los archivos versionados | `tests/architecture/test_no_secrets_in_repo.py` |
| US4 — el núcleo no lee archivos ni entorno | `tests/architecture/test_core_reads_no_config.py` |

## 2. Puertas de calidad (las mismas de la CI)

```bash
ruff format --check .
ruff check .
mypy src tests
pytest --cov=harness_agent --cov-report=term-missing
```

Resultado esperado: sin diferencias de formato, sin avisos de `ruff`, `mypy --strict` limpio y toda la suite en verde. Debe cumplirse en Windows y en Linux (la matriz de CI lo ejecuta).

## 3. Comprobar que no se tocaron los puertos

```bash
git diff --exit-code -- src/harness_agent/core/interfaces
```

Resultado esperado: sin salida y código de salida 0. También `git status --short src/harness_agent/core/interfaces` debe estar vacío.

## 4. AC-02: ninguna clave en archivos ni en el historial

**4.1 Archivos versionados (automático).** Lo hace `tests/architecture/test_no_secrets_in_repo.py` dentro de la suite del punto 1. Para ejecutarlo solo:

```bash
pytest tests/architecture/test_no_secrets_in_repo.py
```

Resultado esperado: pasa (0 archivos con nombre de secreto y 0 coincidencias). Si no hay repositorio o `git`, se salta con un motivo, salvo en la CI, donde fallaría.

**4.2 Historial de cambios (manual).** La CI hace una copia superficial del repositorio, así que esta comprobación se hace a mano y se registra en `docs/PROGRESO.md` con la fecha, la versión de `git` y el resultado. Desde la raíz de un clon **completo** (en una copia superficial, hacer antes `git fetch --unshallow`):

```bash
# 1) Formas conocidas de clave (OpenAI/Anthropic sk-, AWS, Google, GitHub, Slack, claves privadas)
git log --all --oneline -G 'sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{36,}|xox[abprs]-[A-Za-z0-9-]{10,}|BEGIN [A-Z ]*PRIVATE KEY'

# 2) Asignaciones del tipo «clave = valor largo»
git log --all --oneline -i -G '(api[_-]?key|secret|token|password|passwd)[[:space:]]*[:=][[:space:]]*[^[:space:]]{17,}'

# 3) Archivos de secretos que hayan existido alguna vez
git log --all --name-only --pretty=format: -- .env config.toml '*.pem' '*.key' | sort -u
```

En PowerShell las mismas órdenes funcionan guardando cada patrón en una variable entre comillas simples (`$p = '...'`) y escribiendo `git log --all --oneline -G $p` (y `-i -G $p` para la segunda); en la tercera, sustituir `| sort -u` por `| Where-Object { $_ } | Sort-Object -Unique`.

Resultado esperado: **ninguna salida** en las tres órdenes. Estas órdenes se comprobaron el 2026-10-20 (git 2.49.0): detectan una clave sintética en un repositorio temporal con las tres órdenes y dan 0 en este repositorio con todas sus ramas.

**Si aparece alguna coincidencia**: (1) considerar la clave **comprometida** y revocarla en el proveedor de inmediato; (2) emitir una clave nueva y definirla solo en el entorno; (3) anotar el hallazgo y la rotación en `docs/PROGRESO.md`. Reescribir el historial queda fuera de esta historia: se decide aparte, con el equipo.

## 5. Recorrido manual opcional (demostración AC-01 / AC-02)

Con un intérprete de Python abierto en la raíz del repositorio (con el paquete instalado) y un directorio temporal vacío como directorio de trabajo:

1. Copiar `config.example.toml` a `config.toml` en ese directorio y cargar la configuración con `load_config()` (con `HARNESS_CONFIG` sin definir): devuelve el modelo del ejemplo, los límites por defecto y `api_key` vacía, porque el modelo de ejemplo es del proveedor simulado.
2. Cambiar en el archivo solo la línea `model` por `anthropic/…` (cualquier nombre de modelo) **sin definir** `ANTHROPIC_API_KEY` y cargar de nuevo: lanza `MissingKeyError` y su texto nombra `ANTHROPIC_API_KEY` y no muestra ningún valor (AC-01 y flujo 4 de la historia).
3. Definir `ANTHROPIC_API_KEY` con un valor de prueba reconocible (por ejemplo, `VALOR-DE-PRUEBA-123`) y cargar otra vez: el modelo es el nuevo y `repr(config)` muestra `<secreto oculto>`; el valor de prueba no aparece en ninguna salida (solo `config.api_key.reveal()` lo devuelve).
4. Añadir al archivo un campo `api_key = "x"`: la carga lanza `SecretInConfigFileError` que nombra el campo y no reproduce su valor. Quitar el campo.
5. Añadir `limites = 3` y `limits.max_turns = 0`: la carga lanza `InvalidConfigError` que enumera **ambos** problemas, cada uno con su campo.
6. Borrar `config.toml` y cargar: lanza `ConfigFileNotFoundError` que nombra la ruta y cómo indicar otra; definir `HARNESS_CONFIG` con la ruta de otro archivo válido y cargar de nuevo: usa ese archivo; pasar un `path` explícito distinto: gana el parámetro.
7. Escribir un `config.toml` con sintaxis rota: la carga lanza `ConfigSyntaxError` con la línea, sin reproducir el contenido.
8. Revisar `git status --short` en el repositorio: `config.toml` y `.env` no aparecen aunque existan (están ignorados) y las plantillas sí están versionadas.

Cargar las claves de `.env.example` en el entorno de la sesión (el sistema no lee `.env`; D4 del plan):

```powershell
# PowerShell: carga cada línea CLAVE=valor de .env en el entorno de la sesión
Get-Content .env | Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*=' } | ForEach-Object { $k, $v = $_ -split '=', 2; Set-Item -Path "Env:$k" -Value $v }
```
```bash
# bash: exporta todas las variables de .env
set -a; . ./.env; set +a
```

## Nota para quien construya la raíz de composición

`load_config()` no recibe más argumentos que la ubicación opcional, así que conectarlo en `bootstrap.py` será una línea al arrancar (la crea la historia del bucle o de la CLI, no esta). La CLI (HU-06-01) pasará su argumento de terminal como `path`. Cada historia consumidora recibirá solo su parte de `HarnessConfig` y nunca llamará a `load_config` ni leerá el entorno.

## Criterios de «listo» para esta historia

- [ ] Las pruebas de los puntos 1 y 2 pasan en Windows y Linux.
- [ ] El punto 3 no muestra cambios en los puertos.
- [ ] El punto 4.1 pasa y el punto 4.2 se ejecutó y su resultado está registrado en `docs/PROGRESO.md`.
- [ ] El recorrido del punto 5 produce lo descrito en cada paso.
