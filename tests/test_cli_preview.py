"""README preview is reproducible, self-contained, and uses real scorer output."""
import importlib.util
from pathlib import Path


def test_readme_terminal_preview(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/render_cli_preview.py"
    spec = importlib.util.spec_from_file_location("qlb_render_preview", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path / "cli-preview.svg"
    module.render(destination)
    first = destination.read_text(encoding="utf-8")
    assert "60.0163" in first
    assert "QuasiLeak-Bench" in first
    assert "OFFLINE DEMO" not in first
    assert "@font-face" not in first
    assert "url(https" not in first
    assert "<svg" in first
    module.render(destination)
    assert destination.read_text(encoding="utf-8") == first
