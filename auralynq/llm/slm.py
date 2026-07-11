"""SLM helpers: GPU detection and GGUF model resolution.

Keeps all hardware-detection and download logic out of the factory so it can
be patched or replaced independently.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from auralynq.telemetry import get_logger

_log = get_logger("auralynq.llm.slm")


def gpu_available() -> bool:
    """Return True if at least one CUDA GPU is accessible.

    Avoids importing torch (which is heavy) by checking:
      1. nvidia-smi -L (instant, requires NVIDIA drivers)
      2. /dev/nvidia0   (Linux sentinel node)
      3. torch.cuda     (if torch is already imported in this process)
    """
    try:
        r = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            timeout=2,
        )
        if r.returncode == 0 and b"GPU" in r.stdout:
            return True
    except Exception:
        pass

    if Path("/dev/nvidia0").exists():
        return True

    try:
        import sys

        torch = sys.modules.get("torch")
        if torch is not None:
            return bool(torch.cuda.is_available())
    except Exception:
        pass

    return False


def resolve_n_gpu_layers(configured: int) -> int:
    """Map the configured slm_n_gpu_layers value to a concrete llama.cpp integer.

    configured == -1  →  auto: all layers on GPU when CUDA is present, 0 otherwise.
    configured ==  0  →  force CPU (no offload).
    configured  > 0   →  offload exactly that many transformer blocks to GPU.
    """
    if configured == -1:
        layers = -1 if gpu_available() else 0
        _log.info("slm.gpu_layers_auto", gpu_present=layers != 0, n_gpu_layers=layers)
        return layers
    return configured


def resolve_model_path(repo: str, filename: str, hf_token: str = "") -> str | None:
    """Return a local path to the GGUF file, downloading it from HuggingFace if needed.

    Uses the HF Hub cache (~/.cache/huggingface/hub/) so subsequent calls are instant.
    Returns None and logs a warning if the download fails or huggingface_hub is missing.
    """
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        _log.warning("slm.hf_hub_missing", hint="uv pip install huggingface_hub")
        return None

    try:
        kwargs: dict[str, str] = {"repo_id": repo, "filename": filename}
        if hf_token:
            kwargs["token"] = hf_token
        path = hf_hub_download(**kwargs)  # type: ignore[call-overload]
        _log.info("slm.model_ready", path=path, repo=repo)
        return path
    except Exception as exc:
        _log.warning("slm.download_failed", repo=repo, filename=filename, error=str(exc))
        return None
