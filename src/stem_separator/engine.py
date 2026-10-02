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


SUPPORTED_AUDIO_EXTENSIONS = frozenset({".wav", ".mp3", ".flac", ".ogg", ".m4a"})


def validate_audio_input(path: str | Path) -> Path:
    """Validate a user-selected audio source before any model work begins."""
    source = validate_input(path)
    if source.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError(f"Unsupported audio format: {source.suffix or '<none>'}")
    return source


def default_output_directory(source: str | Path, root: str | Path | None = None) -> Path:
    """Return a deterministic per-track output directory without creating it."""
    audio = validate_audio_input(source)
    base = Path(root).expanduser().resolve() if root is not None else audio.parent
    return base / f"{audio.stem}_stems"


@dataclass(frozen=True)
class SeparationPlan:
    source: Path
    output_directory: Path
    model_name: str = "htdemucs"
    device: str = "auto"


def create_separation_plan(
    source: str | Path,
    output_root: str | Path | None = None,
    model_name: str = "htdemucs",
    device: str = "auto",
) -> SeparationPlan:
    if not model_name.strip():
        raise ValueError("Model name cannot be empty.")
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"Unsupported device: {device}")
    audio = validate_audio_input(source)
    resolved_output = default_output_directory(audio, output_root)
    if resolved_output == audio.parent and resolved_output.name == audio.name:
        raise ValueError("Output directory cannot be the input file.")
    return SeparationPlan(audio, resolved_output, model_name.strip(), device)


def resolve_device(requested: str = "auto") -> str:
    """Resolve automatic acceleration with a safe CPU fallback."""
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"Unsupported device: {requested}")
    if requested == "cpu":
        return "cpu"
    if requested == "cuda":
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("CUDA was requested but PyTorch is not installed.") from exc
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA was requested but no compatible GPU is available.")
        return "cuda"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except (ImportError, RuntimeError):
        return "cpu"


def prepare_output_directory(plan: SeparationPlan) -> Path:
    """Create the planned output directory without deleting existing user files."""
    plan.output_directory.mkdir(parents=True, exist_ok=True)
    return plan.output_directory


def discover_model_stems(model) -> tuple[str, ...]:
    """Read the actual source names exposed by a loaded separation model."""
    sources = getattr(model, "sources", None)
    if not sources:
        raise RuntimeError("Separation model does not expose any stems.")
    names = tuple(str(name).strip() for name in sources if str(name).strip())
    if not names:
        raise RuntimeError("Separation model returned an empty stem list.")
    if len(set(names)) != len(names):
        raise RuntimeError("Separation model returned duplicate stem names.")
    return names


def stem_output_paths(plan: SeparationPlan, stem_names) -> dict[str, Path]:
    """Map model-reported stems to safe WAV destinations without assuming stem count."""
    names = tuple(str(name).strip() for name in stem_names)
    if not names or any(not name for name in names):
        raise ValueError("Stem names cannot be empty.")
    if len(set(names)) != len(names):
        raise ValueError("Stem names must be unique.")
    unsafe = {"/", "\\", ".."}
    if any(any(token in name for token in unsafe) for name in names):
        raise ValueError("Stem names contain unsafe path characters.")
    return {name: plan.output_directory / safe_stem_filename(name) for name in names}


def validate_stem_results(stem_names, tensors) -> tuple[str, ...]:
    """Validate that model output count matches its dynamically reported sources."""
    names = tuple(str(name).strip() for name in stem_names)
    if not names:
        raise RuntimeError("Separation produced no stem names.")
    try:
        count = len(tensors)
    except TypeError as exc:
        raise RuntimeError("Separation output is not a stem collection.") from exc
    if count != len(names):
        raise RuntimeError(f"Separation returned {count} outputs for {len(names)} stems.")
    return names


def validate_stem_audio(stem_name: str, audio) -> None:
    """Reject empty or malformed model output before a stem is written to disk."""
    if audio is None:
        raise RuntimeError(f"Stem '{stem_name}' contains no audio.")
    numel = getattr(audio, "numel", None)
    if not callable(numel) or numel() <= 0:
        raise RuntimeError(f"Stem '{stem_name}' contains no audio.")


def safe_stem_filename(stem_name: str) -> str:
    """Normalize a model-reported stem label into a Windows-safe WAV filename."""
    name = str(stem_name).strip()
    if not name:
        raise ValueError("Stem name cannot be empty.")
    invalid = '<>:"/\\|?*'
    cleaned = ''.join('_' if ch in invalid or ord(ch) < 32 else ch for ch in name).rstrip(' .')
    if not cleaned:
        raise ValueError("Stem name does not contain a usable filename.")
    reserved = {"CON","PRN","AUX","NUL",*(f"COM{i}" for i in range(1,10)),*(f"LPT{i}" for i in range(1,10))}
    if cleaned.upper() in reserved:
        cleaned = f"_{cleaned}"
    return f"{cleaned}.wav"


def validate_sample_rate(sample_rate: int) -> int:
    """Validate export sample rate before writing separated audio."""
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise ValueError("Sample rate must be a positive integer.")
    return sample_rate


