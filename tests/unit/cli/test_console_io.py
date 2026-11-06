"""Юнит-тесты ConsoleIO: повтор запроса, отмена, подтверждения."""

from __future__ import annotations

import pytest

from src.cli.console_io import Cancelled, ConsoleIO
from src.domain.exceptions import InvalidYesNoError
from src.domain.validation import parse_positive_int
from tests.fakes import ScriptedIO


class TestAsk:
    def test_returns_parsed_value(self):
        assert ScriptedIO(["5"]).ask("n: ", parse_positive_int) == 5

    def test_repeats_until_valid_and_reports_each_error(self, capsys):
        io = ScriptedIO(["x", "0.5", "7"])
        assert io.ask("n: ", parse_positive_int) == 7
        assert capsys.readouterr().out.count("✗") == 2
        assert len(io.prompts) == 3

    @pytest.mark.parametrize("word", ["0", "отмена", "cancel", "ОТМЕНА", "Cancel", "  0  "])
    def test_cancel_words(self, word):
        with pytest.raises(Cancelled):
            ScriptedIO([word]).ask("n: ", lambda raw: raw)

    def test_cancel_has_message(self):
        with pytest.raises(Cancelled, match="отменено"):
            ScriptedIO(["0"]).ask("n: ", lambda raw: raw)

    def test_zero_inside_longer_text_is_not_cancel(self):
        assert ScriptedIO(["10"]).ask("n: ", lambda raw: raw) == "10"

    def test_secret_uses_secret_reader(self):
        calls = []

        class Spy(ScriptedIO):
            def read_secret(self, prompt):
                calls.append("secret")
                return super().read_secret(prompt)

        Spy(["pw"]).ask("p: ", lambda raw: raw, secret=True)
        assert calls == ["secret"]

    def test_non_domain_errors_are_not_swallowed(self):
        def boom(raw):
            raise RuntimeError("bug")

        with pytest.raises(RuntimeError):
            ScriptedIO(["x"]).ask("n: ", boom)

    def test_end_of_input_propagates(self):
        with pytest.raises(EOFError):
            ScriptedIO([]).ask("n: ", lambda raw: raw)


class TestConfirm:
    @pytest.mark.parametrize(
        ("answer", "expected"), [("y", True), ("да", True), ("n", False), ("нет", False)]
    )
    def test_answers(self, answer, expected):
        assert ScriptedIO([answer]).confirm("Точно?") is expected

    def test_reasks_on_garbage(self, capsys):
        io = ScriptedIO(["maybe", "y"])
        assert io.confirm("Точно?") is True
        assert "✗" in capsys.readouterr().out

    def test_prompt_contains_hint(self):
        io = ScriptedIO(["y"])
        io.confirm("Точно?")
        assert io.prompts == ["Точно? (y/n): "]

    def test_cancel(self):
        with pytest.raises(Cancelled):
            ScriptedIO(["0"]).confirm("Точно?")

    def test_invalid_yes_no_error_type(self):
        from src.domain.validation import parse_yes_no

        with pytest.raises(InvalidYesNoError):
            parse_yes_no("maybe")


class TestAskText:
    def test_trims(self):
        assert ScriptedIO(["  hi  "]).ask_text("t: ", "Поле") == "hi"

    def test_blank_is_reasked(self, capsys):
        assert ScriptedIO(["  ", "ok"]).ask_text("t: ", "Поле") == "ok"
        assert "Поле" in capsys.readouterr().out

    def test_max_length_boundary(self):
        assert ScriptedIO(["abc"]).ask_text("t: ", "Поле", 3) == "abc"
        io = ScriptedIO(["abcd", "abc"])
        assert io.ask_text("t: ", "Поле", 3) == "abc"
        assert len(io.prompts) == 2


class TestAskOptionalText:
    def test_empty_gives_none(self):
        assert ScriptedIO([""]).ask_optional_text("t: ") is None
        assert ScriptedIO(["   "]).ask_optional_text("t: ") is None

    def test_text_is_trimmed(self):
        assert ScriptedIO(["  x "]).ask_optional_text("t: ") == "x"

    def test_cancel_still_works(self):
        with pytest.raises(Cancelled):
            ScriptedIO(["0"]).ask_optional_text("t: ")


class TestRealIO:
    def test_read_line_uses_input(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: f"echo:{prompt}")
        assert ConsoleIO().read_line("q") == "echo:q"

    def test_read_secret_uses_getpass(self, monkeypatch):
        monkeypatch.setattr("getpass.getpass", lambda prompt: "secret")
        assert ConsoleIO().read_secret("p") == "secret"

    def test_pause_waits_for_enter(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda prompt: "")
        ConsoleIO().pause()

    def test_header_mentions_cancel(self, capsys):
        ConsoleIO().header("Форма")
        out = capsys.readouterr().out
        assert "Форма" in out
        assert "0 — отмена" in out

    def test_clear_screen_without_tty_prints_blank_line(self, capsys, monkeypatch):
        monkeypatch.setattr("sys.stdout.isatty", lambda: False, raising=False)
        ConsoleIO().clear_screen()
        assert capsys.readouterr().out == "\n"

    def test_clear_screen_in_terminal_runs_clear_command(self, monkeypatch):
        commands = []
        monkeypatch.setattr("sys.stdout.isatty", lambda: True, raising=False)
        monkeypatch.setattr("os.system", commands.append)
        ConsoleIO().clear_screen()
        assert commands and commands[0] in ("clear", "cls")
