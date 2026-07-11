"""Hardware profiler for Auralynq ModelFit Index.

Detects CPU, RAM, GPU, VRAM, backend support, Ollama, HF cache, and disk.
All detection is read-only and purely local - no network calls, no telemetry.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GPUInfo:
    vendor: str  # "nvidia" | "apple" | "amd" | "intel" | "unknown"
    name: str
    vram_gb: float
    backend: str  # "cuda" | "metal" | "rocm" | "cpu"
    device_index: int = 0
    vram_free_gb: float | None = None  # live free VRAM (nvidia-smi memory.free)
    vram_used_gb: float | None = None  # live used VRAM (nvidia-smi memory.used)
    integrated: bool = False  # True for iGPUs / unified-memory (Apple) devices

    def to_dict(self) -> dict[str, Any]:
        return {
            "vendor": self.vendor,
            "name": self.name,
            "vram_gb": self.vram_gb,
            "backend": self.backend,
            "device_index": self.device_index,
            "vram_free_gb": self.vram_free_gb,
            "vram_used_gb": self.vram_used_gb,
            "integrated": self.integrated,
        }


@dataclass
class HardwareProfile:
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    cpu_model: str = ""
    cpu_cores_physical: int = 0
    cpu_cores_logical: int = 0
    cpu_arch: str = ""  # x86_64 | arm64 | ...
    ram_gb: float = 0.0
    gpus: list[GPUInfo] = field(default_factory=list)
    disk_free_gb: float = 0.0
    ollama_available: bool = False
    ollama_version: str | None = None
    hf_available: bool = False
    hf_cache_path: str | None = None
    in_container: bool = False
    cuda_available: bool = False
    cuda_version: str | None = None
    metal_available: bool = False
    rocm_available: bool = False
    # CPU SIMD support - llama.cpp needs AVX2 for usable CPU-only inference speed.
    avx2: bool = False
    avx512: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def best_backend(self) -> str:
        if self.cuda_available:
            return "cuda"
        if self.metal_available:
            return "metal"
        if self.rocm_available:
            return "rocm"
        return "cpu"

    @property
    def total_vram_gb(self) -> float:
        return sum(g.vram_gb for g in self.gpus)

    @property
    def total_vram_free_gb(self) -> float | None:
        """Sum of live free VRAM across GPUs, or None if unreported."""
        frees = [g.vram_free_gb for g in self.gpus if g.vram_free_gb is not None]
        return round(sum(frees), 1) if frees else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "os": {"name": self.os_name, "version": self.os_version},
            "python_version": self.python_version,
            "cpu": {
                "model": self.cpu_model,
                "cores_physical": self.cpu_cores_physical,
                "cores_logical": self.cpu_cores_logical,
                "arch": self.cpu_arch,
                "avx2": self.avx2,
                "avx512": self.avx512,
            },
            "ram_gb": round(self.ram_gb, 1),
            "gpus": [g.to_dict() for g in self.gpus],
            "total_vram_gb": round(self.total_vram_gb, 1),
            "total_vram_free_gb": self.total_vram_free_gb,
            "disk_free_gb": round(self.disk_free_gb, 1),
            "best_backend": self.best_backend,
            "cuda_available": self.cuda_available,
            "cuda_version": self.cuda_version,
            "metal_available": self.metal_available,
            "rocm_available": self.rocm_available,
            "avx2": self.avx2,
            "avx512": self.avx512,
            "ollama_available": self.ollama_available,
            "ollama_version": self.ollama_version,
            "hf_available": self.hf_available,
            "hf_cache_path": self.hf_cache_path,
            "in_container": self.in_container,
            "warnings": self.warnings,
        }


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    """Run a command and return stdout, or '' on any failure. Never raises."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""


def _read_proc_cpuinfo() -> tuple[str, int, set[str]]:
    """Parse /proc/cpuinfo -> (model_name, physical_cores, flags). Linux only."""
    try:
        with open("/proc/cpuinfo") as f:
            content = f.read()
    except OSError:
        return "", 0, set()
    model = ""
    flags: set[str] = set()
    core_ids: set[str] = set()
    for line in content.splitlines():
        if not model and line.startswith("model name"):
            model = line.split(":", 1)[1].strip()
        elif not flags and (line.startswith("flags") or line.startswith("Features")):
            flags = set(line.split(":", 1)[1].split())
        elif line.startswith("core id"):
            core_ids.add(line.split(":", 1)[1].strip())
    return model, len(core_ids), flags


