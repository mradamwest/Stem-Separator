from pathlib import Path

import pytest

from stem_separator.engine import inspect_engine, validate_input


def test_engine_imports():
    info = inspect_engine()
    assert info.demucs_available
    assert info.device in {"cpu", "cuda"}
    assert info.torch_version
    assert info.torchaudio_version


def test_validate_input(tmp_path: Path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"not-empty")
    assert validate_input(audio) == audio.resolve()


def test_missing_input(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_input(tmp_path / "missing.wav")
