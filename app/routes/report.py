# report generation + encryption
from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.services import report_service

router = APIRouter(prefix="/report", tags=["report"])
service = report_service

@router.get("/fraud_status_breakdown/{key:path}")
async def fraud_status_breakdown(key: str, user = Depends(get_current_user)):
    return service.get_fraud_status_breakdown(key)

@router.get("/fraud_type_breakdown/{key:path}")
async def fraud_type_breakdown(key: str, user = Depends(get_current_user)):
    return service.get_fraud_type_breakdown(key)


    

