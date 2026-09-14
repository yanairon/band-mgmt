"""chartgen CLI: YAML chart description -> PDF (Verovio or LilyPond backend)."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from .model import load_chart
from .lilypond import render_ly
from .backends import verovio as verovio_backend

_STYLE = os.path.join(os.path.dirname(__file__), "style", "roi.ily")


def _find_lilypond(explicit: str | None) -> str:
    for cand in [explicit, os.environ.get("LILYPOND"), "lilypond"]:
        if cand and shutil.which(cand):
            return shutil.which(cand) or cand
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    sys.exit("lilypond not found. Install it (https://lilypond.org) or pass --lilypond PATH.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chartgen",
                                 description="Render a chord-chart YAML to PDF (Roi's house style).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rp = sub.add_parser("render", help="render YAML -> PDF (and .ly)")
    rp.add_argument("input", help="chart YAML file")
    rp.add_argument("-o", "--output", help="output PDF path (default: <input>.pdf)")
    rp.add_argument("--ly", action="store_true", help="write the .ly next to the PDF as well")
    rp.add_argument("--lilypond", help="path to the lilypond binary")
    rp.add_argument("--backend", choices=["verovio", "lilypond"], default="verovio",
                    help="rendering engine (default: verovio; lilypond is the legacy renderer)")
    rp.add_argument("--png", action="store_true",
                    help="also write a PNG preview (verovio backend; inspect before delivering)")
    rp.add_argument("--musicxml", action="store_true",
                    help="write the generated MusicXML next to the PDF (verovio backend)")
    args = ap.parse_args(argv)

    chart = load_chart(args.input)
    out_pdf = args.output or os.path.splitext(args.input)[0] + ".pdf"

    if args.backend == "verovio":
        verovio_backend.render(chart, out_pdf, png=args.png)
        if args.musicxml:
            with open(os.path.splitext(out_pdf)[0] + ".musicxml", "w", encoding="utf-8") as fh:
                fh.write(verovio_backend.render_musicxml(chart))
        print(out_pdf)
        return 0

    ly_source = render_ly(chart)

    lilypond = _find_lilypond(args.lilypond)

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(_STYLE, os.path.join(tmp, "roi.ily"))
        ly_path = os.path.join(tmp, "chart.ly")
        with open(ly_path, "w", encoding="utf-8") as fh:
            fh.write(ly_source)
        proc = subprocess.run(
            [lilypond, "-dno-point-and-click", "-o", os.path.join(tmp, "chart"), ly_path],
            capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(os.path.join(tmp, "chart.pdf")):
            sys.stderr.write(proc.stdout + proc.stderr)
            sys.exit(f"lilypond failed on {args.input} (see above; .ly kept in {tmp}?)")
        shutil.move(os.path.join(tmp, "chart.pdf"), out_pdf)
        if args.ly:
            with open(os.path.splitext(out_pdf)[0] + ".ly", "w", encoding="utf-8") as fh:
                fh.write(ly_source)
    print(out_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