def _sysctl(key: str) -> str:
    """Read a macOS sysctl value, or '' on failure."""
    return _run(["sysctl", "-n", key]).strip()


def _detect_cpu() -> tuple[str, int, int, str, bool, bool]:
    """Return (model, physical_cores, logical_cores, arch, avx2, avx512).

    Robust across Linux (/proc/cpuinfo + lscpu), macOS (sysctl), and Windows
    (PROCESSOR_IDENTIFIER / PowerShell). ``platform.processor()`` is only a last
    resort because it returns '' or bare 'x86_64' on most Linux distributions.
    """
    system = platform.system()
    arch = platform.machine()
    logical = os.cpu_count() or 1
    physical = logical
    model = ""
    avx2 = avx512 = False

    if system == "Linux":
        model, phys, flags = _read_proc_cpuinfo()
        if phys:
            physical = phys
        avx2 = "avx2" in flags
        avx512 = any(f.startswith("avx512") for f in flags)
        if not model:  # some ARM/virtualised hosts omit "model name"
            out = _run(["lscpu"])
            for line in out.splitlines():
                if line.strip().startswith("Model name:"):
                    model = line.split(":", 1)[1].strip()
                    break
    elif system == "Darwin":
        model = _sysctl("machdep.cpu.brand_string")
        physical = int(_sysctl("hw.physicalcpu") or 0) or logical
        # Apple Silicon has no AVX (NEON instead); Intel Macs expose leaf7 flags.
        feats = (
            _sysctl("machdep.cpu.features") + " " + _sysctl("machdep.cpu.leaf7_features")
        ).lower()
        avx2 = "avx2" in feats
        avx512 = "avx512" in feats
    elif system == "Windows":
        model = os.environ.get("PROCESSOR_IDENTIFIER", "")
        ps = _run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        ).strip()
        if ps:
            model = ps

    # psutil gives the most reliable physical-core count when installed.
    try:
        import psutil

        physical = psutil.cpu_count(logical=False) or physical
    except ImportError:
        pass

    if not model:
        model = platform.processor() or "unknown"
    return model, physical, logical, arch, avx2, avx512


def _detect_ram_gb() -> float:
    try:
        import psutil

        return psutil.virtual_memory().total / (1024**3)
    except ImportError:
        pass
    if platform.system() == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return round(kb / (1024**2), 1)
        except OSError:
            pass
    return 0.0


def _detect_nvidia_gpus() -> list[GPUInfo]:
    """Enumerate NVIDIA GPUs with total AND live free/used VRAM.

    Works identically on Linux and Windows (nvidia-smi ships with the driver).
    Free VRAM enables an accurate "will it fit right now" check rather than only
    a theoretical capacity check.
    """
    gpus: list[GPUInfo] = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for i, line in enumerate(result.stdout.strip().splitlines()):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                try:
                    name = parts[0]
                    vram_gb = round(float(parts[1]) / 1024, 1)
                    free_gb = round(float(parts[2]) / 1024, 1) if len(parts) > 2 else None
                    used_gb = round(float(parts[3]) / 1024, 1) if len(parts) > 3 else None
                except ValueError:
                    continue
                gpus.append(
                    GPUInfo(
                        vendor="nvidia",
                        name=name,
                        vram_gb=vram_gb,
                        backend="cuda",
                        device_index=i,
                        vram_free_gb=free_gb,
                        vram_used_gb=used_gb,
                    )
                )
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return gpus


