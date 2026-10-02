param([string]$Python = "python")
$ErrorActionPreference = "Stop"
& $Python -m PyInstaller --noconfirm --clean --windowed --name StemSeparator --collect-submodules demucs --collect-submodules torchaudio src/stem_separator/__main__.py
if (-not (Test-Path "dist/StemSeparator/StemSeparator.exe")) { throw "Packaged StemSeparator.exe was not created." }
Write-Host "Packaged: dist/StemSeparator/StemSeparator.exe"
