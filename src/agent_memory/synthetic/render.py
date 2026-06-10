"""Render demo dossier artifacts to bytes — handwritten / printed / scanned (ADR-0015).

Pillow only. Used by ``scripts/render_fixtures.py`` to produce the committed demo
fixtures under ``data/synthetic/fixtures/``. NOT imported by the app or the ingest
runtime — keep this module free of any Databricks / agent dependency.

Each renderer takes ground-truth text and returns the encoded bytes for one artifact:
- ``render_handwritten`` → PNG, a cursive/handwriting font on off-white paper.
- ``render_pdf``         → single-page raster PDF, a clean printed page.
- ``render_scan``        → JPEG, a printed page degraded to look photographed/scanned
                           (grayscale, slight rotation, light noise + blur).

Fonts resolve from a candidate list per style with a graceful fallback to Pillow's
default bitmap font, so the script still runs (less pretty) on a machine without the
preferred fonts installed.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont, ImageOps

# truetype() returns FreeTypeFont; the load_default() fallback may return either —
# accept both so the fallback path type-checks.
_Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

# Candidate font files per style. macOS Supplemental fonts first (what we render with);
# common Linux fallbacks next; Pillow's default bitmap font as the last resort.
_HANDWRITING_FONTS = (
    "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "Caveat-Regular.ttf",
    "Comic Sans MS.ttf",
)
_PRINT_FONTS = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
)


def _load_font(candidates: tuple[str, ...], size: int) -> _Font:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: _Font, max_width: int) -> list[str]:
    """Greedy word-wrap a single paragraph to fit ``max_width`` pixels."""
    if not text:
        return [""]
    lines: list[str] = []
    words = text.split()
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _render_page(
    text: str,
    *,
    font: _Font,
    size: int,
    width: int,
    ink: str,
    bg: str,
    line_spacing: float,
    margin: int,
) -> Image.Image:
    """Render multi-line text onto a single page image, height sized to the content."""
    # Probe with a scratch image to measure wrapped lines before sizing the real one.
    scratch = ImageDraw.Draw(Image.new("RGB", (width, 10), bg))
    line_h = int(size * line_spacing)
    visual_lines: list[str] = []
    for para in text.split("\n"):
        visual_lines.extend(_wrap(scratch, para, font, width - 2 * margin))

    height = 2 * margin + max(1, len(visual_lines)) * line_h
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    y = margin
    for line in visual_lines:
        draw.text((margin, y), line, fill=ink, font=font)
        y += line_h
    return img


def render_handwritten(text: str, *, ink: str = "#1a2b4a", bg: str = "#fffef8") -> bytes:
    """Handwritten meeting note → PNG bytes (cursive font on off-white paper)."""
    size = 34
    font = _load_font(_HANDWRITING_FONTS, size)
    img = _render_page(
        text, font=font, size=size, width=980, ink=ink, bg=bg,
        line_spacing=1.6, margin=44,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_pdf(text: str) -> bytes:
    """Printed document (e.g. brokerage statement) → single-page raster PDF bytes."""
    size = 30
    font = _load_font(_PRINT_FONTS, size)
    img = _render_page(
        text, font=font, size=size, width=1000, ink="#15212b", bg="#ffffff",
        line_spacing=1.45, margin=56,
    )
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=150.0)
    return buf.getvalue()


def render_scan(text: str) -> bytes:
    """Printed document degraded to look photographed/scanned → JPEG bytes.

    Grayscale + a slight rotation + light noise so it reads as a scan, but kept mild
    enough that ai_parse_document still extracts it cleanly.
    """
    size = 30
    font = _load_font(_PRINT_FONTS, size)
    page = _render_page(
        text, font=font, size=size, width=1000, ink="#1b1b1b", bg="#fbfbf7",
        line_spacing=1.45, margin=56,
    )
    gray = ImageOps.grayscale(page)
    # Light noise blended over the page, then a small CCW rotation with white fill.
    noise = Image.effect_noise(gray.size, 18).convert("L")
    blended = Image.blend(gray, noise, 0.08)
    scanned = blended.rotate(-1.5, expand=True, fillcolor=245, resample=Image.Resampling.BICUBIC)
    buf = io.BytesIO()
    scanned.convert("RGB").save(buf, format="JPEG", quality=85)
    return buf.getvalue()
