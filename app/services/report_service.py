import io
import pandas as pd

from app.core.local_storage import load_decrypted
"""
def get_report(report_id: int):
    #TO DO : Downloads dummy file currently
    file_path = os.path.join(os.path.dirname(__file__), "test_csv.csv")
    return FileResponse(file_path, media_type="text/csv", filename="test_csv.csv") 
"""
def get_fraud_breakdown(key:str):
    csv_bytes = load_decrypted(key)
    df = pd.read_csv(io.BytesIO(csv_bytes))  
    fraud_counts = df["is_fraud"].value_counts()
    data_for_js = [
    {"label": "Not Fraud", "value": int(fraud_counts.get(0, 0))},
    {"label": "Fraud", "value": int(fraud_counts.get(1, 0))}
    ]
    return data_for_js

