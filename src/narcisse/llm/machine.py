"""What this machine can run: its memory, its processor, its graphics cards, and the model
size that suits them.

Read without any extra dependency, from what each system offers. Whatever can't be read is
"unknown", never an error: the recommendation then errs on the small side.
"""

import ctypes
import json
import logging
import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
COMMAND_TIMEOUT = 10.0
# Graphics cards with their own memory (an integrated one shares the RAM).
DEDICATED = ("nvidia", "radeon rx", "radeon pro", "arc a", "arc b")

# Runs a command, its output or None (missing, failed, too slow).
Command = Callable[[list[str]], str | None]


def run(args: list[str]) -> str | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        done = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            creationflags=NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


@dataclass(frozen=True)
class Gpu:
    name: str
    memory_gb: float | None  # its own memory (None: unknown, or shared with the RAM)
    dedicated: bool


@dataclass(frozen=True)
class Machine:
    system: str  # "Windows", "Darwin", "Linux"
    memory_gb: float | None
    cores: int | None
    gpus: tuple[Gpu, ...] = field(default_factory=tuple)
    # Apple Silicon: the graphics share a fast unified memory, models use most of it.
    unified: bool = False

    @property
    def gpu_memory_gb(self) -> float:
        """The most memory one dedicated card has (0 without one)."""
        return max((g.memory_gb or 0 for g in self.gpus if g.dedicated), default=0)


def _windows_memory() -> float | None:
    class Status(ctypes.Structure):
        _fields_ = (
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        )

    status = Status()
    status.dwLength = ctypes.sizeof(Status)
    windll = getattr(ctypes, "windll", None)
    if windll is None or not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    total: int = status.ullTotalPhys
    return total / 2**30


def _linux_memory(meminfo: Path) -> float | None:
    try:
        for line in meminfo.read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) / 2**20  # kB
    except (OSError, ValueError, IndexError):
        pass
    return None


def _nvidia(command: Command) -> list[Gpu]:
    out = command(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    gpus = []
    for line in (out or "").splitlines():
        name, _, memory = line.partition(",")
        try:
            gpus.append(Gpu(name.strip(), float(memory) / 1024, True))
        except ValueError:
            continue
    return gpus


def _windows_gpus(command: Command) -> list[Gpu]:
    out = command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name | ConvertTo-Json",
        ]
    )
    try:
        data = json.loads(out or "[]")
    except ValueError:
        return []
    rows = data if isinstance(data, list) else [data]
    names = [str(r.get("Name", "")).strip() for r in rows if isinstance(r, dict)]
    # Windows reports at most 4 GB of a card's memory: its size comes from nvidia-smi, if any.
    return [Gpu(n, None, any(d in n.lower() for d in DEDICATED)) for n in names if n]


def _linux_gpus(command: Command) -> list[Gpu]:
    out = command(["lspci"]) or ""
    gpus = []
    for line in out.splitlines():
        if "VGA" in line or "3D controller" in line:
            name = line.split(":", 2)[-1].strip()
            gpus.append(Gpu(name, None, any(d in name.lower() for d in DEDICATED)))
    return gpus


def detect(
    command: Command = run,
    system: str | None = None,
    meminfo: Path = Path("/proc/meminfo"),
) -> Machine:
    system = system or platform.system()
    memory: float | None = None
    gpus: list[Gpu] = []
    unified = False
    try:
        if system == "Windows":
            memory = _windows_memory()
            gpus = _windows_gpus(command)
        elif system == "Darwin":
            out = command(["sysctl", "-n", "hw.memsize"])
            memory = int(out) / 2**30 if out and out.strip().isdigit() else None
            unified = (command(["sysctl", "-n", "machdep.cpu.brand_string"]) or "").startswith(
                "Apple"
            )
        else:
            memory = _linux_memory(meminfo)
            gpus = _linux_gpus(command)
    except Exception:
        log.exception("could not read this machine's resources")
    nvidia = _nvidia(command)
    if nvidia:
        # Exact sizes for NVIDIA cards; the others as the system listed them.
        gpus = nvidia + [g for g in gpus if "nvidia" not in g.name.lower()]
    return Machine(
        system=system,
        memory_gb=round(memory, 1) if memory else None,
        cores=os.cpu_count(),
        gpus=tuple(gpus),
        unified=unified,
    )


@dataclass(frozen=True)
class Recommendation:
    model: str  # the Ollama name
    size_gb: float  # about what it downloads (and takes on disk)
    speed: str  # what to expect: "fast", "processor" (a few tens of seconds), "slow"


# From the smallest: (Ollama name, download size in GB). Gemma 3: good at French and at keeping
# to a JSON shape, with no "thinking" step to wait for; Gemma 4's small models download 6.6 GB
# and more, too much for a machine without a graphics card. Sizes from Ollama's library,
# checked 2026-10-30.
TIERS = (("gemma3:1b", 0.8), ("gemma3:4b", 3.4), ("gemma3:12b", 8.2), ("gemma3:27b", 17.0))


def recommend(machine: Machine) -> Recommendation:
    """The largest model that runs comfortably here."""
    memory = machine.memory_gb or 0
    gpu = machine.gpu_memory_gb
    if gpu >= 20 or (machine.unified and memory >= 48):
        tier, speed = 3, "fast"
    elif gpu >= 10 or (machine.unified and memory >= 24):
        tier, speed = 2, "fast"
    elif gpu >= 6 or (machine.unified and memory >= 16):
        tier, speed = 1, "fast"
    elif memory >= 12:
        tier, speed = 1, "processor"
    else:
        tier, speed = 0, "slow"
    model, size = TIERS[tier]
    return Recommendation(model, size, speed)
