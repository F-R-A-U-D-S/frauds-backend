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
from reportlab.platypus import KeepTogether

from app.core.local_storage import load_decrypted

formattedDate = datetime.now().strftime("%B %d, %Y")
GRAPH_COLOR = "#8e44ad"
FINAL_REVIEW_PRIORITY_THRESHOLD = 0.65


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
    reasoning_counts = pd.Series(all_reasonings).value_counts() if all_reasonings else pd.Series(dtype=int)
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
        # "rule_rare_mcc",
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
        fontName="Times-Bold"
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

    summary_table_style = TableStyle([
        ("BOX", (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("FONTNAME", (0,0), (0,-1), "Times-Bold"),
        ("FONTNAME", (1,0), (-1,-1), "Times-Roman"),
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
    anomaly_tx = int((pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int) == 1).sum()) if "anomaly_flag" in df.columns else 0
    final_harmonized_tx = int((pd.to_numeric(df["review_priority"], errors="coerce").fillna(0) >= FINAL_REVIEW_PRIORITY_THRESHOLD).sum()) if "review_priority" in df.columns else 0

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
        if amt.notna().any():
            highest_amount = f"${amt.max():,.2f}"
            total_spend = f"${amt.sum():,.2f}"
            avg_amount = f"${amt.mean():,.2f}"
            median_amount = f"${amt.median():,.2f}"
        else:
            highest_amount = "Unknown"
            total_spend = "Unknown"
            avg_amount = "Unknown"
            median_amount = "Unknown"
    else:
        highest_amount = "Unknown"
        total_spend = "Unknown"
        avg_amount = "Unknown"
        median_amount = "Unknown"

    if "merchant" in df.columns:
        unique_merchants = df["merchant"].nunique()
    else:
        unique_merchants = "Unknown"

    if "country" in df.columns:
        amt_foreign_transactions = (df["country"].astype(str).str.lower() != "ca").sum()
    else:
        amt_foreign_transactions = "Unknown"

    transactions_per_day = "Unknown"
    top_fraud_merchant = "None"
    avg_flagged_amount = "Unknown"
    avg_normal_amount = "Unknown"
    multi_model_agreement_pct = "0.00%"

    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"], errors="coerce")
        valid_days = ts.dt.date.dropna()
        unique_days = valid_days.nunique()
        if unique_days > 0:
            transactions_per_day = f"{(total_tx / unique_days):.2f}"

    if "xgb_flag" in df.columns and "merchant" in df.columns:
        xgb_flag_series = pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int)
        fraud_merchants = df.loc[xgb_flag_series.eq(1), "merchant"].dropna().astype(str)
        if not fraud_merchants.empty:
            top_fraud_merchant = fraud_merchants.value_counts().idxmax()

    if "amount" in df.columns and "xgb_flag" in df.columns:
        amt = pd.to_numeric(df["amount"], errors="coerce")
        xgb_flag_series = pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int)

        flagged_amounts = amt[xgb_flag_series.eq(1)]
        normal_amounts = amt[xgb_flag_series.eq(0)]

        if flagged_amounts.notna().any():
            avg_flagged_amount = f"${flagged_amounts.mean():,.2f}"
        if normal_amounts.notna().any():
            avg_normal_amount = f"${normal_amounts.mean():,.2f}"

    if "xgb_flag" in df.columns and "anomaly_flag" in df.columns:
        xgb_flag_series = pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int)
        anomaly_flag_series = pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int)

        any_flagged = (xgb_flag_series.eq(1) | anomaly_flag_series.eq(1))
        both_flagged = (xgb_flag_series.eq(1) & anomaly_flag_series.eq(1))

        any_flagged_count = int(any_flagged.sum())
        both_flagged_count = int(both_flagged.sum())

        if any_flagged_count > 0:
            multi_model_agreement_pct = f"{(both_flagged_count / any_flagged_count * 100):.2f}%"

    executive_summary_data = [
        ["Date Range", date_range],
        ["Transactions Analyzed", f"{total_tx:,}"],
        ["XGBoost Flagged Transactions", f"{fraud_tx:,}"],
        ["Anomaly Flagged Transactions", f"{anomaly_tx:,}"],
        ["Final Harmonized Flagged", f"{final_harmonized_tx:,}"],
        ["Total Spend", total_spend],
        ["Average Transaction Amount", avg_amount]
    ]

    transaction_summary_data = [
        ["Largest Transaction", f"{highest_amount}"],
        ["Unique Merchants", f"{unique_merchants}"],
        ["Foreign Transactions", f"{amt_foreign_transactions}"]
    ]

    additional_risk_insights_data = [
        ["Median Transaction Amount", median_amount],
        ["Transactions Per Day", transactions_per_day],
        ["Top Fraud Merchant", top_fraud_merchant],
        ["Average Flagged Amount", avg_flagged_amount],
        ["Average Normal Amount", avg_normal_amount],
        ["Multi-Model Agreement", multi_model_agreement_pct],
    ]

    xgb_breakdown_data = [["Status", "Count", "Percentage"]]
    if "xgb_flag" in df.columns:
        xgb_counts = pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int).value_counts()
        xgb_flagged = int(xgb_counts.get(1, 0))
        xgb_not_flagged = int(xgb_counts.get(0, 0))
        xgb_breakdown_data.append(["Flagged", str(xgb_flagged), f"{(xgb_flagged / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
        xgb_breakdown_data.append(["Not Flagged", str(xgb_not_flagged), f"{(xgb_not_flagged / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
    else:
        xgb_breakdown_data.append(["Unavailable", "0", "0.00%"])

    xgb_reason_data = [["Reason", "Count", "Percentage"]]
    if "xgb_flag" in df.columns and "reasoning" in df.columns:
        flagged = df[pd.to_numeric(df["xgb_flag"], errors="coerce").fillna(0).astype(int).eq(1)]
        rs = flagged["reasoning"].dropna().astype(str).str.split(";")
        all_reasonings = [r.strip() for sub in rs for r in sub if str(r).strip()]
        vc = pd.Series(all_reasonings).value_counts() if all_reasonings else pd.Series(dtype=int)
        for label, count in vc.items():
            xgb_reason_data.append([label, str(int(count)), f"{(count / fraud_tx * 100):.2f}%" if fraud_tx > 0 else "0.00%"])
    if len(xgb_reason_data) == 1:
        xgb_reason_data.append(["No XGBoost reasons found", "0", "0.00%"])

    anomaly_breakdown_data = [["Status", "Count", "Percentage"]]
    if "anomaly_flag" in df.columns:
        anomaly_counts = pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int).value_counts()
        anomaly_flagged = int(anomaly_counts.get(1, 0))
        anomaly_not_flagged = int(anomaly_counts.get(0, 0))
        anomaly_breakdown_data.append(["Flagged", str(anomaly_flagged), f"{(anomaly_flagged / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
        anomaly_breakdown_data.append(["Not Flagged", str(anomaly_not_flagged), f"{(anomaly_not_flagged / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
    else:
        anomaly_breakdown_data.append(["Unavailable", "0", "0.00%"])

    anomaly_reason_data = [["Reason", "Count", "Percentage"]]
    if "anomaly_flag" in df.columns and "anomaly_reasoning" in df.columns:
        anomaly_flagged_rows = df[pd.to_numeric(df["anomaly_flag"], errors="coerce").fillna(0).astype(int).eq(1)]
        ars = anomaly_flagged_rows["anomaly_reasoning"].dropna().astype(str).str.split(";")
        all_anomaly_reasonings = [r.strip() for sub in ars for r in sub if str(r).strip()]
        avc = pd.Series(all_anomaly_reasonings).value_counts() if all_anomaly_reasonings else pd.Series(dtype=int)
        for label, count in avc.items():
            anomaly_reason_data.append([label, str(int(count)), f"{(count / anomaly_tx * 100):.2f}%" if anomaly_tx > 0 else "0.00%"])
    if len(anomaly_reason_data) == 1:
        anomaly_reason_data.append(["No anomaly reasons found", "0", "0.00%"])

    harmonized_breakdown_data = [["Bucket", "Count", "Percentage"]]
    if "review_priority" in df.columns:
        rp = pd.to_numeric(df["review_priority"], errors="coerce").fillna(0)
        low_count = int((rp < 0.40).sum())
        med_count = int(((rp >= 0.40) & (rp < FINAL_REVIEW_PRIORITY_THRESHOLD)).sum())
        high_count = int((rp >= FINAL_REVIEW_PRIORITY_THRESHOLD).sum())
        harmonized_breakdown_data.append(["Low (< 0.40)", str(low_count), f"{(low_count / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
        harmonized_breakdown_data.append([f"Medium (0.40 - {FINAL_REVIEW_PRIORITY_THRESHOLD:.2f})", str(med_count), f"{(med_count / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
        harmonized_breakdown_data.append([f"High (>= {FINAL_REVIEW_PRIORITY_THRESHOLD:.2f})", str(high_count), f"{(high_count / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"])
    else:
        harmonized_breakdown_data.append(["Unavailable", "0", "0.00%"])

    rule_cols = [
        "rule_geo_jump",
        "rule_new_country_high_amt",
        "rule_dormant_spike",
        "rule_online_rare_spike",
        "rule_high_velocity",
        # "rule_rare_mcc",
    ]

    rule_breakdown_data = [["Rule", "Count", "Percentage"]]
    existing_rule_cols = [c for c in rule_cols if c in df.columns]
    if existing_rule_cols:
        for col in existing_rule_cols:
            count = int((pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int) == 1).sum())
            rule_breakdown_data.append([
                col.replace("rule_", ""),
                str(count),
                f"{(count / total_tx * 100):.2f}%" if total_tx > 0 else "0.00%"
            ])
    else:
        rule_breakdown_data.append(["No rule columns found", "0", "0.00%"])

    xgb_table_data = [[Paragraph("Timestamp", table_header_style), Paragraph("Merchant", table_header_style), Paragraph("Fraud Reasoning", table_header_style), Paragraph("Amount", amount_table_header_style)]]
    anomaly_table_data = [[Paragraph("Timestamp", table_header_style), Paragraph("Merchant", table_header_style), Paragraph("Anomaly Reasoning", table_header_style), Paragraph("Amount", amount_table_header_style)]]
    rule_reason_table_data = [[Paragraph("Timestamp", table_header_style), Paragraph("Merchant", table_header_style), Paragraph("Rule Reasoning", table_header_style), Paragraph("Amount", amount_table_header_style)]]
    final_table_data = [[Paragraph("Timestamp", table_header_style), Paragraph("Merchant", table_header_style), Paragraph("Combined Reasoning", table_header_style), Paragraph("Amount", amount_table_header_style)]]

    for row in rows[1:]:
        current_timestamp = str(row[timeDate_idx]) if len(row) > timeDate_idx else "—"
        current_merchant = str(row[merchant_idx]) if len(row) > merchant_idx else "—"
        current_amount = str(row[amount_idx]) if len(row) > amount_idx else "—"

        mcc_str = ""
        try:
            mcc_str = str(int(float(row[mcc_idx])))
        except Exception:
            mcc_str = str(row[mcc_idx]) if len(row) > mcc_idx else ""

        merchant_display = current_merchant + " #" + mcc_str

        xgb_reason = str(row[reasoning_idx]).strip() if len(row) > reasoning_idx and pd.notna(row[reasoning_idx]) else ""

        anomaly_reason = ""
        if "anomaly_reasoning" in df.columns:
            anomaly_reason_idx = header.index("anomaly_reasoning")
            anomaly_reason = str(row[anomaly_reason_idx]).strip() if len(row) > anomaly_reason_idx and pd.notna(row[anomaly_reason_idx]) else ""

        rule_reason = ""
        if "rule_reasoning" in df.columns:
            rule_reason_idx = header.index("rule_reasoning")
            rule_reason = str(row[rule_reason_idx]).strip() if len(row) > rule_reason_idx and pd.notna(row[rule_reason_idx]) else ""

        rf_reason = ""
        if "rf_reasoning" in df.columns:
            rf_reason_idx = header.index("rf_reasoning")
            rf_reason = str(row[rf_reason_idx]).strip() if len(row) > rf_reason_idx and pd.notna(row[rf_reason_idx]) else ""

        xgb_flag_value = 0
        if "xgb_flag" in df.columns:
            xgb_flag_idx = header.index("xgb_flag")
            try:
                xgb_flag_value = int(float(row[xgb_flag_idx]))
            except Exception:
                xgb_flag_value = 0

        anomaly_flag_value = 0
        if "anomaly_flag" in df.columns:
            anomaly_flag_idx = header.index("anomaly_flag")
            try:
                anomaly_flag_value = int(float(row[anomaly_flag_idx]))
            except Exception:
                anomaly_flag_value = 0

        review_priority_value = 0.0
        if "review_priority" in df.columns:
            review_priority_idx = header.index("review_priority")
            try:
                review_priority_value = float(row[review_priority_idx])
            except Exception:
                review_priority_value = 0.0

        if xgb_flag_value == 1:
            xgb_table_data.append([
                Paragraph(current_timestamp, table_row_style),
                Paragraph(merchant_display, table_row_style),
                Paragraph(xgb_reason if xgb_reason else "—", table_row_style),
                Paragraph(current_amount, amount_table_row_style)
            ])

        if anomaly_flag_value == 1:
            anomaly_table_data.append([
                Paragraph(current_timestamp, table_row_style),
                Paragraph(merchant_display, table_row_style),
                Paragraph(anomaly_reason if anomaly_reason else "—", table_row_style),
                Paragraph(current_amount, amount_table_row_style)
            ])

        if rule_reason:
            rule_reason_table_data.append([
                Paragraph(current_timestamp, table_row_style),
                Paragraph(merchant_display, table_row_style),
                Paragraph(rule_reason, table_row_style),
                Paragraph(current_amount, amount_table_row_style)
            ])

        if review_priority_value >= FINAL_REVIEW_PRIORITY_THRESHOLD:
            combined_parts = []
            if xgb_reason:
                combined_parts.append(f"XGB: {xgb_reason}")
            if anomaly_reason:
                combined_parts.append(f"ANOM: {anomaly_reason}")
            if rf_reason:
                combined_parts.append(f"RF: {rf_reason}")
            if rule_reason:
                combined_parts.append(f"RULE: {rule_reason}")

            combined_reasoning = "; ".join(combined_parts) if combined_parts else "High review priority"

            final_table_data.append([
                Paragraph(current_timestamp, table_row_style),
                Paragraph(merchant_display, table_row_style),
                Paragraph(combined_reasoning, table_row_style),
                Paragraph(current_amount, amount_table_row_style)
            ])

    if len(xgb_table_data) == 1:
        xgb_table_data.append(["—", "—", "No XGBoost flagged results found", "—"])

    if len(anomaly_table_data) == 1:
        anomaly_table_data.append(["—", "—", "No anomaly flagged results found", "—"])

    if len(rule_reason_table_data) == 1:
        rule_reason_table_data.append(["—", "—", "No rule reasoning found", "—"])

    if len(final_table_data) == 1:
        final_table_data.append(["—", "—", "No harmonized flagged results found", "—"])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=25, leftMargin=25, rightMargin=25)
    styles = getSampleStyleSheet()

    elements = []

    img = Image("fraud_logo_64.png")
    img.hAlign = "LEFT"
    elements.append(img)

    elements.append(Spacer(1, 25))

    elements.append(Paragraph("Fraud Analysis Summary",report_header_style))

    formattedDate = datetime.now().strftime("%B %d, %Y")
    elements.append(Paragraph("Report Date: " + formattedDate, report_paragraph_style))

    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Executive Summary", section_header_style))

    executive_summary_table = Table(executive_summary_data, colWidths=[200, 350])
    executive_summary_table.setStyle(summary_table_style)

    elements.append(executive_summary_table)
    elements.append(Spacer(1, 10))

    transaction_summary_table = Table(transaction_summary_data, colWidths=[200, 350])
    transaction_summary_table.setStyle(summary_table_style)

    elements.append(KeepTogether([Paragraph("Transaction Summary", section_header_style), transaction_summary_table]))
    elements.append(Spacer(1, 10))

    additional_risk_insights_table = Table(additional_risk_insights_data, colWidths=[200, 350])
    additional_risk_insights_table.setStyle(summary_table_style)

    elements.append(KeepTogether([Paragraph("Additional Risk Insights", section_header_style), additional_risk_insights_table]))
    elements.append(Spacer(1, 10))

    xgb_flag_chart = _make_flag_bar(df)
    xgb_reason_chart = _make_reason_bar(df)
    anomaly_flag_chart = _make_anomaly_flag_bar(df)
    anomaly_reason_chart = _make_anomaly_reason_bar(df)
    harmonized_chart = _make_review_priority_hist(df)
    rule_chart = _make_rule_trigger_bar(df)

    xgb_breakdown_table = Table(xgb_breakdown_data, colWidths=[250, 150, 150])
    xgb_breakdown_table.setStyle(summary_table_style)

    xgb_reason_table = Table(xgb_reason_data, colWidths=[350, 100, 100])
    xgb_reason_table.setStyle(summary_table_style)

    anomaly_breakdown_table = Table(anomaly_breakdown_data, colWidths=[250, 150, 150])
    anomaly_breakdown_table.setStyle(summary_table_style)

    anomaly_reason_table = Table(anomaly_reason_data, colWidths=[350, 100, 100])
    anomaly_reason_table.setStyle(summary_table_style)

    harmonized_breakdown_table = Table(harmonized_breakdown_data, colWidths=[250, 150, 150])
    harmonized_breakdown_table.setStyle(summary_table_style)

    rule_breakdown_table = Table(rule_breakdown_data, colWidths=[250, 150, 150])
    rule_breakdown_table.setStyle(summary_table_style)

    xgb_tx_table = Table(
        xgb_table_data,
        colWidths=[90, 100, 300, 60],
        repeatRows=1,
    )
    xgb_tx_table.setStyle(flagged_transactions_table_style)

    anomaly_tx_table = Table(
        anomaly_table_data,
        colWidths=[90, 100, 300, 60],
        repeatRows=1,
    )
    anomaly_tx_table.setStyle(flagged_transactions_table_style)

    rule_reason_table = Table(
        rule_reason_table_data,
        colWidths=[90, 100, 300, 60],
        repeatRows=1,
    )
    rule_reason_table.setStyle(flagged_transactions_table_style)

    final_tx_table = Table(
        final_table_data,
        colWidths=[90, 100, 300, 60],
        repeatRows=1,
    )
    final_tx_table.setStyle(flagged_transactions_table_style)

    if xgb_flag_chart or xgb_reason_chart:
        elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("XGBoost Fraud Breakdown", section_header_style),
            xgb_breakdown_table,
            Spacer(1, 10),
            xgb_reason_table
        ]))
        elements.append(Spacer(1, 10))
        if xgb_flag_chart:
            elements.append(xgb_flag_chart)
            elements.append(Spacer(1, 15))
        if xgb_reason_chart:
            elements.append(xgb_reason_chart)
            elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("XGBoost Flagged Transactions", section_header_style),
            Paragraph("Transactions flagged by the supervised fraud model.", report_paragraph_style),
            Spacer(1, 10),
            xgb_tx_table
        ]))
        elements.append(Spacer(1, 15))

    if anomaly_flag_chart or anomaly_reason_chart:
        elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("Anomaly Detection Breakdown", section_header_style),
            anomaly_breakdown_table,
            Spacer(1, 10),
            anomaly_reason_table
        ]))
        elements.append(Spacer(1, 10))
        if anomaly_flag_chart:
            elements.append(anomaly_flag_chart)
            elements.append(Spacer(1, 15))
        if anomaly_reason_chart:
            elements.append(anomaly_reason_chart)
            elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("Anomaly Flagged Transactions", section_header_style),
            Paragraph("Transactions flagged as unusual for this account.", report_paragraph_style),
            Spacer(1, 10),
            anomaly_tx_table
        ]))
        elements.append(Spacer(1, 15))

    if harmonized_chart:
        elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("Harmonized Fraud Breakdown", section_header_style),
            harmonized_breakdown_table
        ]))
        elements.append(Spacer(1, 10))
        elements.append(harmonized_chart)
        elements.append(Spacer(1, 15))

    if rule_chart or len(rule_breakdown_data) > 1:
        elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("Fraud Rule Scenario Logic", section_header_style),
            rule_breakdown_table
        ]))
        elements.append(Spacer(1, 10))
        if rule_chart:
            elements.append(rule_chart)
            elements.append(Spacer(1, 15))
        elements.append(KeepTogether([
            Paragraph("Rule Reasoning Table", section_header_style),
            Paragraph("Transactions with explicit fraud rule triggers.", report_paragraph_style),
            Spacer(1, 10),
            rule_reason_table
        ]))
        elements.append(Spacer(1, 15))

    elements.append(KeepTogether([
        Paragraph("Final Harmonized Flagged Transactions", section_header_style),
        Paragraph(f"Fraudulent transactions are organized by review priority. Transactions shown here have review_priority >= {FINAL_REVIEW_PRIORITY_THRESHOLD:.2f}.", report_paragraph_style),
        Spacer(1, 10),
        final_tx_table
    ]))

    doc.build(elements)

    buffer.seek(0)
    return buffer.read()