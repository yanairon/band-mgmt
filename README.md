# band-mgmt

Band management tooling. First tool: **chartgen**, a repeatable chord-chart
generator that renders Roi's house-style charts as PDF.

## chartgen: song name / photo -> PDF

The flow for a new chart:

1. **Get the chords.** Either look the song up online (chord sites, tabs) or
   transcribe a photo of a handwritten chart.
2. **Write a small YAML file** describing the song: title, artist, key, time
   signature, and the sections with their bars (see `examples/something.yaml`).
3. **Render:**

   ```sh
   python3 -m chartgen render examples/something.yaml -o examples/something.pdf
   ```

   Requires Python 3.9+ with `PyYAML`, and
   [LilyPond](https://lilypond.org) on the PATH (or pass `--lilypond PATH`).
   Pass `--ly` to also keep the generated `.ly` source.

The output matches Roi's charts: A4, 18pt staff, thin staff lines, bold
centered title with a bold artist on the right, a "Guitar" staff with treble
clef and 4/4 on the first system only, stemless mid-staff slash notation (one
slash per beat, geometry measured from his engraved charts), upright roman
chord names inline above the staff, boxed Hebrew rehearsal marks at section
starts with the start bar folded in, repeat barlines with light volta 1./2.
brackets, centered boxed roadmap lines between sections, bar numbers at the
start of every system, full-width systems, and a heavy final barline.

## Input format

```yaml
title: Something
artist: The Beatles
key: c major          # "bb minor", "f# major", ...
time: 4/4
instrument: Guitar    # staff label
bars_per_system: 8    # auto line-break cadence (default 8)

sections:
  - label: "בית 1"     # boxed rehearsal mark (Hebrew or Latin)
    boxed: true        # set false for a plain bold mark ("CHORUS")
    bars:
      - F              # one chord per bar
      - [C, F]         # two chords in one bar (even split)
      - { chords: G, break: true }        # force a line break after this bar
      - { chords: Am, barline: "|." }     # explicit barline after this bar
```

Each section renders as its own score, so sections start on a fresh system and
short sections still stretch to the full text width. Sections after the first
hide the time signature, and their start bar number is folded under the boxed
label (bar numbers are computed from the written bar counts - add or remove
bars and every later number follows automatically).

Sections can carry Roi's repeat idiom:

```yaml
  - label: "בית"
    repeat: 2          # |: ... :| around the body bars
    bars: [ ... ]      # written once
    endings:           # volta alternatives (1. / 2.), each a list of bars
      - [F, Eb, G]
      - [F, Eb, G, A]
    roadmap_after:     # centered boxed roadmap lines printed after this section
      - "בית 3 - סולו"
      - "בית 4"
    final_barline: true   # heavy |. at the very end of the chart
```

Bar numbering counts written bars (body once + every ending), which is how
Roi numbers his charts.

Chord shorthand: `F`, `Am`, `C7`, `Cmaj7`, `F#m7b5`, `Ddim7`, `Gsus4`,
`Am/G#` (slash chords), `N.C.` (no chord, whole-bar rest). Anything else can
be written in raw LilyPond chordmode with an `ly:` prefix
(e.g. `ly:c2:7.9-`). Bar durations split evenly when possible (2 chords in
4/4 = half notes); 3 chords in 4/4 default to quarter-quarter-half - use raw
`ly:` chords for other rhythms.

Section marks are computed from the bar counts, so boxes never drift from the
music: add or remove bars and the marks follow automatically.

## Layout

```
chartgen/            the generator (python -m chartgen ...)
  model.py           YAML parsing + chord shorthand -> LilyPond chordmode
  lilypond.py        chart model -> .ly source
  style/roi.ily      Roi's house style (staff size, slash glyph, fonts)
examples/
  something.yaml     "Something" (The Beatles), matching Roi's chart
  something.pdf      rendered output
```
