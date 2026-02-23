from datetime import datetime
import io
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Image, SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.local_storage import load_decrypted

formattedDate = datetime.now().strftime("%B %d, %Y")

def get_fraud_table_breakdown(key:str):
    csv_bytes = load_decrypted(key)
    df = pd.read_csv(io.BytesIO(csv_bytes))  
    fraud_rows = df[df["xgb_flag"] == 1]
    data_for_js = [
        {"id": _, "timestamp": row["timestamp"], "merchant": row["merchant"], "amount": row["amount"], "mcc": row["mcc"], "city": row["city"], "country": row["country"], "channel": row["channel"], "reasoning": row["reasoning"]}
        for _, row in fraud_rows.iterrows()
    ]
    return data_for_js

def get_fraud_status_breakdown(key:str):
    csv_bytes = load_decrypted(key)
    df = pd.read_csv(io.BytesIO(csv_bytes))  
    fraud_counts = df["xgb_flag"].value_counts()
    positive_fraud_counts = int(fraud_counts.get(1, 0))
    negative_fraud_counts = int(fraud_counts.get(0, 0))
    total_fraud_counts = positive_fraud_counts + negative_fraud_counts   
    if total_fraud_counts > 0:
        positive_fraud_percentage = positive_fraud_counts / total_fraud_counts
        negative_fraud_percentage = negative_fraud_counts / total_fraud_counts
    else:
        positive_fraud_percentage = 0
        negative_fraud_percentage = 0
    
    data_for_js = [
    {"label": "Not Fraud", "value": negative_fraud_counts, "percentage": round(negative_fraud_percentage * 100, 2), "total": total_fraud_counts},
    {"label": "Fraud", "value": positive_fraud_counts, "percentage": round(positive_fraud_percentage * 100, 2), "total": total_fraud_counts}
    ]
    return data_for_js

def get_fraud_type_breakdown(key:str):
    csv_bytes = load_decrypted(key)
    df = pd.read_csv(io.BytesIO(csv_bytes))  
    fraud_counts = df["xgb_flag"].value_counts()
    positive_fraud_counts = int(fraud_counts.get(1, 0))
    total_fraud_counts = positive_fraud_counts
    fraud_rows = df[df["xgb_flag"] == 1]
    reasoning_series = fraud_rows["reasoning"].dropna().str.split(";")
    all_reasonings = [reason.strip() for sublist in reasoning_series for reason in sublist]
    reasoning_counts = pd.Series(all_reasonings).value_counts()
    reasoning_data_for_js = [
        {"label": label, "value": int(count), "percentage": round(count / positive_fraud_counts * 100, 2), "total": total_fraud_counts}
        for label, count in reasoning_counts.items()
    ]
    return reasoning_data_for_js

def get_csv_data_for_key(key: str) -> bytes:
    print("🔍 Downloading key:", key)
    data = load_decrypted(key)
    return data

def convert_csv_to_pdf(csv_bytes: bytes) -> bytes:
    
    csv_text = csv_bytes.decode("utf-8")
    reader = csv.reader(csv_text.splitlines())
    rows = list(reader)

    styles = getSampleStyleSheet()

    report_header_style = ParagraphStyle(
        "ReportHeaderStyle",
        parent=styles["Title"],
        alignment=0,
        fontName="Times-Roman"
    )
    
    report_paragraph_style = ParagraphStyle(
        "ReportParagraphStyle",
        parent=styles["Normal"],
        alignment=0,
        fontName="Times-Roman"
    )

    table_header_style = ParagraphStyle(
        "TableHeaderStyle",
        parent=styles["Normal"],
        fontName="Times-Roman"
    )

    amount_table_header_style = ParagraphStyle(
        "AmountHeaderStyle",
        parent=styles["Normal"],
        alignment=2,
        fontName="Times-Roman"
    )

    table_row_style = ParagraphStyle(
        "TableRowStyle",
        parent=styles["Normal"],      
        wordWrap="CJK",
        fontName="Times-Roman"
    )

    amount_table_row_style = ParagraphStyle(
        "AmountRowStyle",
        parent=styles["Normal"],
        alignment=2,
        fontName="Times-Roman"
    )

    if not rows:
        raise ValueError("CSV is empty")

    header = rows[0]

    try:
        timeDate_idx = header.index("timestamp")
        merchant_idx = header.index("merchant")
        mcc_idx = header.index("mcc")
        reasoning_idx = header.index("reasoning")
        amount_idx = header.index("amount")
    except ValueError as e:
        raise ValueError("Required columns missing from CSV") from e

    table_data = [[Paragraph("<b>Timestamp</b>",table_header_style),Paragraph("<b>Merchant</b>",table_header_style),Paragraph("<b>Fraud Reasoning</b>",table_header_style),Paragraph("<b>Amount</b>",amount_table_header_style)]]

    for row in rows[1:]:
        reasoning_value = row[reasoning_idx].strip() if len(row) > reasoning_idx else ""

        if reasoning_value:  
            table_data.append([
                Paragraph(str(row[timeDate_idx]), table_row_style),
                Paragraph(row[merchant_idx] + " #" + str(int(float(row[mcc_idx]))), table_row_style),
                Paragraph(reasoning_value, table_row_style),
                Paragraph(row[amount_idx], amount_table_row_style)
            ])

    if len(table_data) == 1:
        table_data.append(["—", "No flagged results found"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=25, leftMargin=25, rightMargin=25)
    styles = getSampleStyleSheet()

    elements = []

    img = Image("fraud_logo_64.png")
    img.hAlign = "LEFT"
    elements.append(img)

    elements.append(Spacer(1, 25))

    elements.append(Paragraph("<b>Fraud Analysis Summary</b>",report_header_style))

    formattedDate = datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph("Report Date: " + formattedDate, report_paragraph_style))

    elements.append(Paragraph("Fraudulent transactions are organized by review priority.", report_paragraph_style))

    elements.append(Spacer(1, 10))

    table = Table(
        table_data,
        colWidths=[90, 100, 300, 60],  
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#b89fe3"),
        ("LINEBELOW", (0,1), (-1,-1), 0.5, colors.grey, None, [2, 2]),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)
    return buffer.read()
    
