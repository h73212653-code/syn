from dataclasses import dataclass

@dataclass
class Theme:
    name: str
    gradient: list[str]

THEMES = [
    Theme("Neon", ["#22d3ee", "#818cf8", "#e879f9"]),
    Theme("Sunset", ["#fb923c", "#f472b6", "#c026d3"]),
    Theme("Forest", ["#4ade80", "#22c55e", "#166534"]),
    Theme("Ocean", ["#38bdf8", "#0ea5e9", "#0369a1"]),
    Theme("Candy", ["#f472b6", "#db2777", "#9d174d"]),
    Theme("Midnight", ["#818cf8", "#4f46e5", "#312e81"]),
]

class ThemeManager:
    def __init__(self, initial_index: int = 0):
        self.index = initial_index % len(THEMES)

    def get_current(self) -> Theme:
        return THEMES[self.index]

    def cycle(self) -> Theme:
        self.index = (self.index + 1) % len(THEMES)
        return self.get_current()
