"""Pydantic models for tool I/O and the shared response envelope."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["success", "error", "pending"]


class ToolEnvelope(BaseModel):
    """The contract every tool returns, preserved from the n8n system."""

    status: Status
    data: Any = None
    message: str = ""

    def to_tool_string(self) -> str:
        """Serialise to the compact JSON string the LLM reads."""
        return self.model_dump_json()

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "ToolEnvelope":
        return cls(status="success", data=data, message=message)

    @classmethod
    def fail(cls, message: str, data: Any = None) -> "ToolEnvelope":
        return cls(status="error", data=data, message=message)

    @classmethod
    def pending(cls, message: str) -> "ToolEnvelope":
        """The action was NOT performed; the caller must confirm a read-back first."""
        return cls(status="pending", data=None, message=message)


# ---- Tool argument schemas (only the LLM-supplied args; phone/ids are injected) ----

SERVICES = ("Cleaning", "Whitening", "Extraction")
ServiceName = Literal["Cleaning", "Whitening", "Extraction"]


class UpsertPatientArgs(BaseModel):
    first_name: str = Field(..., description="Caller's first name as spoken")
    last_name: str = Field(..., description="Caller's last name as spoken")
    email: str | None = Field(None, description="Optional email")


class AvailableSlotsArgs(BaseModel):
    service_name: ServiceName = Field(..., description="Exact service: Cleaning, Whitening or Extraction")
    date: str = Field(..., description="Date in YYYY-MM-DD")


class BookArgs(BaseModel):
    service_name: ServiceName
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM 24h, from get_available_slots")


class RescheduleArgs(BaseModel):
    new_date: str = Field(..., description="YYYY-MM-DD")
    new_time: str = Field(..., description="HH:MM 24h")
    new_service_name: ServiceName | None = Field(
        None, description="Only if the caller is changing the service; omit to keep current."
    )


class AppointmentEmailArgs(BaseModel):
    email: str = Field(..., description="Recipient email address, EXACTLY as confirmed (spelled back) with the caller")
    operation: Literal["booking", "reschedule", "cancellation"] = Field(
        ..., description="Which operation just completed successfully"
    )
    service: str = Field("", description="Service in Spanish: limpieza / blanqueamiento / extracción")
    date: str = Field("", description="Appointment date, YYYY-MM-DD")
    time: str = Field("", description="Appointment time, HH:MM 24h")
    patient_name: str = Field("", description="Caller's first name, if known")


class EmptyArgs(BaseModel):
    """For tools whose only input is the injected session phone."""
    pass
