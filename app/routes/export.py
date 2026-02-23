from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.db.models import User
from app.services.export_service import process_export_request, validate_and_consume_token
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])

@router.post("/request", status_code=202)
def request_export(
    background_tasks: BackgroundTasks,
    format: str = Query(..., regex="^(csv|pdf)$"),
    current_user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Request a fraud analysis export.
    Generates a secure token and sends a download link via email.
    """
    # Fetch full user object
    user_id = current_user_payload.get("sub")
    current_user = db.query(User).filter(User.id == user_id).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")
    # Trigger background task
    # Passing db session to background task is generally not recommended if session is closed.
    # However, since we are doing a quick prototype, and process_export_request handles basic logic.
    # Ideally, we would pass db factory or handle session inside task. 
    # For now, we'll run it synchronously or rely on session lifespan if minimal.
    # BETTER: Let's run it here or pass a new session creator. 
    # To keep it simple and safe: We will run the synchronous part of token creation HERE, 
    # and only the file generation/email in background. 
    # But `process_export_request` does everything.
    
    # Let's just schedule it. Note: 'db' dependency might close. 
    # Ideally: background_tasks.add_task(process_export_request, current_user, format, db)
    # But db closing issue. 
    # So we'll call it synchronously for the token creation part inside the service, 
    # or just risk it/fix it later. For this strict flow, let's just run it.
    
    background_tasks.add_task(process_export_request, current_user.id, current_user.email, format)
    
    return {"message": "Export started. You will receive an email with the download link shortly."}

@router.get("/download")
def download_export(
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Download the exported file using a secure, one-time token.
    """
    try:
        file_path = validate_and_consume_token(token, db)
        
        # Determine content type
        media_type = "text/csv" if file_path.endswith(".csv") else "application/pdf"
        filename = file_path.split("/")[-1].split("\\")[-1] # Simple split for safety
        
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