def unique_stem_output_paths(plan: SeparationPlan, stem_names) -> dict[str, Path]:
    """Build collision-free paths after Windows filename normalization."""
    result: dict[str, Path] = {}
    used: set[str] = set()
    for original in stem_names:
        base = safe_stem_filename(original)
        candidate = base
        index = 2
        while candidate.casefold() in used:
            stem = Path(base).stem
            candidate = f"{stem}_{index}.wav"
            index += 1
        used.add(candidate.casefold())
        result[str(original).strip()] = plan.output_directory / candidate
    if not result:
        raise ValueError("Stem names cannot be empty.")
    return result


def ensure_output_paths_are_inside_plan(plan: SeparationPlan, paths: dict[str, Path]) -> None:
    """Guarantee every generated stem remains inside its planned output directory."""
    root = plan.output_directory.resolve()
    for path in paths.values():
        resolved = path.resolve()
        if resolved.parent != root:
            raise ValueError(f"Stem output escapes planned directory: {resolved}")


def verify_exported_stems(paths: dict[str, Path]) -> None:
    """Verify every expected stem file exists and is non-empty after export."""
    if not paths:
        raise RuntimeError("No stem outputs were provided for verification.")
    for name, path in paths.items():
        if not path.is_file():
            raise RuntimeError(f"Stem '{name}' was not exported.")
        if path.stat().st_size == 0:
            raise RuntimeError(f"Stem '{name}' export is empty.")


def validate_model_sample_rate(model) -> int:
    """Read and validate the loaded separation model's sample rate."""
    sample_rate = getattr(model, "samplerate", None)
    if sample_rate is None:
        sample_rate = getattr(model, "sample_rate", None)
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate <= 0:
        raise RuntimeError("Separation model does not expose a valid sample rate.")
    return sample_rate


def validate_model_channels(model) -> int:
    """Validate the channel count expected by a loaded separation model."""
    channels = getattr(model, "audio_channels", None)
    if channels is None:
        channels = getattr(model, "channels", None)
    if isinstance(channels, bool) or not isinstance(channels, int) or channels <= 0:
        raise RuntimeError("Separation model does not expose a valid channel count.")
    return channels


def validate_model_sources(model) -> tuple[str, ...]:
    """Return validated dynamic source names directly from the loaded model."""
    names = discover_model_stems(model)
    folded = [name.casefold() for name in names]
    if len(set(folded)) != len(folded):
        raise RuntimeError("Separation model returned case-insensitive duplicate stem names.")
    return names


def build_export_manifest(plan: SeparationPlan, stem_names) -> dict[str, str]:
    """Create a deterministic manifest of model-reported stems and their output files."""
    paths = unique_stem_output_paths(plan, stem_names)
    ensure_output_paths_are_inside_plan(plan, paths)
    return {name: path.name for name, path in paths.items()}


def completed_export_manifest(plan: SeparationPlan, stem_names) -> dict[str, dict[str, object]]:
    """Return verified export metadata only after every dynamic stem exists on disk."""
    paths = unique_stem_output_paths(plan, stem_names)
    ensure_output_paths_are_inside_plan(plan, paths)
    verify_exported_stems(paths)
    return {
        name: {"filename": path.name, "bytes": path.stat().st_size}
        for name, path in paths.items()
    }


def separation_status(plan: SeparationPlan, stem_names) -> dict[str, object]:
    """Report planned/completed dynamic stem outputs without modifying user files."""
    paths = unique_stem_output_paths(plan, stem_names)
    ensure_output_paths_are_inside_plan(plan, paths)
    completed = [name for name, path in paths.items() if path.is_file() and path.stat().st_size > 0]
    return {
        "source": str(plan.source),
        "output_directory": str(plan.output_directory),
        "stems": tuple(paths.keys()),
        "completed": tuple(completed),
        "complete": len(completed) == len(paths) and bool(paths),
    }


def separation_progress(plan: SeparationPlan, stem_names) -> tuple[int, int, float]:
    """Return completed count, total count, and percentage for dynamic stems."""
    status = separation_status(plan, stem_names)
    total = len(status["stems"])
    completed = len(status["completed"])
    percent = (completed / total * 100.0) if total else 0.0
    return completed, total, percent


def separation_summary(plan: SeparationPlan, stem_names) -> str:
    """Create a concise UI-ready status line for any dynamic stem model."""
    completed, total, percent = separation_progress(plan, stem_names)
    if total == 0:
        return "No stems detected"
    if completed == total:
        return f"Complete — {total} stems exported"
    return f"Separating — {completed}/{total} stems ({percent:.0f}%)"


def load_separator(plan: SeparationPlan):
    """Load Demucs through its Python API; never spawn the packaged executable."""
    return load_separator_for_plan(plan)


