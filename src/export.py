import pandas as pd
import os
import io
from typing import List, Dict, Optional
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

def export_to_excel(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Vendor Results")
    buffer.seek(0)
    return buffer.read()

def export_to_csv(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")

def export_to_pdf(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    x, y = 40, height - 40
    c.setFont("Helvetica", 9)

    # Header
    for col in df.columns:
        c.drawString(x, y, col)
        x += 120
    y -= 14

    for _, row in df.iterrows():
        x = 40
        for val in row:
            c.drawString(x, y, str(val))
            x += 120
        y -= 14
        if y < 40:
            c.showPage()
            y = height - 40

    c.save()
    buffer.seek(0)
    return buffer.read()

