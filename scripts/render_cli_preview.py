"""Regenerate the README's vector terminal preview from real offline CLI output."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from rich.console import Console
from rich.terminal_theme import TerminalTheme
from rich.text import Text

from quasileak import terminal
from quasileak.cli import main


def render(destination):
    root = Path(__file__).resolve().parents[1]
    stream = io.StringIO()
    capture = Console(file=stream, width=112, height=80, force_terminal=True, color_system="truecolor",
                      no_color=False, highlight=False)
    original_console = terminal.console
    terminal.console = lambda: capture
    try:
        with TemporaryDirectory(prefix="qlb-preview-") as temporary, redirect_stdout(stream):
            with ZipFile(root / "data/quasileak_bench_data.zip") as archive:
                dataset = Path(archive.extract("quasileak_bench_data_1k.jsonl", temporary))
            predictions = root / "examples/predictions_1k.jsonl"
            for arguments in (
                ["banner"],
                ["datasets", "list"],
                ["check", "--dataset", str(dataset), "--predictions", str(predictions)],
                ["score", "--dataset", str(dataset), "--predictions", str(predictions),
                 "--name", "Example predictions (synthetic)"],
            ):
                if main(arguments) != 0:
                    raise RuntimeError("CLI preview command failed")
                capture.print()
    finally:
        terminal.console = original_console
        terminal.configure()

    theme = TerminalTheme(
        (25, 31, 39), (220, 229, 239),
        [(25, 31, 39), (226, 123, 132), (133, 199, 161), (226, 194, 129),
         (130, 168, 223), (177, 156, 213), (114, 200, 207), (220, 229, 239)],
        [(139, 157, 177), (242, 151, 160), (158, 220, 183), (242, 215, 156),
         (157, 193, 242), (203, 183, 237), (150, 224, 229), (242, 246, 251)],
    )
    output = Console(file=io.StringIO(), width=112, height=80, record=True, force_terminal=True,
                     color_system="truecolor", no_color=False)
    output.print(Text.from_ansi(stream.getvalue()), end="")
    destination.parent.mkdir(parents=True, exist_ok=True)
    svg = output.export_svg(title="QuasiLeak-Bench · Command line", theme=theme, unique_id="qlb-cli-preview")
    # Self-contained GitHub image: no remote fonts or network dependencies.
    svg = re.sub(r"\s*@font-face\s*\{[^}]*\}", "", svg)
    svg = svg.replace("Fira Code, monospace", "'SFMono-Regular', Menlo, Consolas, monospace")
    destination.write_text(svg, encoding="utf-8")
    print(f"Generated {destination.name} from the released scorer and example predictions.")


if __name__ == "__main__":
    render(Path(__file__).resolve().parents[1] / "docs/cli-preview.svg")
