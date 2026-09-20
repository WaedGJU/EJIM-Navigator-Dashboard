"""
Builds a one-off PDF snapshot of the Project Overview page — KPIs, per-work-
package progress, status distribution, and the delayed/at-risk lists —
stamped with the exact date and time it was generated, so it can be dropped
straight into a report later. Pure Python (reportlab), no chart images
(nothing needs kaleido/orca), no external service calls — same approach as
utils/meeting_pdf.py.
"""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from utils.style import COLORS as C, MASAR_LOGO_PATH

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def build_overview_report_pdf(project_name, generated_at, kpis_dict, wp_rows,
                               status_counts, delayed_df, at_risk_df) -> bytes:
    """
    generated_at: a datetime — stamped on the report as when it was pulled.
    kpis_dict: utils.compute.kpis(df)'s return value.
    wp_rows: [{"wp", "pct", "done", "total", "delayed", "at_risk"}, ...].
    status_counts: DataFrame with "Status" / "Count" columns.
    delayed_df / at_risk_df: the same enriched DataFrames the Overview page
    itself lists in its "Delayed" / "At risk" tabs.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    def fit_text(text, font, size, max_width):
        """Truncates text with an ellipsis so it actually fits max_width at
        this font/size — a character-count guess isn't reliable."""
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
        c.drawString(MARGIN + 24 * mm, y - 7 * mm, "Project Status Report")
        c.setFont("Helvetica", 10.5)
        c.drawString(MARGIN + 24 * mm, y - 13.5 * mm, f"{project_name} · Snapshot of the Project Overview page")

        c.setStrokeColor(colors.HexColor(C["border"]))
        c.setLineWidth(0.8)
        c.line(MARGIN, y - 17 * mm, PAGE_W - MARGIN, y - 17 * mm)

        # "Generated on ..." stamp — its own row, right-aligned, clear of the
        # title above it. (An earlier rotated version overlapped the title
        # for a long project name — a plain bordered box is more robust.)
        stamp_w, stamp_h = 55 * mm, 12 * mm
        stamp_x = PAGE_W - MARGIN - stamp_w
        stamp_y = y - 17 * mm - stamp_h - 3 * mm
        c.setStrokeColor(colors.HexColor(C["orange"]))
        c.setLineWidth(1.1)
        c.roundRect(stamp_x, stamp_y, stamp_w, stamp_h, 2.5 * mm, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.HexColor(C["orange"]))
        c.drawCentredString(stamp_x + stamp_w / 2, stamp_y + stamp_h - 5 * mm, "REPORT GENERATED")
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(colors.HexColor(C["navy"]))
        c.drawCentredString(stamp_x + stamp_w / 2, stamp_y + 2.2 * mm,
                             generated_at.strftime("%d %b %Y, %H:%M"))
        c.setFillColor(colors.black)

        return stamp_y - 6 * mm

    def draw_footer():
        fy = MARGIN
        c.setStrokeColor(colors.HexColor(C["border"]))
        c.setLineWidth(0.6)
        c.line(MARGIN, fy + 8 * mm, PAGE_W - MARGIN, fy + 8 * mm)
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(colors.HexColor(C["ink"]))
        c.drawString(MARGIN, fy + 3.5 * mm, "Prepared by Eng. Waed Alswaeer — Evaluation and Monitoring Officer.")
        c.setFillColor(colors.black)

    def draw_table_header(yy, headers, widths):
        x = MARGIN
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(colors.HexColor(C["navy"]))
        for h, w in zip(headers, widths):
            c.drawString(x + 1 * mm, yy, h)
            x += w
        c.setFillColor(colors.black)
        c.setStrokeColor(colors.HexColor(C["border"]))
        c.line(MARGIN, yy - 1.5 * mm, MARGIN + sum(widths), yy - 1.5 * mm)
        return yy - 6 * mm

    y = draw_header()

    # ---------------- KPI summary ----------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Summary")
    y -= 7 * mm

    kpi_pairs = [
        ("Total activities", kpis_dict.get("total", 0)),
        ("Completed", f"{kpis_dict.get('completed', 0)} ({kpis_dict.get('completed_pct', 0)}%)"),
        ("In progress", kpis_dict.get("in_progress", 0)),
        ("Not started", kpis_dict.get("not_started", 0)),
        ("Needs confirmation", kpis_dict.get("needs_confirmation", 0)),
        ("Delayed", kpis_dict.get("overdue", 0)),
        ("At risk", kpis_dict.get("at_risk", 0)),
        ("No owner", kpis_dict.get("unassigned", 0)),
    ]
    col_w = (PAGE_W - 2 * MARGIN) / 4
    for i, (label, value) in enumerate(kpi_pairs):
        col, row = i % 4, i // 4
        x = MARGIN + col * col_w
        yy = y - row * 11 * mm
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor(C["ink"]))
        c.drawString(x, yy, label)
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(colors.HexColor(C["navy"]))
        c.drawString(x, yy - 5 * mm, str(value))
        c.setFillColor(colors.black)
    rows_used = (len(kpi_pairs) + 3) // 4
    y -= rows_used * 11 * mm + 6 * mm

    # ---------------- Work package progress ----------------
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Work package progress")
    y -= 7 * mm

    wp_headers = ["Work package", "% complete", "Completed", "Delayed", "At risk"]
    wp_widths = [70 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm]

    y = draw_table_header(y, wp_headers, wp_widths)
    c.setFont("Helvetica", 8.5)
    for row in wp_rows:
        if y < MARGIN + 30 * mm:
            draw_footer()
            c.showPage()
            y = draw_header()
            y = draw_table_header(y, wp_headers, wp_widths)
            c.setFont("Helvetica", 8.5)
        x = MARGIN
        values = [
            row["wp"], f"{row['pct']}%", f"{row['done']}/{row['total']}",
            str(row["delayed"]), str(row["at_risk"]),
        ]
        for v, w in zip(values, wp_widths):
            text = fit_text(v, "Helvetica", 8.5, w - 2 * mm)
            c.drawString(x + 1 * mm, y, text)
            x += w
        y -= 5.4 * mm
    y -= 6 * mm

    # ---------------- Status distribution ----------------
    if y < MARGIN + 40 * mm:
        draw_footer()
        c.showPage()
        y = draw_header()
    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, y, "Status distribution")
    y -= 7 * mm
    c.setFont("Helvetica", 9.5)
    for _, srow in status_counts.iterrows():
        c.drawString(MARGIN, y, f"{srow['Status']}: {srow['Count']}")
        y -= 5.4 * mm
    y -= 4 * mm

    # ---------------- Delayed / at-risk lists ----------------
    def draw_activity_list(title, sub_df, extra_label=None, extra_col=None, limit=15):
        nonlocal y
        if y < MARGIN + 30 * mm:
            draw_footer()
            c.showPage()
            y = draw_header()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(MARGIN, y, title)
        y -= 7 * mm
        if sub_df.empty:
            c.setFont("Helvetica-Oblique", 9.5)
            c.drawString(MARGIN, y, "None right now.")
            y -= 7 * mm
            return
        c.setFont("Helvetica", 8.5)
        for _, arow in sub_df.head(limit).iterrows():
            if y < MARGIN + 20 * mm:
                draw_footer()
                c.showPage()
                y = draw_header()
                c.setFont("Helvetica", 8.5)
            line = (f"• {arow.get('Activity', '')} — {arow.get('Original WP', '')} — "
                    f"{arow.get('Responsible (Name)', '—') or '—'}")
            if extra_col and extra_col in sub_df.columns:
                line += f" ({extra_label}: {arow.get(extra_col)})"
            line = fit_text(line, "Helvetica", 8.5, PAGE_W - 2 * MARGIN)
            c.drawString(MARGIN, y, line)
            y -= 5 * mm
        if len(sub_df) > limit:
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(MARGIN, y, f"...and {len(sub_df) - limit} more.")
            y -= 5.5 * mm
        y -= 4 * mm

    draw_activity_list("Delayed activities", delayed_df, extra_label="days overdue", extra_col="days_overdue")
    draw_activity_list("At-risk activities", at_risk_df)

    draw_footer()
    c.showPage()
    c.save()
    return buf.getvalue()
