from pathlib import Path

import pytest

from stem_separator.engine import default_output_directory, inspect_engine, validate_audio_input, validate_input


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


def test_validate_audio_input_rejects_unknown_format(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_bytes(b"audio")
    with pytest.raises(ValueError, match="Unsupported audio format"):
        validate_audio_input(source)


def test_validate_audio_input_accepts_wav(tmp_path: Path):
    source = tmp_path / "sample.WAV"
    source.write_bytes(b"audio")
    assert validate_audio_input(source) == source.resolve()


def test_default_output_directory(tmp_path: Path):
    source = tmp_path / "My Song.wav"
    source.write_bytes(b"audio")
    assert default_output_directory(source) == tmp_path / "My Song_stems"