def _detect_windows_gpus() -> list[GPUInfo]:
    """Best-effort Windows GPU enumeration when nvidia-smi found nothing.

    Reads ``HardwareInformation.qwMemorySize`` via PowerShell, which - unlike
    WMI's Win32_VideoController.AdapterRAM - is not capped at 4 GB. Covers AMD
    and Intel/iGPU cases. Never raises.
    """
    if platform.system() != "Windows":
        return []
    ps_cmd = (
        "Get-CimInstance -Namespace root/cimv2 Win32_VideoController | "
        "ForEach-Object { $n=$_.Name; "
        "$k='HKLM:\\SYSTEM\\ControlSet001\\Control\\Class\\"
        "{4d36e968-e325-11ce-bfc1-08002be10318}'; "
        "$m=(Get-ChildItem $k -ErrorAction SilentlyContinue | "
        "ForEach-Object { (Get-ItemProperty $_.PSPath)."
        "'HardwareInformation.qwMemorySize' } | Where-Object { $_ } | "
        "Measure-Object -Maximum).Maximum; "
        '"$n|$m" }'
    )
    out = _run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=15)
    gpus: list[GPUInfo] = []
    for i, line in enumerate(out.strip().splitlines()):
        name, _, mem = line.partition("|")
        name = name.strip()
        if not name:
            continue
        vram_gb = 0.0
        try:
            if mem.strip():
                vram_gb = round(int(mem.strip()) / (1024**3), 1)
        except ValueError:
            vram_gb = 0.0
        lname = name.lower()
        vendor = (
            "amd"
            if ("amd" in lname or "radeon" in lname)
            else ("intel" if "intel" in lname else "unknown")
        )
        gpus.append(
            GPUInfo(
                vendor=vendor,
                name=name,
                vram_gb=vram_gb,
                backend="cpu",  # no CUDA/ROCm runtime assumed on generic Windows
                device_index=i,
                integrated="intel" in lname,
            )
        )
    return gpus


def _detect_apple_silicon() -> list[GPUInfo]:
    if platform.system() != "Darwin":
        return []
    try:
        result = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Apple Silicon shares one pool of RAM between CPU and GPU. macOS caps
            # the GPU working set (Metal recommendedMaxWorkingSetSize) at a
            # fraction of total RAM that rises with capacity: smaller machines
            # keep proportionally more for the OS.
            ram_gb = _detect_ram_gb()
            fraction = 0.65 if ram_gb <= 8 else 0.70 if ram_gb <= 18 else 0.75
            vram_est = round(ram_gb * fraction, 1)
            # Prefer the marketing chip name ("Apple M3 Pro") from the profiler.
            gpu_name = "Apple Silicon"
            for line in result.stdout.splitlines():
                if "Chipset Model:" in line:
                    gpu_name = line.split(":", 1)[1].strip()
                    break
            else:
                gpu_name = _sysctl("machdep.cpu.brand_string") or gpu_name
            return [
                GPUInfo(
                    vendor="apple",
                    name=gpu_name,
                    vram_gb=vram_est,
                    backend="metal",
                    device_index=0,
                    integrated=True,
                )
            ]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return []


def _detect_amd_gpus() -> list[GPUInfo]:
    gpus: list[GPUInfo] = []
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--csv"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            for i, line in enumerate(lines[1:], 0):
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        vram_bytes = int(parts[1].strip())
                        gpus.append(
                            GPUInfo(
                                vendor="amd",
                                name=f"AMD GPU {i}",
                                vram_gb=round(vram_bytes / (1024**3), 1),
                                backend="rocm",
                                device_index=i,
                            )
                        )
                    except ValueError:
                        pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return gpus


