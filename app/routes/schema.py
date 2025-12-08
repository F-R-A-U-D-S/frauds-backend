from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from app.services.schema_service import save_schema, load_schema
from fastapi import HTTPException


router = APIRouter(prefix="/schema", tags=["Schema"])

class SchemaMapping(BaseModel):
    bank_name: str
    mapping: Dict[str, str]

@router.post("/save")
async def save_schema_api(data: SchemaMapping):
    save_schema(data.bank_name, data.mapping)
    return {
        "message": f"Default schema saved for {data.bank_name}",
         "data": data.mapping}

@router.get("/load/{bank_name}")
async def load_schema_api(bank_name: str):
    schema = load_schema(bank_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"No schema found for bank: {bank_name}")
    return {
        "bank": bank_name,
        "mapping": schema,
    }