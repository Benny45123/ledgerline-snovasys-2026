"""
How this works / why it is safe:
This module defines strict Pydantic v2 schemas for the AI Financial Intelligence
and Copilot service. Strict validation (extra="forbid", strict=True) prevents
field injection and mass-assignment attacks.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(..., min_length=1, max_length=1000, description="Natural language question or request")
    account_id: UUID | None = Field(default=None, description="Optional account context for holders")
    history: list[ChatMessage] = Field(default_factory=list, max_length=10, description="Recent conversation turns")

    @field_validator("account_id", mode="before")
    @classmethod
    def parse_account_id(cls, v: Any) -> Any:
        if isinstance(v, str):
            try:
                return UUID(v)
            except ValueError as e:
                raise ValueError("Invalid UUID format") from e
        return v


class InsightCard(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str
    value: str
    change: str | None = None
    sentiment: Literal["positive", "neutral", "warning", "negative"] = "neutral"


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reply: str
    provider: str  # "groq" | "gemini" | "deterministic"
    model: str
    intent: str  # "search" | "anomaly" | "forecast" | "insights" | "reconciliation" | "general"
    risk_score: int | None = None  # 0 to 100
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    risk_reasons: list[str] = Field(default_factory=list)
    insights: list[InsightCard] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    data_payload: dict[str, Any] | None = None
