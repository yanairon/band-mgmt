"""Parse chart YAML into a model and expand shorthand chords to LilyPond chordmode."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from fractions import Fraction

import yaml

# Duration token for a fraction of a whole note (plain or single-dotted).
_DURATIONS = {
    Fraction(1): "1", Fraction(3, 4): "2.", Fraction(1, 2): "2",
    Fraction(3, 8): "4.", Fraction(1, 4): "4", Fraction(3, 16): "8.",
    Fraction(1, 8): "8", Fraction(1, 16): "16",
}

_NOTE_NAMES = {
    "c": "c", "d": "d", "e": "e", "f": "f", "g": "g", "a": "a", "b": "b",
}

_QUALITIES = {
    "": "", "m": ":m", "7": ":7", "maj7": ":maj7", "M7": ":maj7",
    "m7": ":m7", "mmaj7": ":m+7", "6": ":6", "m6": ":m6",
    "9": ":9", "m9": ":m9", "7b9": ":7.9-", "dim": ":dim", "dim7": ":dim7",
    "m7b5": ":m7.5-", "aug": ":aug", "sus2": ":sus2", "sus4": ":sus4",
    "sus": ":sus4", "add9": ":9", "5": ":5",
}

_CHORD_RE = re.compile(
    r"^([A-Ga-g])(#|b)?(m7b5|maj7|mmaj7|dim7|dim|aug|sus[24]?|add9|m6|m7|m9|m|6|7|9|5)?"
    r"(?:/([A-Ga-g])(#|b)?)?$")


def _note(letter: str, accidental: str | None) -> str:
    name = _NOTE_NAMES[letter.lower()]
    if accidental == "#":
        name += "is"
    elif accidental == "b":
        name += "es"
    return name


def chord_token(token: str, dur: str = "") -> str:
    """Convert a shorthand chord like 'F#m7b5' or 'Am/G#' plus a LilyPond
    duration to chordmode: root + duration + quality + /bass ('fis1:m7.5-/e').
    LilyPond requires the duration before the /bass note."""
    token = token.strip()
    if token.startswith("ly:"):  # explicit chordmode passthrough, carries own duration
        return token[3:]
    if token in ("N.C.", "NC", "nc"):  # no chord: whole-bar rest
        return "r" + (dur or "1")
    m = _CHORD_RE.match(token)
    if not m:
        raise ValueError(f"unrecognized chord: {token!r} "
                         f"(use 'ly:<chordmode>' for explicit LilyPond syntax)")
    out = _note(m.group(1), m.group(2)) + dur + _QUALITIES[m.group(3) or ""]
    if m.group(4):
        out += "/" + _note(m.group(4), m.group(5))
    return out


def _duration_token(frac: Fraction) -> str:
    if frac in _DURATIONS:
        return _DURATIONS[frac]
    raise ValueError(f"cannot express duration {frac} as a plain/dotted note")


def _split_bar(bar_len: Fraction, n: int) -> list[str]:
    """Split a bar into n chord durations. Even split when possible, else
    greedy quarter-up allocation (3 chords in 4/4 -> 4 4 2)."""
    if n == 1:
        return [_duration_token(bar_len)]
    each = bar_len / n
    if each in _DURATIONS:
        return [_DURATIONS[each]] * n
    out, remaining = [], bar_len
    for i in range(n - 1):
        share = remaining / (n - i)
        dur = max(f for f in _DURATIONS if f <= share)
        out.append(_DURATIONS[dur])
        remaining -= dur
    out.append(_duration_token(remaining))
    return out


@dataclass
class Bar:
    chords: list[str]            # shorthand chord tokens
    break_after: bool = False
    barline_after: str | None = None  # e.g. ":|." for a repeat end


@dataclass
class Section:
    label: str | None
    boxed: bool
    bars: list[Bar] = field(default_factory=list)
    repeat: int = 0                    # >1 wraps bars in \repeat volta N
    endings: list[list[Bar]] = field(default_factory=list)  # volta alternatives
    roadmap_after: list[str] = field(default_factory=list)  # centered boxes after section
    final_barline: bool = False        # append \bar "|."

    @property
    def written_bars(self) -> int:
        """Bars as printed once (body + all volta endings). Drives bar numbering."""
        return len(self.bars) + sum(len(e) for e in self.endings)


@dataclass
class Chart:
    title: str
    artist: str
    key_root: str
    key_mode: str
    time_num: int
    time_den: int
    instrument: str
    bars_per_system: int
    sections: list[Section]

    @property
    def bar_length(self) -> Fraction:
        return Fraction(self.time_num, self.time_den)

    def start_bar(self, index: int) -> int:
        """1-based written-bar number at which sections[index] starts."""
        return 1 + sum(s.written_bars for s in self.sections[:index])


def _parse_bar(raw) -> Bar:
    """A bar is: a chord string, a list of chord strings, or a mapping with
    chords/break/barline keys."""
    if isinstance(raw, str):
        return Bar([raw])
    if isinstance(raw, list):
        return Bar([str(c) for c in raw])
    if isinstance(raw, dict):
        chords = raw.get("chords")
        if isinstance(chords, str):
            chords = [chords]
        if not chords:
            raise ValueError(f"bar mapping missing 'chords': {raw!r}")
        return Bar([str(c) for c in chords],
                   break_after=bool(raw.get("break", False)),
                   barline_after=raw.get("barline"))
    raise ValueError(f"unsupported bar entry: {raw!r}")


def parse_chart(data: dict) -> Chart:
    key = str(data.get("key", "c major")).split()
    if len(key) != 2 or key[0].lower() not in _NOTE_NAMES and not re.match(
            r"^[A-Ga-g](#|b)?$", key[0]):
        raise ValueError(f"key must look like 'c major' or 'bb minor', got {data.get('key')!r}")
    root_m = re.match(r"^([A-Ga-g])(#|b)?$", key[0])
    key_root = _note(root_m.group(1), root_m.group(2))
    key_mode = key[1].lower()
    if key_mode not in ("major", "minor"):
        raise ValueError("key mode must be 'major' or 'minor'")
    time_m = re.match(r"^(\d+)/(\d+)$", str(data.get("time", "4/4")))
    if not time_m:
        raise ValueError(f"time must look like '4/4', got {data.get('time')!r}")
    sections = []
    for raw_sec in data.get("sections", []):
        if isinstance(raw_sec, str):
            raw_sec = {"label": raw_sec, "bars": []}
        endings = [[_parse_bar(b) for b in ending]
                   for ending in raw_sec.get("endings", [])]
        sections.append(Section(
            label=raw_sec.get("label"),
            boxed=bool(raw_sec.get("boxed", True)),
            bars=[_parse_bar(b) for b in raw_sec.get("bars", [])],
            repeat=int(raw_sec.get("repeat", 0) or 0),
            endings=endings,
            roadmap_after=[str(t) for t in raw_sec.get("roadmap_after", [])],
            final_barline=bool(raw_sec.get("final_barline", False)),
        ))
    if not sections:
        raise ValueError("chart has no sections")
    return Chart(
        title=str(data.get("title", "Untitled")),
        artist=str(data.get("artist", "")),
        key_root=key_root, key_mode=key_mode,
        time_num=int(time_m.group(1)), time_den=int(time_m.group(2)),
        instrument=str(data.get("instrument", "Guitar")),
        bars_per_system=int(data.get("bars_per_system", 8)),
        sections=sections,
    )


def load_chart(path: str) -> Chart:
    with open(path, encoding="utf-8") as fh:
        return parse_chart(yaml.safe_load(fh))
