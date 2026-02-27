import pandas as pd
import io
from datetime import datetime

# ---------------------------
# CSV EXPORT
# ---------------------------

def export_to_csv(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8-sig")  # UTF-8 with BOM for Excel compatibility


# ---------------------------
# EXCEL EXPORT (Formatted)
# ---------------------------

def export_to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Vendor Results")

        workbook = writer.book
        worksheet = writer.sheets["Vendor Results"]

        # Formats
        header_format = workbook.add_format({
            "bold": True,
            "text_wrap": True,
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        cell_format = workbook.add_format({
            "text_wrap": True,
            "border": 1,
            "valign": "top"
        })

        # Apply header format
        for col_num, column in enumerate(df.columns):
            worksheet.write(0, col_num, column, header_format)

        # Auto column width
        for i, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(col)
            ) + 2
            worksheet.set_column(i, i, min(max_length, 40), cell_format)

        # Freeze header
        worksheet.freeze_panes(1, 0)

    buffer.seek(0)
    return buffer.read()


# ---------------------------
# PDF EXPORT (Professional Table)
# ---------------------------

try:
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import inch

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def export_to_pdf(df: pd.DataFrame) -> bytes:

    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer
    )
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import inch

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(
        Paragraph(
            f"<b>Vendor Search Results</b><br/>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles["Heading2"]
        )
    )
    elements.append(Spacer(1, 0.3 * inch))

    # Prepare wrapped data
    wrapped_data = []

    # Wrap header
    header = [
        Paragraph(f"<b>{col}</b>", styles["Normal"])
        for col in df.columns
    ]
    wrapped_data.append(header)

    # Wrap rows
    for _, row in df.iterrows():
        wrapped_row = [
            Paragraph(str(val), styles["Normal"])
            for val in row
        ]
        wrapped_data.append(wrapped_row)

    # Safe width calculation
    total_width = 10.5 * inch
    col_ratios = []

    for col in df.columns:
        values = df[col].fillna("").astype(str)
        avg_len = values.map(len).mean()

        # fallback if column empty
        if avg_len is None or avg_len == 0 or pd.isna(avg_len):
            avg_len = 5

        col_ratios.append(avg_len)

    total_ratio = sum(col_ratios)

    # fallback if somehow all columns empty
    if total_ratio == 0:
        total_ratio = len(df.columns)

    col_widths = [
        max((r / total_ratio) * total_width, 0.8 * inch)
        for r in col_ratios
    ]

    table = Table(
        wrapped_data,
        colWidths=col_widths,
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return buffer.read()