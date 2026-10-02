from pathlib import Path


def test_stem_ui_guards_active_worker_shutdown():
    text = Path("src/stem_separator/ui.py").read_text(encoding="utf-8")
    assert "def closeEvent" in text
    assert "isRunning()" in text
