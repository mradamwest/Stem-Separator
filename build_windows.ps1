param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$demucsDir = (& $Python -c "import pathlib, demucs; print(pathlib.Path(demucs.__file__).resolve().parent)").Trim()
$demucsApi = Join-Path $demucsDir "api.py"
if (!(Test-Path $demucsApi)) { throw "Installed Demucs package is missing api.py: $demucsApi" }
& $Python -m PyInstaller --noconfirm --clean --windowed --name StemSeparator `
  --collect-all demucs `
  --collect-all torchaudio `
  --collect-all numpy `
  --hidden-import demucs.api `
  --add-data "$demucsApi;demucs" `
  --hidden-import numpy.core._multiarray_umath `
  src/stem_separator/__main__.py
if (-not (Test-Path "dist/StemSeparator/StemSeparator.exe")) { throw "Packaged StemSeparator.exe was not created." }
Write-Host "Packaged: dist/StemSeparator/StemSeparator.exe"
