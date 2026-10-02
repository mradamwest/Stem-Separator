from pathlib import Path

import pytest

from stem_separator.engine import build_export_manifest, completed_export_manifest, create_separation_plan, default_output_directory, discover_model_stems, inspect_engine, prepare_output_directory, safe_stem_filename, separation_progress, separation_status, separation_summary, stem_output_paths, resolve_device, validate_audio_input, validate_input


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


def test_discover_model_stems_is_dynamic():
    class Model:
        sources = ["vocals", "drums", "bass", "other", "guitar", "piano"]
    assert discover_model_stems(Model()) == ("vocals", "drums", "bass", "other", "guitar", "piano")


def test_discover_model_stems_rejects_missing_sources():
    class Model:
        sources = []
    with pytest.raises(RuntimeError, match="does not expose"):
        discover_model_stems(Model())


def test_stem_output_paths_follow_dynamic_model(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    paths = stem_output_paths(plan, ["vocals", "guitar", "piano"])
    assert list(paths) == ["vocals", "guitar", "piano"]
    assert paths["guitar"] == plan.output_directory / "guitar.wav"


def test_stem_output_paths_reject_unsafe_names(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    with pytest.raises(ValueError, match="unsafe"):
        stem_output_paths(plan, ["../escape"])


def test_validate_stem_results_accepts_dynamic_count():
    assert validate_stem_results(["vocals", "guitar", "piano"], [1, 2, 3]) == ("vocals", "guitar", "piano")


def test_validate_stem_results_rejects_count_mismatch():
    with pytest.raises(RuntimeError, match="2 outputs for 3 stems"):
        validate_stem_results(["vocals", "guitar", "piano"], [1, 2])


def test_validate_stem_audio_rejects_empty_output():
    class EmptyAudio:
        def numel(self): return 0
    with pytest.raises(RuntimeError, match="vocals"):
        validate_stem_audio("vocals", EmptyAudio())


def test_validate_stem_audio_accepts_nonempty_output():
    class Audio:
        def numel(self): return 10
    validate_stem_audio("guitar", Audio())


def test_safe_stem_filename_handles_windows_reserved_names():
    assert safe_stem_filename("CON") == "_CON.wav"
    assert safe_stem_filename("lead:vocal") == "lead_vocal.wav"


def test_ensure_output_paths_are_inside_plan, unique_stem_output_paths, validate_sample_rate():
    assert validate_sample_rate(44100) == 44100
    with pytest.raises(ValueError, match="positive integer"):
        validate_sample_rate(0)
    with pytest.raises(ValueError, match="positive integer"):
        validate_sample_rate(True)


def test_unique_stem_output_paths_avoid_windows_collisions(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    paths = unique_stem_output_paths(plan, ["lead:vocal", "lead?vocal"])
    assert len({p.name.casefold() for p in paths.values()}) == 2


def test_output_paths_must_stay_inside_plan(tmp_path: Path):
    source = tmp_path / "track.wav"
    source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    ensure_output_paths_are_inside_plan(plan, {"vocals": plan.output_directory / "vocals.wav"})
    with pytest.raises(ValueError, match="escapes"):
        ensure_output_paths_are_inside_plan(plan, {"bad": tmp_path / "outside.wav"})


def test_verify_exported_stems(tmp_path: Path):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"audio")
    verify_exported_stems({"vocals": vocals})
    with pytest.raises(RuntimeError, match="not exported"):
        verify_exported_stems({"drums": tmp_path / "missing.wav"})


def test_validate_model_sample_rate_supports_demucs_attribute():
    class Model:
        samplerate = 44100
    assert validate_model_sample_rate(Model()) == 44100


def test_validate_model_sample_rate_rejects_missing_rate():
    class Model: pass
    with pytest.raises(RuntimeError, match="valid sample rate"):
        validate_model_sample_rate(Model())


def test_validate_model_channels():
    class Model:
        audio_channels = 2
    assert validate_model_channels(Model()) == 2


def test_validate_model_channels_rejects_missing_value():
    class Model: pass
    with pytest.raises(RuntimeError, match="valid channel count"):
        validate_model_channels(Model())


def test_validate_model_sources_rejects_case_collisions():
    class Model:
        sources = ["Vocals", "vocals"]
    with pytest.raises(RuntimeError, match="case-insensitive duplicate"):
        validate_model_sources(Model())


def test_build_export_manifest_tracks_dynamic_stems(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    manifest = build_export_manifest(plan, ["vocals", "guitar", "piano"])
    assert manifest == {"vocals": "vocals.wav", "guitar": "guitar.wav", "piano": "piano.wav"}


def test_completed_export_manifest_verifies_files(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    plan.output_directory.mkdir()
    (plan.output_directory / "vocals.wav").write_bytes(b"stem")
    manifest = completed_export_manifest(plan, ["vocals"])
    assert manifest["vocals"]["filename"] == "vocals.wav"
    assert manifest["vocals"]["bytes"] == 4


def test_separation_status_tracks_partial_dynamic_outputs(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source)
    plan.output_directory.mkdir()
    (plan.output_directory / "vocals.wav").write_bytes(b"stem")
    status = separation_status(plan, ["vocals", "guitar"])
    assert status["completed"] == ("vocals",)
    assert status["complete"] is False


def test_separation_progress_uses_dynamic_stem_count(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source); plan.output_directory.mkdir()
    (plan.output_directory / "vocals.wav").write_bytes(b"stem")
    completed, total, percent = separation_progress(plan, ["vocals", "guitar", "piano"])
    assert (completed, total) == (1, 3)
    assert percent == pytest.approx(100 / 3)


def test_separation_summary_uses_dynamic_counts(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source); plan.output_directory.mkdir()
    (plan.output_directory / "vocals.wav").write_bytes(b"stem")
    assert separation_summary(plan, ["vocals", "guitar"]) == "Separating — 1/2 stems (50%)"
