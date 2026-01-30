import io
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.local_storage import load_decrypted

def get_fraud_breakdown(key:str):
    csv_bytes = load_decrypted(key)
    df = pd.read_csv(io.BytesIO(csv_bytes))  
    fraud_counts = df["is_fraud"].value_counts()
    data_for_js = [
    {"label": "Not Fraud", "value": int(fraud_counts.get(0, 0))},
    {"label": "Fraud", "value": int(fraud_counts.get(1, 0))}
    ]
    return data_for_js

def convert_csv_to_pdf(csv_bytes: bytes) -> bytes:
    csv_text = csv_bytes.decode("utf-8")
    reader = csv.reader(csv_text.splitlines())
    rows = list(reader)

    styles = getSampleStyleSheet()

    reasoning_style = ParagraphStyle(
        "ReasoningStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,        # line spacing
        wordWrap="CJK",    # forces wrapping even for long strings
    )

    if not rows:
        raise ValueError("CSV is empty")

    header = rows[0]

    # Find column indexes safely
    try:
        fraud_idx = header.index("is_fraud")
        reasoning_idx = header.index("reasoning")
    except ValueError as e:
        raise ValueError("Required columns missing from CSV") from e

    # Build filtered table data
    table_data = [["is_fraud", "reasoning"]]

    for row in rows[1:]:
        reasoning_value = row[reasoning_idx].strip() if len(row) > reasoning_idx else ""

        if reasoning_value:  # non-null / non-empty
            table_data.append([
                row[fraud_idx],
                Paragraph(reasoning_value, reasoning_style),
            ])

    # Handle case: nothing to show
    if len(table_data) == 1:
        table_data.append(["—", "No flagged results found"])

    # PDF generation
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    elements = []

    # Optional title
    elements.append(Paragraph("<b>Fraud Analysis Summary</b>", styles["Title"]))

    table = Table(
        table_data,
        colWidths=[80, 420],  # narrow fraud flag, wide reasoning
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)
    return buffer.read()

