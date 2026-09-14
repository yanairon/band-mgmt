"""Verovio backend: Chart -> MusicXML -> Verovio -> SVG (overlay) -> PDF.

Port of the amy-charts pipeline (MusicXML 4.0 -> Verovio -> cairosvg) extended
with Roi's idiom via an SVG overlay: boxed section labels with the start bar
folded in, boxed roadmap lines between sections, and the composer credit.
Hebrew cannot go through MusicXML <words> (Verovio silently drops the glyphs),
so all labels/roadmaps are drawn here - DejaVu has full Hebrew coverage, and
python-bidi supplies the visual-order reordering that cairo's toy text API
lacks.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ..model import Chart
from .musicxml import Overlay, to_musicxml

# Verovio page units are 1/10 mm; internal SVG units are 1/100 mm (x10).
PAGE_W, PAGE_H = 2100, 2970
MARGIN_L, MARGIN_T = 110, 230
U = 10

SERIF_FONT = "DejaVu Serif, Times, serif"
SANS_FONT = "DejaVu Sans, Arial, sans-serif"

_SMUFL_TEXT_ACCID = {"": "♭", "": "♯", "": "♮"}

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_LABEL_SIZE = 340        # internal units (~12pt at scale 40)
_ROADMAP_SIZE = 360
_COMPOSER_SIZE = 300
_BARNUM_SIZE = 220
_BOX_PAD_X, _BOX_PAD_Y = 130, 90


def _display(text: str) -> str:
    """Visual-order the text for renderers without bidi (Hebrew labels)."""
    if re.search(r"[֐-׿]", text):
        from bidi.algorithm import get_display
        return get_display(text)
    return text


def _text_width(text: str, size: int, bold: bool = True) -> float:
    from PIL import ImageFont
    font = ImageFont.truetype(_FONT_PATH, size)
    bbox = font.getbbox(_display(text))
    return bbox[2] - bbox[0]


def _fix_accidentals(svg: str) -> str:
    """Replace Leipzig private-use accidental codepoints with real glyphs."""
    def repl(m: "re.Match[str]") -> str:
        attrs, body = m.group(1), m.group(2)
        if body not in _SMUFL_TEXT_ACCID:
            return m.group(0)
        size = re.search(r'font-size="(\d+(?:\.\d+)?)px"', attrs)
        new_attrs = attrs
        if size:
            new_attrs = attrs.replace(size.group(0),
                                      f'font-size="{float(size.group(1)) * 0.62:.0f}px"')
        new_attrs = new_attrs.replace('font-family="Leipzig"', f'font-family="{SERIF_FONT}"')
        return f"<tspan{new_attrs}>{_SMUFL_TEXT_ACCID[body]}</tspan>"

    return re.sub(r'<tspan([^>]*font-family="Leipzig"[^>]*)>([^<]*)</tspan>', repl, svg)


@dataclass
class _SystemGeom:
    top: float
    bottom: float
    left: float
    right: float


def _systems(svg: str) -> list[_SystemGeom]:
    """Geometry of each engraved system, top to bottom."""
    out = []
    marks = list(re.finditer(r'class="system"', svg))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(svg)
        chunk = svg[m.start():end]
        pts = re.findall(r'<path d="M(\d+(?:\.\d+)?) (\d+(?:\.\d+)?)', chunk)
        if not pts:
            continue
        xs = [float(x) for x, _ in pts]
        ys = [float(y) for _, y in pts]
        out.append(_SystemGeom(top=min(ys), bottom=max(ys), left=min(xs), right=max(xs)))
    return out


def _font_for(text: str, preferred: str) -> str:
    """Hebrew renders reliably only in DejaVu Sans under cairo's toy text API."""
    if re.search(r"[֐-׿]", text):
        return SANS_FONT
    return preferred


def _text_el(x: float, y: float, text: str, size: int, *, anchor: str = "start",
             font: str = SANS_FONT) -> str:
    font = _font_for(text, font)
    return (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-size="0px">'
            f'<tspan font-size="{size}px" font-weight="bold" font-family="{font}">'
            f'{_display(text)}</tspan></text>')


def _boxed(x: float, baseline: float, text: str, size: int, *, anchor: str = "start") -> str:
    """Boxed bold label. (x, baseline) is the text start per the anchor."""
    w = _text_width(text, size)
    tx = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
    rx, ry = tx - _BOX_PAD_X, baseline - size - _BOX_PAD_Y
    rw, rh = w + 2 * _BOX_PAD_X, size + 2 * _BOX_PAD_Y
    return (f'<rect x="{rx:.0f}" y="{ry:.0f}" width="{rw:.0f}" height="{rh:.0f}" '
            f'fill="none" stroke="black" stroke-width="26"/>'
            + _text_el(x, baseline, text, size, anchor=anchor))


