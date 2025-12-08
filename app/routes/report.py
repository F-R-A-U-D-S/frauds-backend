# report generation + encryption
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.services import report_service

router = APIRouter(prefix="/report", tags=["report"])
service = report_service

"""
@router.get("/csv/{report_id}")
def read_csv_report(report_id: int, user = Depends(get_current_user)):
    report = service.get_report(report_id)
    return report
"""
@router.get("/fraud_breakdown/{key:path}")
async def fraud_breakdown(key: str, user = Depends(get_current_user)):
    return service.get_fraud_breakdown(key)
    

