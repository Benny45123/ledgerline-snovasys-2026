"""
How this works / why it is safe:
This module defines Pydantic schemas for authentication payloads.
All models configure extra="forbid" and strict=True.
Unknown fields, type coercions, or malicious mass-assignment attempts
(e.g., passing 'role' or 'is_active' in the login payload) are rejected at the edge.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LoginRequest(StrictBaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, max_length=256, description="Plaintext password")


class UserResponse(StrictBaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime


class LoginResponse(StrictBaseModel):
    token: str
    expires_at: datetime
    user: UserResponse
