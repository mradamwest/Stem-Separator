from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EngineInfo:
    device: str
    torch_version: str
    torchaudio_version: str
    demucs_available: bool


def inspect_engine() -> EngineInfo:
    import torch
    import torchaudio
    import demucs

    device = "cuda" if torch.cuda.is_available() else "cpu"
    return EngineInfo(
        device=device,
        torch_version=torch.__version__,
        torchaudio_version=torchaudio.__version__,
        demucs_available=demucs is not None,
    )


def validate_input(path: str | Path) -> Path:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.stat().st_size == 0:
        raise ValueError("Input audio file is empty.")
    return source
