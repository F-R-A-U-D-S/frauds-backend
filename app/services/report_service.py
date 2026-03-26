from datetime import datetime
import io
import csv
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.platypus import Image, SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from app.core.local_storage import load_decrypted

formattedDate = datetime.now().strftime("%B %d, %Y")
GRAPH_COLOR = "#8e44ad"

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
    reasoning_series = fraud_rows["reasoning"].dropna().astype(str).str.split(";")
    all_reasonings = [reason.strip() for sublist in reasoning_series for reason in sublist if str(reason).strip()]
    reasoning_counts = pd.Series(all_reasonings).value_counts()
    denom = positive_fraud_counts if positive_fraud_counts > 0 else 1
    reasoning_data_for_js = [
        {"label": label, "value": int(count), "percentage": round(count / denom * 100, 2), "total": total_fraud_counts}
        for label, count in reasoning_counts.items()
    ]
    return reasoning_data_for_js

def get_csv_data_for_key(key: str) -> bytes:
    print("🔍 Downloading key:", key)
    data = load_decrypted(key)
    return data

def _plot_to_rl_image(fig, max_width=520, max_height=260):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    img = Image(buf)
    img.hAlign = "LEFT"

    original_width = img.imageWidth
    original_height = img.imageHeight
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    scale = min(width_ratio, height_ratio)

    img.drawWidth = original_width * scale
    img.drawHeight = original_height * scale
    return img

def _make_flag_bar(df: pd.DataFrame):
    if "xgb_flag" not in df.columns:
        return None
    s = pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int)
    counts = s.value_counts().reindex([0, 1], fill_value=0)
    fig = plt.figure(figsize=(8, 3.5))
    ax = fig.add_subplot(111)
    ax.bar(["Not Flagged", "Flagged"], [int(counts.loc[0]), int(counts.loc[1])], color=GRAPH_COLOR)
    ax.set_title("XGBoost Fraud Flag Breakdown")
    ax.set_ylabel("Transactions")
    return _plot_to_rl_image(fig)

def _make_reason_bar(df: pd.DataFrame):
    if "xgb_flag" not in df.columns or "reasoning" not in df.columns:
        return None
    flagged = df[pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int).eq(1)]
    if flagged.empty:
        return None
    rs = flagged["reasoning"].dropna().astype(str).str.split(";")
    all_reasonings = [r.strip() for sub in rs for r in sub if str(r).strip()]
    if not all_reasonings:
        return None
    vc = pd.Series(all_reasonings).value_counts().head(8)
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.barh(list(reversed(vc.index.tolist())), list(reversed(vc.values.tolist())), color=GRAPH_COLOR)
    ax.set_title("Top XGBoost Reasons")
    ax.set_xlabel("Count")
    return _plot_to_rl_image(fig, max_width=520, max_height=320)

def _make_anomaly_flag_bar(df: pd.DataFrame):
    if "anomaly_flag" not in df.columns:
        return None
    s = pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int)
    counts = s.value_counts().reindex([0, 1], fill_value=0)
    fig = plt.figure(figsize=(8, 3.5))
    ax = fig.add_subplot(111)
    ax.bar(["Not Flagged", "Flagged"], [int(counts.loc[0]), int(counts.loc[1])], color=GRAPH_COLOR)
    ax.set_title("Anomaly Detection Flag Breakdown")
    ax.set_ylabel("Transactions")
    return _plot_to_rl_image(fig)

def _make_anomaly_reason_bar(df: pd.DataFrame):
    if "anomaly_flag" not in df.columns or "anomaly_reasoning" not in df.columns:
        return None
    flagged = df[pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int).eq(1)]
    if flagged.empty:
        return None
    rs = flagged["anomaly_reasoning"].dropna().astype(str).str.split(";")
    all_reasonings = [r.strip() for sub in rs for r in sub if str(r).strip()]
    if not all_reasonings:
        return None
    vc = pd.Series(all_reasonings).value_counts().head(8)
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.barh(list(reversed(vc.index.tolist())), list(reversed(vc.values.tolist())), color=GRAPH_COLOR)
    ax.set_title("Top Anomaly Detection Reasons")
    ax.set_xlabel("Count")
    return _plot_to_rl_image(fig, max_width=520, max_height=320)

def _make_review_priority_hist(df: pd.DataFrame):
    if "review_priority" not in df.columns:
        return None
    s = pd.to_numeric(df["review_priority"], errors="coerce").dropna()
    if s.empty:
        return None
    fig = plt.figure(figsize=(8, 3.5))
    ax = fig.add_subplot(111)
    ax.hist(s.values, bins=20, color=GRAPH_COLOR)
    ax.set_title("Review Priority Distribution")
    ax.set_xlabel("review_priority")
    ax.set_ylabel("Count")
    return _plot_to_rl_image(fig)

def _make_rule_trigger_bar(df: pd.DataFrame):
    rule_cols = [
        "rule_geo_jump",
        "rule_new_country_high_amt",
        "rule_dormant_spike",
        "rule_online_rare_spike",
        "rule_high_velocity",
        "rule_rare_mcc",
    ]
    existing = [c for c in rule_cols if c in df.columns]
    if not existing:
        return None
    counts = []
    labels = []
    for col in existing:
        count = int((pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int) == 1).sum())
        counts.append(count)
        labels.append(col.replace("rule_", ""))
    if not any(counts):
        return None
    fig = plt.figure(figsize=(8, 4.5))
    ax = fig.add_subplot(111)
    ax.barh(list(reversed(labels)), list(reversed(counts)), color=GRAPH_COLOR)
    ax.set_title("Fraud Rule Scenario Trigger Counts")
    ax.set_xlabel("Trigger Count")
    return _plot_to_rl_image(fig, max_width=520, max_height=320)

