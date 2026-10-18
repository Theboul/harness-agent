import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2] / "src" / "harness_agent"
CORE = RAIZ / "core"
PROHIBIDOS = (
    "harness_agent.adapters", "harness_agent.cli", "harness_agent.observability", "harness_agent.bootstrap",
    "litellm", "openai", "anthropic", "google", "mcp", "sqlite3",
    "typer", "click", "rich",
)


def _modulo_de(path: Path) -> list[str]:
    rel = path.relative_to(RAIZ.parent).with_suffix("")
    return list(rel.parts[:-1]) if path.name == "__init__.py" else list(rel.parts)


def _imports(path: Path):
    pkg = _modulo_de(path)[:-1] if path.name != "__init__.py" else _modulo_de(path)
    arbol = ast.parse(path.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for a in nodo.names:
                yield a.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = pkg[: len(pkg) - (nodo.level - 1)]
                yield ".".join(base + ([nodo.module] if nodo.module else []))
            elif nodo.module:
                yield nodo.module


def _prohibido(nombre: str) -> bool:
    return any(nombre == p or nombre.startswith(p + ".") for p in PROHIBIDOS)


def test_el_nucleo_no_importa_de_fuera():
    violaciones = []
    for archivo in CORE.rglob("*.py"):
        for nombre in _imports(archivo):
            if _prohibido(nombre):
                violaciones.append(f"{archivo.relative_to(RAIZ)} importa {nombre}")
    assert not violaciones, "Fronteras rotas:\n" + "\n".join(violaciones)


def test_el_nucleo_no_imprime():
    violaciones = []
    for archivo in CORE.rglob("*.py"):
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) in {"print", "input"}:
                violaciones.append(f"{archivo.relative_to(RAIZ)} línea {nodo.lineno}")
    assert not violaciones, "El núcleo no imprime ni lee de la terminal; emite eventos:\n" + "\n".join(violaciones)
