"""``python -m harness_agent``: starts the harness (the logic is in ``bootstrap``)."""

from harness_agent.bootstrap import entry

raise SystemExit(entry())