def convert_csv_to_pdf(csv_bytes: bytes) -> bytes:
    
    csv_text = csv_bytes.decode("utf-8", errors="replace")
    reader = csv.reader(csv_text.splitlines())
    rows = list(reader)

    df = pd.read_csv(io.BytesIO(csv_bytes))

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

    section_header_style = ParagraphStyle(
        "SectionHeaderStyle",
        parent=styles["Heading2"],
        alignment=0,
        fontName="Times-Roman"
    )

    table_header_style = ParagraphStyle(
        "TableHeaderStyle",
        parent=styles["Normal"],
        fontName="Times-Bold"
    )

    amount_table_header_style = ParagraphStyle(
        "AmountHeaderStyle",
        parent=styles["Normal"],
        alignment=2,
        fontName="Times-Bold"
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

    flagged_transactions_table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#b89fe3"),
        ("LINEBELOW", (0,1), (-1,-1), 0.5, colors.grey, None, [2, 2]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ])

    executive_summary_table_style = TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("FONTNAME", (0,0), (0,-1), "Times-Bold"),
        ("FONTNAME", (1,1), (-1,-1), "Times-Roman"),
        ("FONTSIZE", (0,0), (-1,-1), 10)
    ])

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

    total_tx = len(df)
    fraud_tx = int((pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int) == 1).sum()) if "xgb_flag" in df.columns else 0
    fraud_rate = (fraud_tx / total_tx * 100) if total_tx > 0 else 0

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        if ts.notna().any():
            date_range = f"{ts.min().strftime('%b %d, %Y')} — {ts.max().strftime('%b %d, %Y')}"
        else:
            date_range = "Unknown"
    else:
        date_range = "Unknown"

    if "amount" in df.columns:
        amt = pd.to_numeric(df["amount"], errors="coerce")
        total_spend = f"${amt.sum():,.2f}"
        avg_amount = f"${amt.mean():,.2f}"
    else:
        total_spend = "Unknown"
        avg_amount = "Unknown"

    executive_summary_data = [
        ["Date Range", date_range],
        ["Transactions Analyzed", f"{total_tx:,}"],
        ["Flagged Transactions", f"{fraud_tx:,}"],
        ["Fraud Rate", f"{fraud_rate:.2f}%"],
        ["Total Spend", total_spend],
        ["Average Transaction Amount", avg_amount]
    ]

    table_data = [[Paragraph("Timestamp",table_header_style),Paragraph("Merchant",table_header_style),Paragraph("Fraud Reasoning",table_header_style),Paragraph("Amount",amount_table_header_style)]]

    for row in rows[1:]:
        reasoning_value = row[reasoning_idx].strip() if len(row) > reasoning_idx else ""

        if reasoning_value:  
            mcc_str = ""
            try:
                mcc_str = str(int(float(row[mcc_idx])))
            except Exception:
                mcc_str = str(row[mcc_idx]) if len(row) > mcc_idx else ""
            table_data.append([
                Paragraph(str(row[timeDate_idx]), table_row_style),
                Paragraph(str(row[merchant_idx]) + " #" + mcc_str, table_row_style),
                Paragraph(str(reasoning_value), table_row_style),
                Paragraph(str(row[amount_idx]), amount_table_row_style)
            ])

    if len(table_data) == 1:
        table_data.append(["—", "—", "No flagged results found", "—"])

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

    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Executive Summary", section_header_style))

    executive_summary_table = Table(executive_summary_data, colWidths=[200, 350])
    executive_summary_table.setStyle(executive_summary_table_style)

    elements.append(executive_summary_table)

    xgb_flag_chart = _make_flag_bar(df)
    xgb_reason_chart = _make_reason_bar(df)
    anomaly_flag_chart = _make_anomaly_flag_bar(df)
    anomaly_reason_chart = _make_anomaly_reason_bar(df)
    harmonized_chart = _make_review_priority_hist(df)
    rule_chart = _make_rule_trigger_bar(df)

    if xgb_flag_chart or xgb_reason_chart:
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("XGBoost Fraud Breakdown", section_header_style))
        elements.append(Spacer(1, 8))
        if xgb_flag_chart:
            elements.append(xgb_flag_chart)
            elements.append(Spacer(1, 10))
        if xgb_reason_chart:
            elements.append(xgb_reason_chart)
            elements.append(Spacer(1, 10))

    if anomaly_flag_chart or anomaly_reason_chart:
        elements.append(Spacer(1, 5))
        elements.append(Paragraph("Anomaly Detection Breakdown", section_header_style))
        elements.append(Spacer(1, 8))
        if anomaly_flag_chart:
            elements.append(anomaly_flag_chart)
            elements.append(Spacer(1, 10))
        if anomaly_reason_chart:
            elements.append(anomaly_reason_chart)
            elements.append(Spacer(1, 10))

    if harmonized_chart:
        elements.append(Spacer(1, 5))
        elements.append(Paragraph("Harmonized Fraud Breakdown", section_header_style))
        elements.append(Spacer(1, 8))
        elements.append(harmonized_chart)
        elements.append(Spacer(1, 10))

    if rule_chart:
        elements.append(Spacer(1, 5))
        elements.append(Paragraph("Fraud Rule Scenario Logic", section_header_style))
        elements.append(Spacer(1, 8))
        elements.append(rule_chart)
        elements.append(Spacer(1, 10))

    elements.append(Spacer(1, 5))
    elements.append(Paragraph("Final Harmonized Flagged Transactions", section_header_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Fraudulent transactions are organized by review priority.", report_paragraph_style))

    elements.append(Spacer(1, 10))

    table = Table(
        table_data,
        colWidths=[90, 100, 300, 60],  
        repeatRows=1,
    )

    table.setStyle(flagged_transactions_table_style)

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)
    return buffer.read()