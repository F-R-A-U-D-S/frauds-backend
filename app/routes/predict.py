from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.schemas.user import PredictRequest

from app.core.local_storage import (
    store_encrypted,
    load_decrypted,
    delete_key,
)

from app.services.model_service import process_local_and_predict

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/")
async def predict(request: PredictRequest, user = Depends(get_current_user)):
    
    print(f"[DEBUG] /Raw input received: {request.input_key}")

    # save encrypted uploaded file key
    input_key = request.input_key
    

    try:
        # run model, get encrypted result file key
        result_key = process_local_and_predict(input_key)
    except Exception as e:
        print(f"[ERROR] Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    print(f"[DEBUG] Prediction successful, result key: {result_key}")
    return {"result_key": result_key}


@router.get("/download/{key:path}")
async def download_result(key: str):
    # decrypt results in memory
    try:
        print("🔍 Downloading key:", key)
        data = load_decrypted(key)
    except Exception as e:
        print("❌ Decrypt error:", str(e))
        raise HTTPException(status_code=500, detail=f"Decrypt failed: {str(e)}")

    # delete encrypted file after serving
    delete_key(key)

    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=flagged_results.csv"
        },
    )