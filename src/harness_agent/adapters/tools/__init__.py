"""Native tools of the harness: the file tools (HU-01-03).

``leer_archivo``, ``escribir_archivo``, ``listar_archivos`` and ``buscar_texto`` receive the
authorized area by constructor and act only inside it. The helpers in ``_paths`` are internal.
"""

from harness_agent.adapters.tools._limits import (
    MAX_LINE_CHARS,
    MAX_LIST_ENTRIES,
    MAX_MATCHES,
    MAX_QUERY_CHARS,
    MAX_READ_BYTES,
    MAX_RESULT_CHARS,
    MAX_WRITE_BYTES,
)
from harness_agent.adapters.tools.list_files import ListFilesTool
from harness_agent.adapters.tools.read_file import ReadFileTool
from harness_agent.adapters.tools.search_text import SearchTextTool
from harness_agent.adapters.tools.write_file import WriteFileTool

__all__ = [
    "ReadFileTool",
    "WriteFileTool",
    "ListFilesTool",
    "SearchTextTool",
    "MAX_READ_BYTES",
    "MAX_WRITE_BYTES",
    "MAX_LIST_ENTRIES",
    "MAX_MATCHES",
    "MAX_LINE_CHARS",
    "MAX_QUERY_CHARS",
    "MAX_RESULT_CHARS",
]
