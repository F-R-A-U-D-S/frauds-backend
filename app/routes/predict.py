from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user

from app.core.local_storage import (
    store_encrypted,
    load_decrypted,
    delete_key,
)

from app.services.model_service import process_local_and_predict

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/")
async def predict(file: UploadFile = File(...), user = Depends(get_current_user)):
    # save encrypted uploaded file
    input_key = store_encrypted(file.file, prefix="incoming")

    # run model, get encrypted result file key
    result_key = process_local_and_predict(input_key)

    return {"result_key": result_key}


@router.get("/download/{key:path}")
async def download_result(key: str):
    # decrypt results in memory
    data = load_decrypted(key)

    # delete encrypted file after serving
    delete_key(key)

    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=flagged_results.csv"
        },
    )