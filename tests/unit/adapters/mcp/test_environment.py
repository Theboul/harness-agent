"""The environment of the server process holds only what the configuration names (FR-007)."""

from __future__ import annotations

from harness_agent.adapters.mcp.environment import server_environment

ANTHROPIC = "ANTHROPIC_API_" + "KEY"
OPENAI = "OPENAI_API_" + "KEY"
PARENT = {
    ANTHROPIC: "uno-1",
    OPENAI: "dos-2",
    "PATH": "/usr/bin",
    "EXTRA": "uno",
}


class TestServerEnvironment:
    def test_nothing_is_inherited_without_names(self) -> None:
        assert server_environment(PARENT, (), windows=False) == {}

    def test_only_the_named_variables_that_exist_are_passed(self) -> None:
        result = server_environment(PARENT, ("EXTRA", "MISSING"), windows=False)

        assert result == {"EXTRA": "uno"}

    def test_the_api_keys_of_the_parent_do_not_pass_unless_named(self) -> None:
        result = server_environment(PARENT, ("EXTRA",), windows=False)

        assert ANTHROPIC not in result
        assert OPENAI not in result

    def test_a_key_named_expressly_is_passed(self) -> None:
        assert server_environment(PARENT, (OPENAI,), windows=False) == {OPENAI: "dos-2"}

    def test_names_are_case_sensitive_on_posix(self) -> None:
        assert server_environment(PARENT, ("extra",), windows=False) == {}

    def test_names_ignore_case_on_windows_and_keep_the_spelling_of_the_parent(self) -> None:
        assert server_environment(PARENT, ("extra",), windows=True) == {"EXTRA": "uno"}

    def test_the_parent_environment_is_not_modified(self) -> None:
        parent = dict(PARENT)

        server_environment(parent, ("EXTRA",), windows=False)

        assert parent == PARENT
