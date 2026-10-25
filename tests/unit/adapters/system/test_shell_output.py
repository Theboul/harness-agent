"""OutputCollector: bounded, marked shell output (HU-01-04 / T002).

The collector keeps only the head and the tail of what a command prints, so a command that writes
without limit cannot exhaust memory, and the text that reaches the model never exceeds the maximum.
"""

from __future__ import annotations

import pytest

from harness_agent.adapters.system.shell_errors import ShellStartError
from harness_agent.adapters.system.shell_limits import (
    GRACE_SECONDS,
    MAX_OUTPUT_CHARS,
    NOTICE_RESERVE_CHARS,
    READER_JOIN_SECONDS,
)
from harness_agent.adapters.system.shell_output import OutputCollector

SMALL_MAX = NOTICE_RESERVE_CHARS + 40


def collect(chunks: list[bytes], max_chars: int = SMALL_MAX) -> str:
    collector = OutputCollector(max_chars)
    for chunk in chunks:
        collector.feed(chunk)
    return collector.finish()


class TestLimits:
    def test_the_documented_values(self) -> None:
        assert MAX_OUTPUT_CHARS == 20_000
        assert NOTICE_RESERVE_CHARS == 160
        assert GRACE_SECONDS == 1.5
        assert READER_JOIN_SECONDS == 1.0

    def test_a_start_error_is_an_os_error(self) -> None:
        assert issubclass(ShellStartError, OSError)


class TestShortOutput:
    def test_empty_output_is_the_empty_text(self) -> None:
        assert collect([]) == ""

    def test_short_output_arrives_whole_and_unmarked(self) -> None:
        assert collect([b"hola\n"]) == "hola\n"

    def test_output_exactly_at_the_maximum_has_no_notice(self) -> None:
        text = "x" * SMALL_MAX
        assert collect([text.encode()]) == text

    def test_many_small_chunks_are_joined_in_order(self) -> None:
        chunks = [str(number).encode() for number in range(10)]
        assert collect(chunks) == "0123456789"


class TestLongOutput:
    def test_one_more_character_than_the_maximum_is_cut_and_marked(self) -> None:
        result = collect([b"x" * (SMALL_MAX + 1)])
        assert "[salida recortada: se omitieron" in result
        assert len(result) <= SMALL_MAX

    def test_the_result_never_exceeds_the_maximum(self) -> None:
        for size in (SMALL_MAX + 1, SMALL_MAX * 3, SMALL_MAX * 100):
            assert len(collect([b"a" * size])) <= SMALL_MAX

    def test_keeps_the_head_and_the_tail(self) -> None:
        body = "INICIO" + "m" * 5_000 + "FINAL"
        result = collect([body.encode()])
        assert result.startswith("INICIO")
        assert result.endswith("FINAL")

    def test_the_notice_states_the_exact_number_of_omitted_characters(self) -> None:
        total = SMALL_MAX * 10
        result = collect([b"z" * total])
        kept = result.replace("z", "")
        omitted = total - result.count("z")
        assert f"se omitieron {omitted} caracteres" in kept

    def test_the_count_does_not_depend_on_how_the_chunks_are_split(self) -> None:
        data = ("abcdefghij" * 500).encode()
        whole = collect([data])
        split = collect([data[index : index + 7] for index in range(0, len(data), 7)])
        assert whole == split

    def test_retained_memory_stays_bounded_for_huge_output(self) -> None:
        collector = OutputCollector(SMALL_MAX)
        for _ in range(2_000):
            collector.feed(b"y" * 1_000)
        assert collector.retained_chars <= SMALL_MAX
        assert collector.total_chars == 2_000_000

    def test_a_default_collector_uses_the_documented_maximum(self) -> None:
        collector = OutputCollector()
        collector.feed(b"q" * (MAX_OUTPUT_CHARS * 2))
        assert len(collector.finish()) <= MAX_OUTPUT_CHARS


class TestDecoding:
    def test_a_multibyte_character_split_between_chunks_is_rebuilt(self) -> None:
        encoded = "áé".encode()
        assert collect([encoded[:1], encoded[1:3], encoded[3:]]) == "áé"

    def test_invalid_bytes_are_replaced_without_raising(self) -> None:
        result = collect([b"ok \xff\xfe fin"])
        assert result.startswith("ok ")
        assert "�" in result
        assert result.endswith(" fin")

    def test_a_truncated_sequence_at_the_end_is_replaced(self) -> None:
        assert collect(["é".encode()[:1]]) == "�"

    def test_finish_can_be_called_twice_with_the_same_result(self) -> None:
        collector = OutputCollector(SMALL_MAX)
        collector.feed(b"abc")
        assert collector.finish() == collector.finish() == "abc"


class TestArguments:
    @pytest.mark.parametrize("bad", [0, -1, NOTICE_RESERVE_CHARS])
    def test_a_maximum_that_cannot_hold_the_notice_is_rejected(self, bad: int) -> None:
        with pytest.raises(ValueError, match="máximo"):
            OutputCollector(bad)
