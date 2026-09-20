"""
Builds the weekly meeting-minutes PDF for the Meeting Prep page: a header
with the project logo/name and date, an attendance checklist, a table of
what was changed during the meeting (before -> after), and a signed-off
footer. Everything in English.

Pure Python (reportlab) — renders the same on Streamlit Community Cloud or a
local machine, no external service calls.
"""

import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from utils.style import COLORS, MASAR_LOGO_PATH
from utils.constants import now_jordan

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def build_meeting_minutes_pdf(
    project_name: str,
    meeting_date: datetime.date,
    attendance: list,
    changes: list,
    general_notes: str = "",
    generated_at: datetime.datetime = None,
) -> bytes:
    """
    attendance: [(name, present_bool), ...] — internal team only.
    changes: [{"activity", "wp", "field", "old", "new"}, ...] — edits saved
             on the Meeting Prep page during this session.
    general_notes: free text for anything discussed that isn't tied to a
             specific activity — printed as its own section, right after
             the changes table.
    generated_at: a datetime — stamped on the minutes as when the PDF was
             produced. Always shown in Jordan time (Asia/Amman) regardless
             of what timezone the app happens to be hosted in — defaults to
             now_jordan() if not passed in explicitly.
    Returns the finished PDF as bytes, ready for st.download_button.
    """
    if generated_at is None:
        generated_at = now_jordan()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    def fit_text(text, font, size, max_width):
        """Truncates text with an ellipsis so it actually fits max_width at
        this font/size — a character-count guess isn't reliable because
        letters vary in width, and it was overlapping table columns."""
        text = str(text)
        if c.stringWidth(text, font, size) <= max_width:
            return text
        while text and c.stringWidth(text + "…", font, size) > max_width:
            text = text[:-1]
        return (text + "…") if text else "…"

    def draw_header():
        y = PAGE_H - MARGIN
        try:
            c.drawImage(str(MASAR_LOGO_PATH), MARGIN, y - 20 * mm, width=20 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

        c.setFont("Helvetica-Bold", 15)
        c.drawString(MARGIN + 24 * mm, y - 7 * mm, f"Minutes of Meeting — {project_name}")
        c.setFont("Helvetica", 10.5)
        weekday = meeting_date.strftime("%A")
        c.drawString(MARGIN + 24 * mm, y - 13.5 * mm, f"Weekly team meeting · {weekday}, {meeting_date.strftime('%d %B %Y')}")

        # "Generated ..." stamp, always in Jordan time regardless of where the
        # app is hosted (Streamlit Community Cloud's servers run on UTC).
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(colors.HexColor(COLORS["ink"]))
        c.drawString(MARGIN + 24 * mm, y - 18.5 * mm,
                     f"Generated {generated_at.strftime('%d %b %Y, %H:%M')} (Jordan time)")
        c.setFillColor(colors.black)

        c.setStrokeColor(colors.HexColor(COLORS["border"]))
        c.setLineWidth(0.8)
        c.line(MARGIN, y - 22 * mm, PAGE_W - MARGIN, y - 22 * mm)
        return y - 28 * mm

    def draw_footer():
        fy = MARGIN
        c.setStrokeColor(colors.HexColor(COLORS["border"]))
        c.setLineWidth(0.6)
        c.line(MARGIN, fy + 8 * mm, PAGE_W - MARGIN, fy + 8 * mm)
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(colors.HexColor(COLORS["ink"]))
        c.drawString(MARGIN, fy + 3.5 * mm, "Prepared by Eng. Waed Alswaeer — Evaluation and Monitoring Officer.")
        c.setFillColor(colors.black)

    y = draw_header()

    # ---------------- Attendance ----------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Attendance")
    y -= 7 * mm

    c.setFont("Helvetica", 10)
    col_w = (PAGE_W - 2 * MARGIN) / 2
    for i, (name, present) in enumerate(attendance):
        col = i % 2
        row = i // 2
        x = MARGIN + col * col_w
        yy = y - row * 6 * mm
        box = "[x]" if present else "[ ]"
        c.drawString(x, yy, f"{box}  {name}")
    rows_used = (len(attendance) + 1) // 2 if attendance else 0
    y -= rows_used * 6 * mm + 10 * mm

    # ---------------- Changes made during the meeting ----------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Changes made during this meeting")
    y -= 8 * mm

    if not changes:
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(MARGIN, y, "No changes were saved during this session.")
        y -= 8 * mm
    else:
        headers = ["Activity", "WP", "Field", "Before", "After"]
        widths = [48 * mm, 34 * mm, 20 * mm, 30 * mm, 30 * mm]
        pad = 2 * mm

        def draw_table_header(yy):
            x = MARGIN
            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(colors.HexColor(COLORS["navy"]))
            for h, w in zip(headers, widths):
                c.drawString(x + 1 * mm, yy, h)
                x += w
            c.setFillColor(colors.black)
            c.setStrokeColor(colors.HexColor(COLORS["border"]))
            c.line(MARGIN, yy - 1.5 * mm, MARGIN + sum(widths), yy - 1.5 * mm)
            return yy - 6 * mm

        y = draw_table_header(y)
        c.setFont("Helvetica", 8)
        for ch in changes:
            if y < MARGIN + 20 * mm:
                draw_footer()
                c.showPage()
                y = draw_header()
                y = draw_table_header(y)
                c.setFont("Helvetica", 8)

            x = MARGIN
            values = [
                ch.get("activity", ""), ch.get("wp", ""), ch.get("field", ""),
                ch.get("old") or "—", ch.get("new") or "—",
            ]
            for v, w in zip(values, widths):
                text = fit_text(v, "Helvetica", 8, w - pad)
                c.drawString(x + 1 * mm, y, text)
                x += w
            y -= 5.4 * mm

    # ---------------- General notes (not tied to any activity) ----------------
    notes_text = (general_notes or "").strip()
    if notes_text:
        y -= 6 * mm
        if y < MARGIN + 30 * mm:
            draw_footer()
            c.showPage()
            y = draw_header()

        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN, y, "General notes")
        y -= 7 * mm

        c.setFont("Helvetica", 9.5)
        max_width = PAGE_W - 2 * MARGIN
        for paragraph in notes_text.splitlines() or [""]:
            words = paragraph.split()
            line = ""
            wrapped = []
            for word in words:
                candidate = f"{line} {word}".strip()
                if c.stringWidth(candidate, "Helvetica", 9.5) <= max_width:
                    line = candidate
                else:
                    if line:
                        wrapped.append(line)
                    line = word
            wrapped.append(line)
            for wrapped_line in wrapped:
                if y < MARGIN + 20 * mm:
                    draw_footer()
                    c.showPage()
                    y = draw_header()
                    c.setFont("Helvetica", 9.5)
                c.drawString(MARGIN, y, wrapped_line)
                y -= 5 * mm

    draw_footer()
    c.showPage()
    c.save()
    return buf.getvalue()
