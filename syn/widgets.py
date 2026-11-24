"""Widgets propios de SYN que no dependen de Pillow ni textual-image."""

from __future__ import annotations

from typing import Sequence

from rich.text import Text
from textual import events
from textual.binding import Binding
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from .library import Track, UNKNOWN_ARTIST


class TrackList(OptionList):
    """Lista de pistas con navegación por flechas, j/k y Enter."""

    BINDINGS = [
        Binding("j", "cursor_down", "Abajo", show=False),
        Binding("k", "cursor_up", "Arriba", show=False),
    ]

    def __init__(self, id: str | None = None) -> None:
        super().__init__(compact=True, id=id)
        self._tracks: list[Track] = []
        self._playing_index: int | None = None
        self._paused = False

    @property
    def tracks(self) -> Sequence[Track]:
        return tuple(self._tracks)

    def set_tracks(self, tracks: Sequence[Track]) -> None:
        self._tracks = list(tracks)
        self._playing_index = None
        options = [
            Option(self._prompt(index, track), id=f"track-{index}")
            for index, track in enumerate(self._tracks)
        ]
        self.set_options(options)
        self.highlighted = 0 if options else None

    def set_playback_state(self, index: int | None, paused: bool = False) -> None:
        old_index = self._playing_index
        self._playing_index = index
        self._paused = paused
        for changed_index in {old_index, index}:
            if changed_index is not None and 0 <= changed_index < len(self._tracks):
                self.replace_option_prompt_at_index(
                    changed_index,
                    self._prompt(changed_index, self._tracks[changed_index]),
                )

    def focus_index(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            self.highlighted = index
            self.scroll_to_highlight()

    def on_resize(self, event: events.Resize) -> None:
        if self._tracks:
            self.call_after_refresh(self._refresh_prompts)

    def _refresh_prompts(self) -> None:
        for index in range(min(len(self._tracks), self.option_count)):
            self.replace_option_prompt_at_index(
                index,
                self._prompt(index, self._tracks[index]),
            )

    def _available_prompt_width(self) -> int:
        width = self.scrollable_content_region.width or self.content_size.width
        # El componente option-list--option tiene 1 celda de padding a cada lado.
        return max(12, width - 2)

    def _prompt(self, index: int, track: Track) -> Text:
        playing = index == self._playing_index
        if playing:
            marker = "‖" if self._paused else "▶"
            marker_style = "bold #f0abfc" if self._paused else "bold #67e8f9"
        else:
            marker = " "
            marker_style = ""

        prompt = Text(
            no_wrap=True,
            overflow="ellipsis",
            end="…",
        )
        prompt.append(f"{marker} ", style=marker_style)
        prompt.append(f"{index + 1:02d}  ", style="#475569")
        prompt.append(
            track.title,
            style="bold #a5f3fc" if playing else "bold #e2e8f0",
        )
        if track.artist and track.artist != UNKNOWN_ARTIST:
            prompt.append("  ·  ", style="#334155")
            prompt.append(track.artist, style="#7f8da3")

        # Textual visualiza los prompts con wrapping. Truncamos aquí para que
        # cada canción ocupe exactamente una línea (y no coma filas vecinas).
        prompt.truncate(self._available_prompt_width(), overflow="ellipsis")
        return prompt
