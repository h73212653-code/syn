"""Reproducción de audio con pygame-ce (importado como ``pygame``)."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

# Debe definirse antes de importar pygame para no ensuciar la TUI.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402  (el orden de importación es intencional)


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class PlaybackError(RuntimeError):
    """Error controlado de inicialización o carga de audio."""


class Player:
    """Pequeño envoltorio síncrono alrededor de ``pygame.mixer.music``.

    Las operaciones de pygame son rápidas y se ejecutan en el hilo de la UI;
    así evitamos condiciones de carrera al cambiar de pista.
    """

    def __init__(self, volume: float = 0.82) -> None:
        self._volume = max(0.0, min(1.0, volume))
        self._last_volume = self._volume or 0.82
        self._muted = False
        self._initialized = False
        self._current: Path | None = None
        self._state = PlaybackState.STOPPED

    @property
    def state(self) -> PlaybackState:
        return self._state

    @property
    def volume(self) -> float:
        """Volumen recordado, entre 0.0 y 1.0."""
        return self._volume

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def effective_volume(self) -> float:
        return 0.0 if self._muted else self._volume

    @property
    def current(self) -> Path | None:
        return self._current

    @property
    def initialized(self) -> bool:
        return self._initialized

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        try:
            pygame.mixer.pre_init(44100, -16, 2, 2048)
            pygame.mixer.init()
        except Exception as exc:  # pygame.error y errores de dispositivo
            raise PlaybackError(
                "No se pudo inicializar el audio. "
                "Comprueba que PipeWire/PulseAudio esté activo."
            ) from exc
        self._initialized = True
        self._apply_volume()

    def _apply_volume(self) -> None:
        if not self._initialized:
            return
        try:
            pygame.mixer.music.set_volume(self.effective_volume)
        except pygame.error:
            pass

    def set_volume(self, value: float) -> float:
        """Fija el volumen (0.0–1.0). Desmutea si se sube el volumen."""
        self._volume = max(0.0, min(1.0, value))
        if self._volume > 0:
            self._last_volume = self._volume
            self._muted = False
        self._apply_volume()
        return self._volume

    def change_volume(self, delta: float) -> float:
        return self.set_volume(self._volume + delta)

    def toggle_mute(self) -> bool:
        """Silencia o restaura el volumen anterior. Devuelve si está muteado."""
        self._muted = not self._muted
        if not self._muted and self._volume <= 0:
            self._volume = self._last_volume
        self._apply_volume()
        return self._muted

    def play(self, path: Path) -> None:
        """Carga y reproduce una pista desde el principio."""
        self._ensure_initialized()
        self._state = PlaybackState.STOPPED
        self._current = None

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(str(path))
            self._apply_volume()
            pygame.mixer.music.play()
        except Exception as exc:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            raise PlaybackError(
                f"No se pudo reproducir «{path.name}»: {exc}"
            ) from exc

        self._current = path
        self._state = PlaybackState.PLAYING

    def toggle_pause(self) -> PlaybackState:
        """Pausa o reanuda. Devuelve el estado resultante."""
        if self._current is None:
            return PlaybackState.STOPPED
        try:
            if self._state is PlaybackState.PLAYING:
                pygame.mixer.music.pause()
                self._state = PlaybackState.PAUSED
            elif self._state is PlaybackState.PAUSED:
                pygame.mixer.music.unpause()
                self._state = PlaybackState.PLAYING
        except pygame.error:
            self._state = PlaybackState.STOPPED
        return self._state

    def stop(self) -> None:
        if self._initialized:
            try:
                pygame.mixer.music.stop()
            except pygame.error:
                pass
        self._state = PlaybackState.STOPPED
        self._current = None

    def position(self) -> float:
        """Segundos transcurridos de la pista actual."""
        if not self._initialized or self._current is None:
            return 0.0
        try:
            milliseconds = pygame.mixer.music.get_pos()
        except pygame.error:
            return 0.0
        if milliseconds is None or milliseconds < 0:
            return 0.0
        return milliseconds / 1000.0

    def finished(self) -> bool:
        """True solo si la pista estaba sonando y llegó al final."""
        if (
            not self._initialized
            or self._current is None
            or self._state is not PlaybackState.PLAYING
        ):
            return False
        try:
            return not pygame.mixer.music.get_busy()
        except pygame.error:
            return False

    def shutdown(self) -> None:
        """Detiene la música y libera el dispositivo de audio."""
        if not self._initialized:
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        try:
            pygame.mixer.quit()
        except pygame.error:
            pass
        self._initialized = False
        self._current = None
        self._state = PlaybackState.STOPPED
