"""Rendering backends for chartgen.

- lilypond: the original backend (YAML -> LilyPond .ly -> PDF), kept for reference.
- verovio: YAML -> MusicXML 4.0 -> Verovio -> SVG (overlay) -> PDF. Pure-pip,
  no system binaries, and native SMuFL engraving. Default backend.
"""
