"""Architecture boundary inspection via AST analysis (AC-02).

Enforces core purity: verifies that no file in src/harness_agent/core/ imports
third-party LLM provider SDKs (LiteLLM, OpenAI, Anthropic, Google GenAI) or
heavy agent frameworks (RNF-12, AC-02, SC-002, Principio III).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_PACKAGES = {
    "litellm",
    "openai",
    "anthropic",
    "google",
    "google.genai",
    "google_genai",
    "langchain",
    "llama_index",
    "cohere",
    "mistralai",
    "mcp",
    "sqlite3",
}


def test_core_does_not_import_vendor_sdks() -> None:
    """Analyze all Python files in core/ and assert zero vendor SDK imports."""
    core_dir = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
    assert core_dir.exists(), f"Core directory not found at {core_dir}"

    python_files = list(core_dir.rglob("*.py"))
    assert len(python_files) >= 8, (
        f"Expected at least 8 core Python files, found {len(python_files)}"
    )

    violations: list[str] = []

    for file_path in python_files:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    if top_pkg in FORBIDDEN_PACKAGES or alias.name in FORBIDDEN_PACKAGES:
                        violations.append(
                            f"{file_path.name}:{node.lineno}: import {alias.name} "
                            "(forbidden provider SDK)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_pkg = node.module.split(".")[0]
                    if top_pkg in FORBIDDEN_PACKAGES or node.module in FORBIDDEN_PACKAGES:
                        violations.append(
                            f"{file_path.name}:{node.lineno}: from {node.module} "
                            "import ... (forbidden provider SDK)"
                        )

    assert not violations, "Core architectural boundary violations detected:\n" + "\n".join(
        violations
    )


def test_core_dependencies_are_standard_library_only() -> None:
    """Whitelist: every absolute import in core/ is stdlib, harness_agent or __future__."""
    core_dir = Path(__file__).resolve().parents[2] / "src" / "harness_agent" / "core"
    python_files = list(core_dir.rglob("*.py"))
    assert python_files, f"No core Python files found at {core_dir}"

    allowed_roots = set(sys.stdlib_module_names) | {"harness_agent", "__future__"}

    disallowed_external: list[str] = []

    for file_path in python_files:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in allowed_roots:
                        disallowed_external.append(
                            f"{file_path.name}:{node.lineno} -> {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                # Relative imports (level > 0) stay inside the package.
                if node.level == 0 and node.module:
                    root = node.module.split(".")[0]
                    if root not in allowed_roots:
                        disallowed_external.append(
                            f"{file_path.name}:{node.lineno} -> {node.module}"
                        )

    assert not disallowed_external, "Disallowed external packages imported in core:\n" + "\n".join(
        disallowed_external
    )
