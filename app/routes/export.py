from urllib.parse import quote
import logging

from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from fastapi.responses import Response, RedirectResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.db.models import User
from app.services.export_service import (
    process_export_request,
    validate_and_consume_token,
    infer_export_type_from_key,
)
from app.core.local_storage import load_decrypted

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/request", status_code=202)
def request_export(
    background_tasks: BackgroundTasks,
    format: str = Query(..., pattern="^(csv|pdf)$"),
    current_user_payload: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user_payload.get("sub")
    current_user = db.query(User).filter(User.id == user_id).first()

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    if not current_user.email:
        raise HTTPException(status_code=400, detail="User does not have an email address")

    background_tasks.add_task(
        process_export_request,
        current_user.id,
        current_user.email,
        format,
    )

    return {
        "message": "Export started. You will receive an email with the download link shortly."
    }


@router.get("/download")
def download_export(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        s3_key = validate_and_consume_token(token, db)
        file_bytes = load_decrypted(s3_key)
        media_type, filename = infer_export_type_from_key(s3_key)

        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except ValueError as e:
        error_message = quote(str(e))
        return RedirectResponse(
            url=f"{settings.FRONTEND_BASE_URL.rstrip('/')}/download-error?error={error_message}"
        )
    except Exception as e:
        logger.exception(f"Download error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")