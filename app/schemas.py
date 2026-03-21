from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IosSmsIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender: str = Field(min_length=2, max_length=64)
    contact_name: str | None = Field(default=None, max_length=128)
    message: str = Field(min_length=5)
    received_at: datetime
    device_name: str | None = Field(default=None, max_length=128)


class IngestResponse(BaseModel):
    ok: bool
    transaction_id: str | None = None
    status: str
    duplicate: bool = False


class ReviewSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str | None = None
    participant_ids: list[str] = Field(default_factory=list)
    split_mode: Literal["equal", "custom"] = "equal"
    description: str | None = None
    notes: str | None = None
    custom_amounts_minor: dict[str, int] = Field(default_factory=dict)
    action: Literal["post", "draft", "manually_done", "ignore"]


class ActionResponse(BaseModel):
    ok: bool
    status: str
    detail: str
    transaction_id: str


class TelegramWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    update_id: int | None = None
    message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None
