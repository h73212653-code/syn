#!/usr/bin/env python3
"""Banco de pruebas reproducible del consumo de SYN.

Arranca el reproductor real en un pseudo-terminal, espera a que cargue la
biblioteca, reproduce una pista y muestrea CPU/RAM desde ``/proc``. Sirve para
comparar antes/después de una optimización en la misma máquina.

Uso:
    .venv/bin/python tools/benchmark.py
    .venv/bin/python tools/benchmark.py --music-dir ~/Música --gaming
    .venv/bin/python tools/benchmark.py --json /tmp/syn-before.json

El audio se envía al driver «dummy» de SDL para que la prueba sea silenciosa y
no dependa del servidor de sonido; la decodificación y la mezcla siguen
ejecutándose igual.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_VERSION = "1"
DEFAULT_TRACKS = 120
TRACK_SECONDS = 30


@dataclass
class Scenario:
    name: str
    cpu_percent: float
    rss_mb: float
    peak_rss_mb: float
    seconds: float


@dataclass
class Report:
    label: str
    timestamp: str
    git_commit: str
    python: str
    music_dir: str
    tracks: int
    scenarios: list[Scenario] = field(default_factory=list)


def _run_quiet(command: list[str]) -> None:
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"Falló {' '.join(command)}: {detail}")


def ensure_fixture(directory: Path, tracks: int) -> Path:
    """Crea una biblioteca fija (una pista real enlazada N veces)."""
    marker = directory / ".syn-bench-fixture"
    expected = f"{FIXTURE_VERSION}:{tracks}:{TRACK_SECONDS}"
    if marker.is_file() and marker.read_text().strip() == expected:
        return directory

    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True, exist_ok=True)

    base = directory / "base.ogg"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "Se necesita ffmpeg para generar la biblioteca de prueba."
        )
    _run_quiet(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={TRACK_SECONDS}",
            "-c:a",
            "libvorbis",
            "-q:a",
            "1",
            "-y",
            str(base),
        ]
    )

    for index in range(tracks):
        target = directory / f"Pista {index + 1:03d}.ogg"
        try:
            os.link(base, target)  # enlaces duros: la fixture ocupa poquísimo
        except OSError:
            shutil.copyfile(base, target)

    marker.write_text(expected + "\n")
    return directory


def _status_value(pid: int, key: str) -> str | None:
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as file:
            for line in file:
                if line.startswith(f"{key}:"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        return None
    return None


def _rss_mb(pid: int) -> float | None:
    value = _status_value(pid, "VmRSS")
    if not value:
        return None
    try:
        return int(value.split()[0]) / 1024.0
    except (ValueError, IndexError):
        return None


def _cpu_ticks(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        fields = raw.rsplit(") ", 1)[1].split()
        return int(fields[11]) + int(fields[12])
    except (IndexError, ValueError):
        return None


def sample(pid: int, seconds: float, name: str) -> Scenario | None:
    """Mide CPU media y RSS durante ``seconds`` segundos."""
    start_ticks = _cpu_ticks(pid)
    start = time.monotonic()
    rss_values: list[float] = []

    while time.monotonic() - start < seconds:
        rss = _rss_mb(pid)
        if rss is not None:
            rss_values.append(rss)
        time.sleep(0.25)

    elapsed = time.monotonic() - start
    end_ticks = _cpu_ticks(pid)
    if start_ticks is None or end_ticks is None or not rss_values:
        return None

    ticks = max(0, end_ticks - start_ticks)
    cpu = (ticks / os.sysconf("SC_CLK_TCK")) / elapsed * 100.0
    return Scenario(
        name=name,
        cpu_percent=round(cpu, 2),
        rss_mb=round(sum(rss_values) / len(rss_values), 1),
        peak_rss_mb=round(max(rss_values), 1),
        seconds=round(elapsed, 1),
    )


class Terminal:
    """SYN real en un pseudo-terminal, con lectura drenada en segundo plano."""

    def __init__(self, music_dir: Path, extra_args: list[str]) -> None:
        self._tail = bytearray()
        self._stop = threading.Event()
        pid, master = pty.fork()
        if pid == 0:  # hijo
            try:
                os.chdir(ROOT)
                env = os.environ.copy()
                env.update(
                    {
                        "SDL_AUDIODRIVER": "dummy",
                        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
                        "TERM": "xterm-256color",
                        "SYN_MUSIC_DIR": str(music_dir),
                    }
                )
                os.execvpe(
                    sys.executable,
                    [
                        sys.executable,
                        "-m",
                        "syn",
                        "--music-dir",
                        str(music_dir),
                        *extra_args,
                    ],
                    env,
                )
            finally:
                os._exit(127)

        self.pid = pid
        self.master = master
        fcntl.ioctl(
            master,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", 40, 120, 0, 0),
        )
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = os.read(self.master, 65536)
            except OSError:
                break
            if not chunk:
                break
            self._tail.extend(chunk)
            if len(self._tail) > 16384:
                del self._tail[:-8192]

    def send(self, text: str) -> None:
        os.write(self.master, text.encode("utf-8"))

    def alive(self) -> bool:
        try:
            pid, _ = os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            return False
        return pid != self.pid

    def wait(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and self.alive():
            time.sleep(0.05)

    def close(self) -> None:
        self.send("q")
        self.wait(3.0)
        if self.alive():
            try:
                os.kill(self.pid, signal.SIGTERM)
            except OSError:
                pass
            self.wait(2.0)
        if self.alive():
            try:
                os.kill(self.pid, signal.SIGKILL)
            except OSError:
                pass
        self._stop.set()
        try:
            os.close(self.master)
        except OSError:
            pass

    def tail(self) -> str:
        return bytes(self._tail).decode("utf-8", "replace")


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip() or "desconocido"
    except OSError:
        return "desconocido"


def _print_report(report: Report) -> None:
    print()
    print(f"SYN · {report.label}   (commit {report.git_commit})")
    print(f"Música: {report.music_dir} · {report.tracks} pistas")
    print()
    header = f"{'Escenario':<22} {'CPU media':>10} {'RAM media':>11} {'RAM pico':>10}"
    print(header)
    print("-" * len(header))
    for scenario in report.scenarios:
        print(
            f"{scenario.name:<22} "
            f"{scenario.cpu_percent:>9.2f}% "
            f"{scenario.rss_mb:>9.1f} MB "
            f"{scenario.peak_rss_mb:>8.1f} MB"
        )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mide CPU y RAM de SYN de forma reproducible."
    )
    parser.add_argument(
        "--music-dir",
        type=Path,
        help="Biblioteca real a medir (por defecto se genera una fixture).",
    )
    parser.add_argument(
        "--tracks",
        type=int,
        default=DEFAULT_TRACKS,
        help=f"Pistas de la fixture (por defecto {DEFAULT_TRACKS}).",
    )
    parser.add_argument(
        "--startup-wait",
        type=float,
        default=6.0,
        help="Segundos de espera hasta que la biblioteca está cargada.",
    )
    parser.add_argument(
        "--idle-seconds",
        type=float,
        default=10.0,
        help="Duración de la medición en reposo.",
    )
    parser.add_argument(
        "--play-seconds",
        type=float,
        default=10.0,
        help="Duración de la medición reproduciendo.",
    )
    parser.add_argument(
        "--gaming",
        action="store_true",
        help="Pulsa «g» y mide también el Gaming Mode.",
    )
    parser.add_argument(
        "--game-mode-arg",
        default="--game-mode",
        help="Argumento CLI para arrancar directamente en Gaming Mode.",
    )
    parser.add_argument(
        "--start-in-gaming",
        action="store_true",
        help="Arranca SYN en Gaming Mode y mide reposo y reproducción.",
    )
    parser.add_argument("--label", default="medición", help="Nombre de la prueba.")
    parser.add_argument("--json", type=Path, help="Guarda el informe en JSON.")
    args = parser.parse_args()

    if args.music_dir:
        music_dir = args.music_dir.expanduser().resolve()
        tracks = sum(
            1
            for item in music_dir.rglob("*")
            if item.is_file() and item.suffix.lower() in {".mp3", ".flac", ".wav", ".ogg", ".opus", ".m4a"}
        )
    else:
        music_dir = ensure_fixture(
            Path(
                os.environ.get("XDG_CACHE_HOME", "~/.cache")
            ).expanduser()
            / "syn"
            / "bench"
            / "library",
            args.tracks,
        )
        tracks = args.tracks

    extra_args = [args.game_mode_arg] if args.start_in_gaming else []
    terminal = Terminal(music_dir, extra_args)
    report = Report(
        label=args.label,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        git_commit=_git_commit(),
        python=sys.version.split()[0],
        music_dir=str(music_dir),
        tracks=tracks,
    )

    try:
        terminal.wait(args.startup_wait)
        if not terminal.alive():
            print("SYN terminó antes de tiempo. Salida:", file=sys.stderr)
            print(terminal.tail(), file=sys.stderr)
            return 1

        prefix = "Gaming · " if args.start_in_gaming else ""
        idle = sample(terminal.pid, args.idle_seconds, f"{prefix}Reposo")
        if idle:
            report.scenarios.append(idle)

        terminal.send("\r")
        terminal.wait(1.5)
        if not terminal.alive():
            print("SYN se cerró al reproducir. Salida:", file=sys.stderr)
            print(terminal.tail(), file=sys.stderr)
            return 1
        playing = sample(
            terminal.pid, args.play_seconds, f"{prefix}Reproduciendo"
        )
        if playing:
            report.scenarios.append(playing)

        if args.gaming and not args.start_in_gaming:
            terminal.send("g")
            terminal.wait(1.5)
            gaming = sample(terminal.pid, args.play_seconds, "Gaming Mode")
            if gaming:
                report.scenarios.append(gaming)
    finally:
        terminal.close()

    _print_report(report)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(asdict(report), indent=2) + "\n")
        print(f"Informe guardado en {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
