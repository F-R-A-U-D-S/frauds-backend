from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict


router = APIRouter(prefix="/schema", tags=["Schema"])

class SchemaMapping(BaseModel):
    mapping: Dict[str, str]

@router.post("/save")
async def save_schema(data: SchemaMapping):
    return {"message": "Schema saved successfully"}