def _overlay_page(svg: str, overlay: Overlay, *, page_index: int,
                  page_system_counts: list[int], page_width_units: int) -> str:
    """Draw composer, section labels and roadmap boxes onto one SVG page."""
    geoms = _systems(svg)
    if not geoms:
        return svg
    systems_before = sum(page_system_counts[:page_index])
    extra: list[str] = []
    inner_w = page_width_units * U - 2 * MARGIN_L * U

    if page_index == 0:
        # Verovio's own header is off (it drops Hebrew), so title + composer
        # are drawn here, placed relative to the first system's top.
        # coordinates inside page-margin are relative; place against the
        # measured first-system top so the header can't land on the staff
        first_top = geoms[0].top
        if overlay.title:
            extra.append(_text_el(inner_w / 2, first_top - 1500, overlay.title, 480,
                                  anchor="middle", font=SERIF_FONT))
        if overlay.composer:
            extra.append(_text_el(inner_w, first_top - 950, overlay.composer,
                                  _COMPOSER_SIZE, anchor="end", font=SERIF_FONT))

    for lab in overlay.labels:
        local = lab.system_index - systems_before
        if not 0 <= local < len(geoms):
            continue
        g = geoms[local]
        x, base = g.left - 40, g.top - 620
        # Bar numbers are NOT folded in: Verovio already prints measure
        # numbers at every system start, and a second number collides with it.
        if lab.boxed:
            extra.append(_boxed(x, base, lab.text, _LABEL_SIZE))
        else:
            extra.append(_text_el(x, base, lab.text, _LABEL_SIZE))

    roadmap_stack: dict[int, int] = {}
    for rm in overlay.roadmaps:
        local = rm.system_index - systems_before
        if not 0 <= local < len(geoms):
            continue
        g = geoms[local]
        cx = (g.left + g.right) / 2
        stack = roadmap_stack.get(rm.system_index, 0)
        roadmap_stack[rm.system_index] = stack + 1
        extra.append(_boxed(cx, g.bottom + 900 + stack * 780, rm.text, _ROADMAP_SIZE,
                            anchor="middle"))

    if not extra:
        return svg
    insert_at = svg.rfind("</g>", 0, svg.rfind("</svg>"))
    return svg[:insert_at] + "".join(extra) + svg[insert_at:]


def render(chart: Chart, out_pdf: str, *, png: bool = False, scale: int = 40) -> str:
    """Render the chart to PDF via MusicXML + Verovio. Returns out_pdf."""
    musicxml, overlay = to_musicxml(chart)

    import verovio
    tk = verovio.toolkit()
    tk.setResourcePath(os.path.join(os.path.dirname(verovio.__file__), "data"))
    tk.setOptions({
        "pageWidth": PAGE_W, "pageHeight": PAGE_H,
        "pageMarginLeft": MARGIN_L, "pageMarginRight": MARGIN_L,
        "pageMarginTop": MARGIN_T, "pageMarginBottom": 90,
        "scale": scale, "adjustPageHeight": False,
        "header": "none", "footer": "none",
        "svgViewBox": True, "breaks": "encoded",
        "spacingStaff": 14, "spacingSystem": 24,
        "svgRemoveXlink": True,
    })
    if not tk.loadData(musicxml):
        raise RuntimeError("Verovio failed to parse the generated MusicXML")

    raw_pages = [_fix_accidentals(tk.renderToSVG(p)) for p in range(1, tk.getPageCount() + 1)]
    counts = [len(_systems(s)) for s in raw_pages]
    pages = [_overlay_page(s, overlay, page_index=i, page_system_counts=counts,
                           page_width_units=PAGE_W) for i, s in enumerate(raw_pages)]

    import cairosvg
    if len(pages) == 1:
        cairosvg.svg2pdf(bytestring=pages[0].encode(), write_to=out_pdf)
    else:
        from pypdf import PdfWriter
        writer = PdfWriter()
        for i, svg in enumerate(pages):
            tmp = f"{out_pdf}.p{i}.pdf"
            cairosvg.svg2pdf(bytestring=svg.encode(), write_to=tmp)
            writer.append(tmp)
        writer.write(out_pdf)
        writer.close()
        for i in range(len(pages)):
            os.remove(f"{out_pdf}.p{i}.pdf")

    if png:
        cairosvg.svg2png(bytestring=pages[0].encode(),
                         write_to=os.path.splitext(out_pdf)[0] + ".png",
                         scale=2, background_color="white")
    return out_pdf


def render_musicxml(chart: Chart) -> str:
    """The generated MusicXML (kept for debugging / --musicxml flag)."""
    return to_musicxml(chart)[0]
