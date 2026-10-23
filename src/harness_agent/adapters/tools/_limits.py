"""Fixed limits of the file tools (HU-01-03): bounded inputs and bounded answers."""

from __future__ import annotations

MAX_READ_BYTES = 262_144
"""Largest file ``leer_archivo`` reads, and the largest file ``buscar_texto`` scans."""

MAX_WRITE_BYTES = 1_048_576
"""Largest content ``escribir_archivo`` writes."""

MAX_LIST_ENTRIES = 200
"""Entries ``listar_archivos`` returns before it cuts the list."""

MAX_MATCHES = 50
"""Matches ``buscar_texto`` returns before it cuts the search."""

MAX_LINE_CHARS = 200
"""Characters of a matching line that ``buscar_texto`` shows."""

MAX_QUERY_CHARS = 200
"""Longest text ``buscar_texto`` accepts."""

MAX_RESULT_CHARS = 20_000
"""Longest listing or search answer."""
