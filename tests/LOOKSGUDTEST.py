from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    PageBreak,
    Spacer,
)
from reportlab.lib.enums import TA_LEFT

from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
import random

OUTPUT_FILE = "report_layout_clean_with_headers.pdf"


# --------------------------------------------------------------------
# Pseudo data generation
# --------------------------------------------------------------------
def generate_pseudodata():
    categories = {}
    issuers = ["Supercell Ltd.", "Blizzard Entertainment", "Valve Corp.", "EA Games"]
    descriptions = ["500 gems", "Battle Pass", "In-game currency", "Premium Skin"]

    for cat in range(1, 6):
        rows = []
        for i in range(random.randint(10, 45)):
            transaction_id = f"{100 + i}"
            date = f"2025-9-{random.randint(1,30)}"
            issuer = random.choice(issuers)
            desc = random.choice(descriptions)
            amount = round(random.uniform(-100, -10), 2)
            rows.append((transaction_id, date, issuer, desc, amount, "EUR"))
        categories[cat] = rows
    return categories


# --------------------------------------------------------------------
# Pie chart
# --------------------------------------------------------------------
def make_pie_chart(category_sums):
    drawing = Drawing(200, 200)
    pie = Pie()
    pie.width = 200
    pie.height = 200
    pie.data = list(category_sums.values())
    pie.labels = [f"Category {c}" for c in category_sums.keys()]
    pie.slices.strokeWidth = 0.25
    drawing.add(pie)
    return drawing


# --------------------------------------------------------------------
# Table builder with alternating rows and sum
# --------------------------------------------------------------------
def make_category_tables(category, rows, styles):
    """Split category data into multiple tables (if needed)."""
    max_rows_per_page = 19
    tables = []

    for start in range(0, len(rows), max_rows_per_page):
        chunk = rows[start : start + max_rows_per_page]
        data = []
        row_colors = []

        # Transaction rows
        for idx, (transaction_id, transaction_date, issuer, description, amount, currency) in enumerate(chunk):
            desc_text = f"Transaction #{transaction_id}, {transaction_date} - {issuer}<br/>&#10148; {description}"
            amount_text = f"{amount:.2f}{currency}"
            data.append([Paragraph(desc_text, styles["Normal"]), amount_text])
            bg_color = colors.whitesmoke if idx % 2 else colors.white
            row_colors.append(bg_color)

        # Sum row on last chunk only
        if start + max_rows_per_page >= len(rows):
            total = sum(r[4] for r in rows)

            right_style = ParagraphStyle(
                "RightSum",
                parent=styles["Normal"],
                alignment=2  # 2 = TA_RIGHT
            )

            data.append([
                Paragraph("<b>Sum:</b>", styles["Normal"]),
                Paragraph(f"<b><font size=10>{total:.2f} EUR</font></b>", right_style),
            ])
            row_colors.append(colors.white)

        # Build table
        table = Table(data, colWidths=[13*cm, 3*cm])
        style_cmds = [
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]

        # Alternating background colors
        for i, bg in enumerate(row_colors):
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

        # Add space above sum row and right-align the sum cell
        if start + max_rows_per_page >= len(rows):
            style_cmds.append(("TOPPADDING", (0, -1), (-1, -1), 10))


        # No borders between cells
        style_cmds.append(("LINEBELOW", (0, 0), (-1, -1), 0, colors.white))

        table.setStyle(TableStyle(style_cmds))
        tables.append(table)

    return tables


# --------------------------------------------------------------------
# PDF generator
# --------------------------------------------------------------------
def generate_pdf():
    doc = SimpleDocTemplate(OUTPUT_FILE, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # === Generate fake data ===
    categories = generate_pseudodata()
    print(categories)
    category_sums = {cat: sum(r[4] for r in items) for cat, items in categories.items()}

    # === Page 1: Overview with Pie Chart ===
    elements.append(make_pie_chart(category_sums))
    elements.append(PageBreak())
    
    # === Category Pages ===
    for cat, items in categories.items():
        tables = make_category_tables(cat, items, styles)

        for idx, table in enumerate(tables):
            # Category header at top of every page
            elements.append(Paragraph(f"<b>Category {cat}</b>", styles["Heading2"]))
            elements.append(Spacer(1, 6))
            elements.append(table)
            if idx < len(tables) - 1:
                elements.append(PageBreak())

        # Page break between categories
        elements.append(PageBreak())

    doc.build(elements)
    print(f"✅ Clean layout PDF with headers created: {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_pdf()
