from pathlib import Path

import pytest

from stem_separator.engine import create_separation_plan, default_output_directory, inspect_engine, prepare_output_directory, resolve_device, validate_audio_input, validate_input


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


def test_create_separation_plan(tmp_path: Path):
    source = tmp_path / "track.flac"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source, model_name="htdemucs", device="cpu")
    assert plan.source == source.resolve()
    assert plan.output_directory == tmp_path / "track_stems"
    assert plan.model_name == "htdemucs"
    assert plan.device == "cpu"


def test_create_separation_plan_rejects_device(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    with pytest.raises(ValueError, match="Unsupported device"):
        create_separation_plan(source, device="metal")


def test_resolve_explicit_device():
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("cuda") == "cuda"


def test_resolve_device_rejects_unknown():
    with pytest.raises(ValueError, match="Unsupported device"):
        resolve_device("metal")


def test_prepare_output_directory_preserves_existing_files(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    plan.output_directory.mkdir()
    existing = plan.output_directory / "keep.txt"
    existing.write_text("keep", encoding="utf-8")
    assert prepare_output_directory(plan) == plan.output_directory
    assert existing.read_text(encoding="utf-8") == "keep"