def separate_with_demucs(plan: SeparationPlan) -> dict[str, Path]:
    """Run real separation through Demucs' Python API and export every model-provided stem."""
    from demucs.api import save_audio
    separator = load_separator(plan)
    _, sources = separator.separate_audio_file(plan.source)
    if not isinstance(sources, dict) or not sources:
        raise RuntimeError("Demucs returned no separated stems.")
    names = tuple(str(name).strip() for name in sources)
    paths = unique_stem_output_paths(plan, names)
    ensure_output_paths_are_inside_plan(plan, paths)
    prepare_output_directory(plan)
    samplerate = validate_sample_rate(separator.samplerate)
    for name, audio in sources.items():
        validate_stem_audio(name, audio)
        save_audio(audio, paths[name], samplerate=samplerate)
    verify_exported_stems(paths)
    return paths


def separate_audio(source: str | Path, output_root: str | Path | None = None, model_name: str = "htdemucs", device: str = "auto") -> dict[str, Path]:
    """Public end-to-end separation entry point used by the future UI and packaged app."""
    plan = create_separation_plan(source, output_root=output_root, model_name=model_name, device=device)
    return separate_with_demucs(plan)


def load_separator_for_plan(plan: SeparationPlan, separator_factory=None):
    """Create a separator with dependency injection for reliable packaging/tests."""
    if separator_factory is None:
        from demucs.api import Separator
        separator_factory = Separator
    return separator_factory(model=plan.model_name, device=resolve_device(plan.device), progress=False)


def separator_runtime_status(plan: SeparationPlan) -> dict[str, object]:
    """Report package/runtime readiness without downloading a Demucs model."""
    try:
        import demucs.api
        demucs_ready = True
    except (ImportError, ModuleNotFoundError):
        demucs_ready = False
    device = resolve_device(plan.device)
    return {"demucs_available": demucs_ready, "device": device, "model_name": plan.model_name, "ready": demucs_ready}


def model_cache_directory() -> Path:
    """Return Demucs/Torch hub checkpoint cache location without downloading anything."""
    import os
    torch_home = os.environ.get("TORCH_HOME")
    base = Path(torch_home).expanduser() if torch_home else Path.home() / ".cache" / "torch"
    return (base / "hub" / "checkpoints").resolve()


def model_cache_status() -> dict[str, object]:
    """Summarize locally cached separation checkpoints for first-run UI."""
    root = model_cache_directory()
    files = tuple(sorted((p for p in root.glob("*") if p.is_file()), key=lambda p: p.name.casefold())) if root.is_dir() else ()
    return {"directory": str(root), "exists": root.is_dir(), "files": tuple(p.name for p in files), "bytes": sum(p.stat().st_size for p in files)}


def separation_preflight(plan: SeparationPlan) -> dict[str, object]:
    """Validate everything possible before model loading or checkpoint download."""
    source = validate_audio_input(plan.source)
    runtime = separator_runtime_status(plan)
    cache = model_cache_status()
    return {
        "source": str(source),
        "output_directory": str(plan.output_directory),
        "model_name": plan.model_name,
        "device": runtime["device"],
        "runtime_ready": runtime["ready"],
        "cache_directory": cache["directory"],
        "cached_files": cache["files"],
    }


def separation_result(plan: SeparationPlan, paths: dict[str, Path]) -> dict[str, object]:
    """Build verified UI-ready metadata after a successful real separation."""
    ensure_output_paths_are_inside_plan(plan, paths)
    verify_exported_stems(paths)
    return {
        "source": str(plan.source),
        "output_directory": str(plan.output_directory),
        "model_name": plan.model_name,
        "stems": {name: str(path) for name, path in paths.items()},
        "count": len(paths),
        "bytes": sum(path.stat().st_size for path in paths.values()),
    }


def run_separation(source: str | Path, output_root: str | Path | None = None, model_name: str = "htdemucs", device: str = "auto") -> dict[str, object]:
    """Complete public workflow: preflight, real separation, then verified result metadata."""
    plan = create_separation_plan(source, output_root=output_root, model_name=model_name, device=device)
    preflight = separation_preflight(plan)
    if not preflight["runtime_ready"]:
        raise RuntimeError("Demucs runtime is not available.")
    paths = separate_with_demucs(plan)
    return separation_result(plan, paths)


def model_cache_has_files() -> bool:
    """Return whether any local separation checkpoint is already cached."""
    return bool(model_cache_status()["files"])


def first_run_status(plan: SeparationPlan) -> dict[str, object]:
    """Return UI-ready first-run state before any model acquisition begins."""
    preflight = separation_preflight(plan)
    cached = model_cache_has_files()
    return {
        **preflight,
        "model_cached": cached,
        "requires_model_download": bool(preflight["runtime_ready"]) and not cached,
    }


def ensure_separation_ready(plan: SeparationPlan, allow_model_download: bool = False) -> dict[str, object]:
    """Enforce explicit consent before a first-run model download can occur."""
    status = first_run_status(plan)
    if not status["runtime_ready"]:
        raise RuntimeError("Demucs runtime is not available.")
    if status["requires_model_download"] and not allow_model_download:
        raise RuntimeError("Separation model is not cached; model download approval is required.")
    return status
