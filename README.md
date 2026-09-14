# band-mgmt

Band management tooling. First tool: **chartgen**, a repeatable chord-chart
generator that renders Roi's house-style charts as PDF.

## chartgen: song name / photo -> PDF

The flow for a new chart:

1. **Get the chords.** Either look the song up online (chord sites, tabs) or
   transcribe a photo of a handwritten chart. Verify progressions against two
   independent human transcriptions; machine-detected chords hallucinate.
   Say plainly what is verified and what is inference.
2. **Write a small YAML file** describing the song: title, artist, key, time
   signature, and the sections with their bars (see `examples/something.yaml`).
3. **Render:**

   ```sh
   python3 -m chartgen render examples/something.yaml -o examples/something.pdf --png
   ```

   Requires Python 3.9+ and `pip install -r requirements.txt`.
4. **Inspect the PNG before delivering.** Check chord symbols, accidentals,
   Hebrew labels, and that nothing collides or overflows. Never deliver a
   chart nobody looked at.

## Backends

chartgen renders through one of two engines (`--backend`):

- **verovio** (default): YAML -> MusicXML 4.0 -> Verovio -> SVG -> PDF.
  Pure-pip (`verovio`, `cairosvg`, `pypdf`, `pillow`, `python-bidi`) - no
  system binaries, so it runs in containers where LilyPond cannot be
  installed. SMuFL engraving: native slash noteheads, clefs, repeat barlines
  and volta brackets. The Roi idiom (boxed Hebrew section marks, boxed
  roadmap lines, title/artist header) is drawn as an SVG overlay, because
  Verovio silently drops Hebrew text encoded in MusicXML; `python-bidi`
  supplies the visual ordering. Pass `--musicxml` to keep the generated
  MusicXML source.
- **lilypond** (legacy): YAML -> .ly -> PDF, the original renderer. Requires
  the [LilyPond](https://lilypond.org) binary on the PATH (or `--lilypond
  PATH`). Kept for reference and comparison; pass `--ly` to keep the `.ly`.

The verovio backend descends from Yanai's earlier amy-charts project
(Python spec -> MusicXML -> Verovio), merged with chartgen's richer YAML
model (sections, repeats, volta endings, roadmap, multi-chord bars) and Roi's
house idiom.

The output matches Roi's charts: A4, bold centered title with a bold artist
on the right, a "Guitar" staff with treble clef and 4/4 on the first system
only, stemless mid-staff slash notation (one slash per beat), chord names
above the staff, boxed Hebrew rehearsal marks at section starts, repeat
barlines with volta 1./2. brackets, centered boxed roadmap lines between
sections, bar numbers at the start of every system, full-width systems, and
a heavy final barline.

## Input format

```yaml
title: Something
artist: The Beatles
key: c major          # "bb minor", "f# major", ...
time: 4/4
instrument: Guitar    # staff label
bars_per_system: 8    # max bars per system; sections and endings never overflow

sections:
  - label: "בית 1"     # boxed rehearsal mark (Hebrew or Latin)
    boxed: true        # set false for a plain bold mark ("CHORUS")
    bars:
      - F              # one chord per bar
      - [C, F]         # two chords in one bar (even split)
      - { chords: G, break: true }        # force a line break after this bar
      - { chords: Am, barline: "|." }     # explicit barline after this bar
```

Each section starts on a fresh system and short sections still stretch to the
full text width. Sections after the first hide the time signature. Bar
numbers print at every system start and are computed from the written bar
counts - add or remove bars and every later number follows automatically.

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
be written in raw LilyPond chordmode with an `ly:` prefix (lilypond backend
only). Bar durations split evenly when possible (2 chords in 4/4 = half
notes); 3 chords in 4/4 default to quarter-quarter-half.

## Layout

```
chartgen/            the generator (python -m chartgen ...)
  model.py           YAML parsing + chord shorthand
  lilypond.py        chart model -> .ly source (legacy backend)
  backends/
    musicxml.py      chart model -> MusicXML 4.0 + overlay spec
    verovio.py       MusicXML -> Verovio -> SVG overlay -> PDF
  style/roi.ily      Roi's house style for the lilypond backend
examples/
  something.yaml     "Something" (The Beatles), matching Roi's chart
  atuf-berachamim.yaml  "עטוף ברחמים" (ריטה), preserving the handwritten chart
```
