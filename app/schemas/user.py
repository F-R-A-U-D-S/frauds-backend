from pydantic import BaseModel



class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str

class PredictRequest(BaseModel):
    # result_key: str
    input_key: str
