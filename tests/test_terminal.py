"""Presentation never contaminates machine-readable output or saved reports."""
import io
import json

import pytest
from rich.console import Console

from quasileak import terminal
from quasileak.cli import main


@pytest.fixture(autouse=True)
def reset_presentation():
    terminal.configure()
    yield
    terminal.configure()


def test_redirected_output_stays_plain(capsys):
    assert main(["datasets", "list"]) == 0
    output = capsys.readouterr().out
    assert "QLB-Test" in output
    assert "\x1b" not in output
    assert "╭" not in output


def test_machine_outputs_remain_valid_even_in_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr(terminal, "enabled", lambda: True)
    assert main(["datasets", "list", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 6
    assert main(["schema"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), dict)


@pytest.mark.parametrize("width", [60, 100, 140])
def test_terminal_banner_badges_and_tables(monkeypatch, width):
    output = io.StringIO()
    monkeypatch.setattr(terminal, "console", lambda: Console(file=output, width=width, force_terminal=True, color_system="standard"))
    assert main(["banner", "--demo"]) == 0
    assert main(["datasets", "list"]) == 0
    rendered = output.getvalue()
    assert "QuasiLeak-Bench" in rendered
    assert "OFFLINE DEMO" in rendered
    assert "QLB-Test" in rendered
    assert "\x1b[" in rendered
    assert "╭" in rendered


def test_plain_option_disables_decoration(monkeypatch, capsys):
    monkeypatch.setattr(terminal, "console", lambda: Console(force_terminal=True))
    assert main(["--plain", "banner", "--demo"]) == 0
    output = capsys.readouterr().out
    assert "OFFLINE DEMO" in output
    assert "\x1b" not in output


def test_no_color_keeps_layout_without_ansi_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    output = io.StringIO()
    monkeypatch.setattr(terminal, "console", lambda: Console(file=output, width=100, force_terminal=True))
    assert main(["datasets", "list"]) == 0
    # Rich still allows emphasis under NO_COLOR, but strips foreground/background colours.
    assert "\x1b[36m" not in output.getvalue()
    assert "QLB-Test" in output.getvalue()


@pytest.mark.parametrize("width", [60, 80, 100, 120, 140])
def test_score_values_are_not_clipped(monkeypatch, width):
    output = io.StringIO()
    monkeypatch.setattr(terminal, "console", lambda: Console(file=output, width=width, force_terminal=True))
    headers = ("Run", "P-GF1", "P-GP", "P-GR", "E-GF1", "DSR", "FAR", "N_docs", "N_pred")
    terminal.show_table(headers, [["Example detector (synthetic)", *([60.0163] * 6), 1000, 665]], "unused")
    assert output.getvalue().count("60.0163") == 6
    assert "1000" in output.getvalue()
    assert "N_pred" in output.getvalue()
