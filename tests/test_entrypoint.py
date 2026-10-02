from pathlib import Path


def test_desktop_entry_point_is_registered():
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'stem-separator = "stem_separator.ui:main"' in text
