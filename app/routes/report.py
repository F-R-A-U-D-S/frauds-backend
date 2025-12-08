# report generation + encryption
from fastapi import APIRouter
from app.services import report_service

router = APIRouter(prefix="/report", tags=["report"])
service = report_service

"""
@router.get("/csv/{report_id}")
def read_csv_report(report_id: int):
    report = service.get_report(report_id)
    return report
"""
@router.get("/fraud_breakdown/{key:path}")
async def fraud_breakdown(key: str):
    return service.get_fraud_breakdown(key)
    

