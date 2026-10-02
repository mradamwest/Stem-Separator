from pathlib import Path

import pytest

from stem_separator.engine import (
    build_export_manifest, completed_export_manifest, create_separation_plan,
    default_output_directory, discover_model_stems, ensure_output_paths_are_inside_plan,
    ensure_separation_ready, first_run_status, inspect_engine, load_separator_for_plan, model_cache_directory, model_cache_has_files, model_cache_status, prepare_output_directory, resolve_device, run_separation, safe_stem_filename,
    separate_audio, separation_preflight, separation_progress, separation_result, separation_status, separation_summary, separator_runtime_status, stem_output_paths,
    unique_stem_output_paths, validate_audio_input, validate_input,
    validate_model_channels, validate_model_sample_rate, validate_model_sources,
    validate_sample_rate, validate_stem_audio, validate_stem_results,
    verify_exported_stems,
)


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


def test_validate_sample_rate():
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


def test_separate_audio_builds_plan_and_dispatches(monkeypatch, tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    captured = {}
    def fake_run(plan):
        captured["plan"] = plan
        return {"vocals": plan.output_directory / "vocals.wav"}
    monkeypatch.setattr("stem_separator.engine.separate_with_demucs", fake_run)
    result = separate_audio(source, model_name="htdemucs", device="cpu")
    assert captured["plan"].source == source.resolve()
    assert captured["plan"].device == "cpu"
    assert "vocals" in result


def test_load_separator_for_plan_uses_requested_model_and_device(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source, model_name="custom-model", device="cpu")
    calls = {}
    def factory(**kwargs):
        calls.update(kwargs)
        return object()
    load_separator_for_plan(plan, factory)
    assert calls == {"model": "custom-model", "device": "cpu", "progress": False}


def test_separator_runtime_status_is_ui_ready(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source, device="cpu")
    status = separator_runtime_status(plan)
    assert status["device"] == "cpu"
    assert status["model_name"] == "htdemucs"
    assert isinstance(status["ready"], bool)


def test_model_cache_status_without_download(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch-home"))
    assert model_cache_directory() == (tmp_path / "torch-home" / "hub" / "checkpoints").resolve()
    status = model_cache_status()
    assert status["exists"] is False
    assert status["files"] == ()
    assert status["bytes"] == 0


def test_separation_preflight_does_not_create_output(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source, device="cpu")
    status = separation_preflight(plan)
    assert status["source"] == str(source.resolve())
    assert status["device"] == "cpu"
    assert not plan.output_directory.exists()


def test_separation_result_verifies_dynamic_exports(tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source); plan.output_directory.mkdir()
    vocals = plan.output_directory / "vocals.wav"; vocals.write_bytes(b"voice")
    guitar = plan.output_directory / "guitar.wav"; guitar.write_bytes(b"guitar")
    result = separation_result(plan, {"vocals": vocals, "guitar": guitar})
    assert result["count"] == 2
    assert result["bytes"] == 11
    assert set(result["stems"]) == {"vocals", "guitar"}


def test_run_separation_connects_preflight_engine_and_result(monkeypatch, tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    def fake_preflight(plan): return {"runtime_ready": True}
    def fake_separate(plan):
        plan.output_directory.mkdir(parents=True, exist_ok=True)
        path = plan.output_directory / "vocals.wav"; path.write_bytes(b"stem")
        return {"vocals": path}
    monkeypatch.setattr("stem_separator.engine.ensure_separation_ready", lambda plan, allow_model_download=False: {"runtime_ready": True})
    monkeypatch.setattr("stem_separator.engine.separate_with_demucs", fake_separate)
    result = run_separation(source, device="cpu")
    assert result["count"] == 1
    assert result["bytes"] == 4


def test_model_cache_has_files(monkeypatch, tmp_path: Path):
    root = tmp_path / "torch-home" / "hub" / "checkpoints"
    monkeypatch.setenv("TORCH_HOME", str(tmp_path / "torch-home"))
    assert model_cache_has_files() is False
    root.mkdir(parents=True); (root / "model.th").write_bytes(b"weights")
    assert model_cache_has_files() is True


def test_first_run_status_reports_model_acquisition(monkeypatch, tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source, device="cpu")
    monkeypatch.setattr("stem_separator.engine.separation_preflight", lambda p: {"runtime_ready": True, "source": str(p.source)})
    monkeypatch.setattr("stem_separator.engine.model_cache_has_files", lambda: False)
    status = first_run_status(plan)
    assert status["model_cached"] is False
    assert status["requires_model_download"] is True


def test_ensure_separation_ready_requires_download_approval(monkeypatch, tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    plan = create_separation_plan(source, device="cpu")
    monkeypatch.setattr("stem_separator.engine.first_run_status", lambda p: {"runtime_ready": True, "requires_model_download": True})
    with pytest.raises(RuntimeError, match="approval"):
        ensure_separation_ready(plan)
    assert ensure_separation_ready(plan, allow_model_download=True)["requires_model_download"] is True


def test_run_separation_forwards_explicit_download_approval(monkeypatch, tmp_path: Path):
    source = tmp_path / "track.wav"; source.write_bytes(b"audio")
    seen = {}
    def ready(plan, allow_model_download=False):
        seen["allowed"] = allow_model_download
        return {"runtime_ready": True}
    def separate(plan):
        plan.output_directory.mkdir(parents=True, exist_ok=True)
        p = plan.output_directory / "vocals.wav"; p.write_bytes(b"stem")
        return {"vocals": p}
    monkeypatch.setattr("stem_separator.engine.ensure_separation_ready", ready)
    monkeypatch.setattr("stem_separator.engine.separate_with_demucs", separate)
    run_separation(source, device="cpu", allow_model_download=True)
    assert seen["allowed"] is True