def _detect_gpus() -> tuple[list[GPUInfo], bool, str | None, bool, bool]:
    """Return (gpus, cuda_avail, cuda_version, metal_avail, rocm_avail)."""
    cuda_available = False
    cuda_version: str | None = None
    metal_available = False
    rocm_available = False

    nvidia = _detect_nvidia_gpus()
    if nvidia:
        cuda_available = True
        try:
            r = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if "release" in line.lower():
                    cuda_version = line.strip()
                    break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cuda_version = "detected (version unknown)"
        return nvidia, cuda_available, cuda_version, metal_available, rocm_available

    # Apple Metal
    if platform.system() == "Darwin":
        apple = _detect_apple_silicon()
        if apple:
            metal_available = True
            return apple, cuda_available, cuda_version, metal_available, rocm_available

    # AMD ROCm
    amd = _detect_amd_gpus()
    if amd:
        rocm_available = True
        return amd, cuda_available, cuda_version, metal_available, rocm_available

    # Try torch as last resort
    try:
        import torch

        if torch.cuda.is_available():
            cuda_available = True
            cuda_version = torch.version.cuda
            count = torch.cuda.device_count()
            gpus: list[GPUInfo] = []
            for i in range(count):
                props = torch.cuda.get_device_properties(i)
                gpus.append(
                    GPUInfo(
                        vendor="nvidia",
                        name=props.name,
                        vram_gb=round(props.total_memory / (1024**3), 1),
                        backend="cuda",
                        device_index=i,
                    )
                )
            return gpus, cuda_available, cuda_version, metal_available, rocm_available
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            metal_available = True
            ram_gb = _detect_ram_gb()
            fraction = 0.65 if ram_gb <= 8 else 0.70 if ram_gb <= 18 else 0.75
            return (
                [
                    GPUInfo(
                        "apple",
                        "Apple MPS",
                        round(ram_gb * fraction, 1),
                        "metal",
                        0,
                        integrated=True,
                    )
                ],
                cuda_available,
                cuda_version,
                metal_available,
                rocm_available,
            )
    except ImportError:
        pass

    # Windows discrete/integrated GPU (AMD/Intel) when no CUDA/ROCm runtime.
    win = _detect_windows_gpus()
    if win:
        return win, cuda_available, cuda_version, metal_available, rocm_available

    return [], cuda_available, cuda_version, metal_available, rocm_available


def _detect_ollama() -> tuple[bool, str | None]:
    if not shutil.which("ollama"):
        return False, None
    try:
        r = subprocess.run(["ollama", "--version"], capture_output=True, text=True, timeout=5)
        version = r.stdout.strip() or r.stderr.strip() or "unknown"
        return True, version
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, None


def _detect_hf() -> tuple[bool, str | None]:
    cache_env = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
    default = Path.home() / ".cache" / "huggingface"
    cache_path = Path(cache_env) if cache_env else default
    available = cache_path.exists()
    return available, str(cache_path) if available else None


def _detect_disk_free_gb() -> float:
    try:
        usage = shutil.disk_usage(Path.home())
        return round(usage.free / (1024**3), 1)
    except OSError:
        return 0.0


def _in_container() -> bool:
    return (
        Path("/.dockerenv").exists()
        or os.environ.get("CONTAINER") == "podman"
        or "KUBERNETES_SERVICE_HOST" in os.environ
    )


def probe_hardware() -> HardwareProfile:
    """Collect a full hardware profile. Never raises - missing data → 0/empty."""
    warnings: list[str] = []

    cpu_model, cpu_physical, cpu_logical, cpu_arch, avx2, avx512 = _detect_cpu()
    ram_gb = _detect_ram_gb()
    if ram_gb == 0.0:
        warnings.append("Could not detect RAM size.")

    gpus, cuda_avail, cuda_ver, metal_avail, rocm_avail = _detect_gpus()
    if not gpus:
        warnings.append("No GPU detected - inference will use CPU only.")
        # AVX2 is the practical floor for tolerable CPU-only llama.cpp inference.
        if cpu_arch.lower() in ("x86_64", "amd64") and not avx2:
            warnings.append(
                "CPU lacks AVX2 - CPU-only inference will be very slow. "
                "Prefer small (≤3B) heavily-quantized models."
            )

    disk_free = _detect_disk_free_gb()
    if disk_free < 10:
        warnings.append(f"Low disk space: {disk_free:.1f} GB free.")

    ollama_avail, ollama_ver = _detect_ollama()
    hf_avail, hf_path = _detect_hf()

    return HardwareProfile(
        os_name=platform.system(),
        os_version=platform.version(),
        python_version=sys.version.split()[0],
        cpu_model=cpu_model,
        cpu_cores_physical=cpu_physical,
        cpu_cores_logical=cpu_logical,
        cpu_arch=cpu_arch,
        ram_gb=round(ram_gb, 1),
        gpus=gpus,
        disk_free_gb=disk_free,
        ollama_available=ollama_avail,
        ollama_version=ollama_ver,
        hf_available=hf_avail,
        hf_cache_path=hf_path,
        in_container=_in_container(),
        cuda_available=cuda_avail,
        cuda_version=cuda_ver,
        metal_available=metal_avail,
        rocm_available=rocm_avail,
        avx2=avx2,
        avx512=avx512,
        warnings=warnings,
    )
