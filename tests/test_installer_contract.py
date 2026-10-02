from pathlib import Path

def test_installer_keeps_required_windows_shortcuts_and_uninstaller():
    text=Path("installer/StemSeparator.iss").read_text(encoding="utf-8")
    assert "{autodesktop}" in text
    assert "{autoprograms}" in text
    assert "Uninstallable=yes" in text
    assert "CreateUninstallRegKey=yes" in text
    assert "{uninstallexe}" in text
