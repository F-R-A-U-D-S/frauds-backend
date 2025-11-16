# report generation + encryption
from fastapi import APIRouter
from services import report_service

router = APIRouter(prefix="/report", tags=["report"])
service = report_service

@router.get("/csv/{report_id}")
def read_csv_report(report_id: int):
    report = service.get_report(report_id)
    return report

