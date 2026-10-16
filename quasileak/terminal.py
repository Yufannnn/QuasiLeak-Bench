"""Terminal-only presentation; redirected output and saved artifacts stay plain."""
from __future__ import annotations

from importlib.metadata import version
import sys

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_plain = False


def configure(*, plain=False):
    global _plain
    _plain = plain


def console():
    return Console(file=sys.stdout, width=None, highlight=False)


def enabled():
    return not _plain and console().is_terminal


def banner(*, demo=False):
    release = version("quasileak-bench")
    if not enabled():
        print(f"QuasiLeak-Bench {release}" + (" | OFFLINE DEMO · synthetic detector" if demo else ""))
        print("Individually weak, but revealing together.")
        return
    out = console()
    logo = Text(
        " ██████╗ ██╗     ██████╗ \n"
        "██╔═══██╗██║     ██╔══██╗\n"
        "██║   ██║██║     ██████╔╝\n"
        "██║▄▄ ██║██║     ██╔══██╗\n"
        "╚██████╔╝███████╗██████╔╝\n"
        " ╚══▀▀═╝ ╚══════╝╚═════╝ ", style="bold cyan")
    title = Text("QuasiLeak-Bench", style="bold bright_white")
    title.append("  /  privacy evaluation toolkit", style="dim")
    badges = Text(f" v{release} ", style="bold black on cyan")
    badges.append("  ")
    badges.append(" OFFLINE DEMO " if demo else " EVALUATE · COMPARE · REPRODUCE ", style="bold white on dark_magenta")
    badges.append("  ")
    badges.append(" RELEASED SCORER ", style="bold black on green")
    content = [logo, Text(""), title, Text("Individually weak, but revealing together.", style="italic"), Text(""), badges]
    if demo:
        content.extend([Text(""), Text("Synthetic example detector · no model calls · not a leaderboard result", style="dim")])
    out.print(Panel(Group(*content), border_style="cyan", padding=(1, 3), width=min(out.width, 108)))
    out.print()


def heading(title, badge=None):
    if not enabled():
        print(f"QuasiLeak-Bench | {title}\n")
        return
    label = Text(" QLB ", style="bold black on cyan")
    label.append("  " + title.upper(), style="bold cyan")
    if badge:
        label.append("  ")
        label.append(f" {badge} ", style="bold white on dark_magenta")
    out = console()
    out.print(label)


def show_table(headers, rows, plain_text):
    if not enabled():
        print(plain_text, end="")
        return
    out = console()
    if headers[0] == "Run" and out.width < 110:
        # Nine metric columns cannot fit at 80 columns without clipping values.
        for row in rows:
            out.print(Text(str(row[0]), style="bold"))
            grid = Table(box=box.ROUNDED, border_style="bright_black", header_style="bold cyan",
                         width=min(out.width, 56))
            grid.add_column("Metric")
            grid.add_column("Value", justify="right", no_wrap=True)
            for header, value in zip(headers[1:], row[1:]):
                label = "—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)
                grid.add_row(Text(header), Text(label, style="bold magenta" if header == "P-GF1" else ""))
            out.print(grid)
        return
    grid = Table(box=box.ROUNDED, border_style="bright_black", header_style="bold cyan",
                 padding=(0, 1), row_styles=["", "dim"], width=min(out.width, 120))
    for index, header in enumerate(headers):
        numeric = index > 0 and header not in ("Selection", "Use")
        grid.add_column(header, justify="left" if index == 0 or header in ("Selection", "Use") else "right",
                        no_wrap=numeric, overflow="fold", style="bold magenta" if header == "P-GF1" else None)
    for row in rows:
        grid.add_row(*(Text("—" if value is None else f"{value:.4f}" if isinstance(value, float) else str(value)) for value in row))
    out.print(grid)


def result_badge(metrics):
    if not enabled() or not isinstance(metrics.get("P-GF1"), (int, float)):
        return
    out = console()
    text = Text(f"{metrics['P-GF1']:.4f}", style="bold magenta")
    text.append(" / 100  P-GF1", style="bold")
    text.append("\nPolicy-conditioned group recovery", style="dim")
    out.print(Panel(text, border_style="magenta", width=min(out.width, 56), padding=(0, 2)))


def success(message):
    if not enabled():
        print("PASS | " + message)
        return
    text = Text(" PASS ", style="bold black on green")
    text.append("  " + message)
    console().print(text)
