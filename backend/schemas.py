from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VpnClientOut(BaseModel):
    id: int
    common_name: str
    vpn_ip: str
    revoked: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MappingCreate(BaseModel):
    protocol: Literal["tcp", "udp"]
    local_port: int = Field(ge=1, le=65535)


class MappingOut(BaseModel):
    id: int
    protocol: str
    external_port: int
    local_port: int
    status: str
    public_host: str
    created_at: datetime

    class Config:
        from_attributes = True
