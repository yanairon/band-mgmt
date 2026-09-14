"""Chart model -> MusicXML 4.0.

Encoding notes (MusicXML 4.0 reference):
- Rhythm slashes: <notehead>slash</notehead> on B4 with <stem>none</stem>,
  one per beat, centred on the treble staff.
- <harmony> children in spec order: root, kind, (inversion), (bass), (degree).
  kind's text attribute controls the printed suffix.
- Section repeats -> heavy-light/light-heavy barlines with <repeat>;
  volta endings -> <ending number type="start|stop"/> on barlines. The
  backward repeat sits on the first ending's closing barline.
- New systems -> <print new-system="yes"/> at each section start, at each
  explicit break, and every bars_per_system bars.
- N.C. -> a <words> direction (kind="none" parses but engraves nothing
  in Verovio; the text direction is what actually shows).

Returns the XML plus an overlay spec: Hebrew/boxed section labels and the
boxed roadmap lines are NOT encoded in MusicXML (Verovio drops Hebrew text
entirely), they are drawn into the SVG afterwards by the verovio backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from xml.sax.saxutils import escape

from ..model import Bar, Chart, Section, _split_bar, _DURATIONS

DIVISIONS = 4  # per quarter note; whole note = 16

_TOKEN_TO_FRAC = {v: k for k, v in _DURATIONS.items()}


def _split_bar_fracs(bar_len, n: int):
    """_split_bar returns LilyPond duration tokens; map back to Fractions."""
    return [_TOKEN_TO_FRAC[t] for t in _split_bar(bar_len, n)]

# LilyPond note names (as produced by model._note) -> (step, alter, fifths in major)
_LY_PITCH = {
    "c": ("C", 0, 0), "d": ("D", 0, 2), "e": ("E", 0, 4), "f": ("F", 0, -1),
    "g": ("G", 0, 1), "a": ("A", 0, 3), "b": ("B", 0, 5),
    "cis": ("C", 1, 7), "dis": ("D", 1, 9), "eis": ("E", 1, 11), "fis": ("F", 1, 6),
    "gis": ("G", 1, 8), "ais": ("A", 1, 10), "bis": ("B", 1, 12),
    "ces": ("C", -1, -7), "des": ("D", -1, -5), "ees": ("E", -1, -3),
    "fes": ("F", -1, -8), "ges": ("G", -1, -6), "aes": ("A", -1, -4),
    "bes": ("B", -1, -2),
}

# chord quality suffix -> (MusicXML kind-value, printed text, extra degrees)
_QUALITIES = [
    ("mmaj7", "major-minor", "m(maj7)", None),
    ("maj7", "major-seventh", "maj7", None),
    ("m7b5", "half-diminished", "m7b5", None),
    ("dim7", "diminished-seventh", "dim7", None),
    ("dim", "diminished", "dim", None),
    ("aug", "augmented", "+", None),
    ("sus4", "suspended-fourth", "sus4", None),
    ("sus2", "suspended-second", "sus2", None),
    ("add9", "major", "add9", [("9", 0, "add")]),
    ("7b9", "dominant", "7b9", [("9", -1, "add")]),
    ("m7", "minor-seventh", "m7", None),
    ("m6", "minor-sixth", "m6", None),
    ("m9", "minor-ninth", "m9", None),
    ("m", "minor", "m", None),
    ("7", "dominant", "7", None),
    ("6", "major-sixth", "6", None),
    ("9", "dominant-ninth", "9", None),
    ("5", "power", "5", None),
    ("", "major", "", None),
]

_BARLINES = {
    "|.": '<bar-style>light-heavy</bar-style>',
    "||": '<bar-style>light-light</bar-style>',
    ".|": '<bar-style>light-heavy</bar-style>',
    ":|.": '<bar-style>light-heavy</bar-style><repeat direction="backward"/>',
    ".|:": '<bar-style>heavy-light</bar-style><repeat direction="forward"/>',
}


@dataclass
class OverlayLabel:
    text: str
    boxed: bool
    bar_number: int
    system_index: int          # 0-based system on which the section starts


@dataclass
class OverlayRoadmap:
    text: str
    system_index: int          # 0-based LAST system of the section it follows


@dataclass
class Overlay:
    title: str
    composer: str
    labels: list[OverlayLabel] = field(default_factory=list)
    roadmaps: list[OverlayRoadmap] = field(default_factory=list)
    total_systems: int = 0


def _fifths(chart: Chart) -> int:
    fifths = _LY_PITCH[chart.key_root][2]
    if chart.key_mode == "minor":
        fifths -= 3
    return fifths


def _chord_xml(symbol: str) -> str:
    text = symbol.strip()
    bass = None
    if "/" in text:
        text, bass = text.split("/", 1)
    root_letter = text[0].upper()
    rest = text[1:]
    alter = 0
    while rest[:1] in ("b", "#"):
        alter += -1 if rest[0] == "b" else 1
        rest = rest[1:]
    kind, kind_text, degrees = "major", rest, None
    for suffix, k, ktext, deg in _QUALITIES:
        if rest == suffix:
            kind, kind_text, degrees = k, ktext, deg
            break
    alter_xml = f"<root-alter>{alter}</root-alter>" if alter else ""
    parts = ['<harmony print-frame="no">',
             f"<root><root-step>{root_letter}</root-step>{alter_xml}</root>",
             f'<kind text="{escape(kind_text)}">{kind}</kind>']
    if bass:
        b_step, b_alter = bass[0].upper(), 0
        for ch in bass[1:]:
            b_alter += -1 if ch == "b" else (1 if ch == "#" else 0)
        b_alter_xml = f"<bass-alter>{b_alter}</bass-alter>" if b_alter else ""
        parts.append(f"<bass><bass-step>{b_step}</bass-step>{b_alter_xml}</bass>")
    for value, d_alter, d_type in degrees or []:
        parts.append(f"<degree><degree-value>{value}</degree-value>"
                     f"<degree-alter>{d_alter}</degree-alter>"
                     f"<degree-type>{d_type}</degree-type></degree>")
    parts.append("</harmony>")
    return "".join(parts)


def _slash(duration_frac: Fraction) -> str:
    """One slash notehead of the given fraction of a whole note."""
    quarter = Fraction(1, 4)
    if duration_frac == quarter:
        ntype = "quarter"
    elif duration_frac == Fraction(1, 8):
        ntype = "eighth"
    elif duration_frac == Fraction(1, 2):
        ntype = "half"
    elif duration_frac == Fraction(1, 16):
        ntype = "16th"
    else:
        ntype = "quarter"  # fallback; beats are quarter/eighth in practice
    divs = int(duration_frac * 16)
    return ("<note><pitch><step>B</step><octave>4</octave></pitch>"
            f"<duration>{divs}</duration><voice>1</voice>"
            f"<type>{ntype}</type><stem>none</stem>"
            "<notehead>slash</notehead></note>")


def _words(text: str, size: int = 11, bold: bool = True) -> str:
    weight = ' font-weight="bold"' if bold else ""
    return (f'<direction placement="above"><direction-type>'
            f'<words font-size="{size}"{weight} xml:space="preserve">'
            f'{escape(text)}</words></direction-type></direction>')


class _Emitter:
    """Walks the Chart and emits measures, tracking systems for the overlay."""

    def __init__(self, chart: Chart):
        self.chart = chart
        self.measure_no = 0
        self.system_index = 0
        self.pending_new_system = False
        self.bars_in_system = 0
        self.overlay = Overlay(title=chart.title, composer=chart.artist)
        self.measures: list[str] = []

    def _measure(self, body: list[str]) -> None:
        self.measure_no += 1
        head = ""
        if self.measure_no == 1:
            head = "<print/>"
            self.bars_in_system = 0
        elif self.pending_new_system:
            head = '<print new-system="yes"/>'
            self.system_index += 1
            self.pending_new_system = False
            self.bars_in_system = 0
        self.measures.append(f'<measure number="{self.measure_no}">{head}{"".join(body)}</measure>')
        self.bars_in_system += 1

    def _bar_body(self, bar: Bar) -> list[str]:
        out: list[str] = []
        if len(bar.chords) == 1 and bar.chords[0].strip() in ("N.C.", "NC", "nc"):
            out.append(_words("N.C."))
        else:
            durs = _split_bar_fracs(self.chart.bar_length, len(bar.chords))
            for chord, dur in zip(bar.chords, durs):
                out.append(_chord_xml(chord))
                # one slash per beat within this chord's share
                beat = Fraction(1, self.chart.time_den)
                n = int(dur / beat)
                out.extend(_slash(beat) for _ in range(n))
        return out

    def _close_bar(self, bar: Bar, body: list[str], *, final: bool = False) -> None:
        if bar.barline_after and bar.barline_after in _BARLINES:
            body.append(f'<barline location="right">{_BARLINES[bar.barline_after]}</barline>')
        elif final:
            body.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')

    def emit_section(self, sec: Section, index: int) -> None:
        first_section = index == 0
        start_bar = self.chart.start_bar(index)
        if not first_section:
            self.pending_new_system = True  # sections start on a fresh system
        # overlay label sits on the system this section will start
        if sec.label:
            self.overlay.labels.append(OverlayLabel(
                text=sec.label, boxed=sec.boxed, bar_number=start_bar,
                system_index=self.system_index + (1 if self.pending_new_system else 0)))

        do_repeat = bool(sec.repeat and sec.repeat > 1)
        has_endings = bool(sec.endings)
        # (ending_number | None, bars, backward_repeat_on_last_bar)
        groups: list[tuple[int | None, list[Bar], bool]] = [
            (None, sec.bars, do_repeat and not has_endings)]
        for ei, ending in enumerate(sec.endings):
            groups.append((ei + 1, ending, do_repeat and ei == 0))

        prefix: list[str] = []
        if first_section:
            c = self.chart
            prefix.append(f"<attributes><divisions>{DIVISIONS}</divisions>"
                          f"<key><fifths>{_fifths(c)}</fifths></key>"
                          f"<time><beats>{c.time_num}</beats><beat-type>{c.time_den}</beat-type></time>"
                          "<clef><sign>G</sign><line>2</line></clef></attributes>")
        if do_repeat:
            prefix.append('<barline location="left"><bar-style>heavy-light</bar-style>'
                          '<repeat direction="forward"/></barline>')

        for gi, (ending_no, bars, back_rep) in enumerate(groups):
            last_group = gi == len(groups) - 1
            # proactive break: a group that would overflow the system starts a fresh one
            if (not first_section or self.measure_no > 0) and self.bars_in_system > 0 and \
                    self.bars_in_system + len(bars) > self.chart.bars_per_system:
                self.pending_new_system = True
            for i, bar in enumerate(bars):
                body: list[str] = []
                if prefix:
                    body, prefix = prefix, []
                if i == 0 and ending_no is not None:
                    body.append(f'<barline location="left"><ending number="{ending_no}" '
                                f'type="start"/></barline>')
                body.extend(self._bar_body(bar))
                last = i == len(bars) - 1
                if last and ending_no is not None:
                    rep = '<repeat direction="backward"/>' if back_rep else ""
                    body.append(f'<barline location="right"><bar-style>light-heavy</bar-style>'
                                f'<ending number="{ending_no}" type="stop"/>{rep}</barline>')
                elif last and back_rep:
                    body.append('<barline location="right"><bar-style>light-heavy</bar-style>'
                                '<repeat direction="backward"/></barline>')
                else:
                    self._close_bar(bar, body,
                                    final=bool(sec.final_barline) and last and last_group)
                self._measure(body)
                if not last and (bar.break_after
                                 or self.bars_in_system >= self.chart.bars_per_system):
                    self.pending_new_system = True
                elif last and bar.break_after:
                    self.pending_new_system = True

        if sec.roadmap_after:
            last_system = self.system_index  # section ends on the current system
            for text in sec.roadmap_after:
                self.overlay.roadmaps.append(OverlayRoadmap(text=text, system_index=last_system))

    def finish(self) -> tuple[str, Overlay]:
        self.overlay.total_systems = self.system_index + 1
        c = self.chart
        return (f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN"
  "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <work><work-title>{escape(c.title)}</work-title></work>
  <identification><creator type="composer">{escape(c.artist)}</creator></identification>
  <part-list><score-part id="P1"><part-name>{escape(c.instrument)}</part-name></score-part></part-list>
  <part id="P1">{"".join(self.measures)}</part>
</score-partwise>
""", self.overlay)


def to_musicxml(chart: Chart) -> tuple[str, Overlay]:
    em = _Emitter(chart)
    for i, sec in enumerate(chart.sections):
        em.emit_section(sec, i)
    return em.finish()
