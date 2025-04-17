from uuid import UUID
from pydantic import BaseModel, Field
from typing import Union, Optional


class AuthAccountToken(BaseModel):
    token: str

    class Config:
        from_attributes = True


class AccountInput(BaseModel):
    email: str
    password: str
    pix_key: Optional[str] = Field(None)

    class Config:
        from_attributes = True


class AccountOutput(BaseModel):
    email: str
    message: str

    class Config:
        from_attributes = True