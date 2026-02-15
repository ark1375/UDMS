from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator


BookingStatus = Literal["Completed", "Cancelled by Customer", "Cancelled by Driver", "Incomplete", "No Driver Found"]


class TransactionCreate(BaseModel):
    """
    Create input:
    - customer_id required
    - ride_distance required (because booking_value is computed from it)
    - trip_ts defaults to now
    - booking_status defaults to Completed
    - vehicle_type defaults to Auto
    - payment_method defaults to cash
    """
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(..., min_length=1)
    ride_distance: float = Field(..., gt=0)

    trip_ts: datetime = Field(default_factory=datetime.now)
    booking_status: BookingStatus = "Completed"
    vehicle_type: str = "Auto"
    payment_method: str = "cash"

    driver_rating: Optional[float] = Field(default=None, ge=0, le=5)
    customer_rating: Optional[float] = Field(default=None, ge=0, le=5)
    trip_undone_reason: Optional[str] = None

    @field_validator("customer_id")
    @classmethod
    def strip_customer_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("vehicle_type", "payment_method")
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()


class TransactionUpdate(BaseModel):
    """
    Update input:
    - BookingID + CustomerID come from path/query and are NOT changeable
    - At least one field must be provided
    """
    model_config = ConfigDict(extra="forbid")

    trip_ts: Optional[datetime] = None
    booking_status: Optional[BookingStatus] = None
    vehicle_type: Optional[str] = None
    payment_method: Optional[str] = None
    ride_distance: Optional[float] = Field(default=None, gt=0)

    driver_rating: Optional[float] = Field(default=None, ge=0, le=5)
    customer_rating: Optional[float] = Field(default=None, ge=0, le=5)
    trip_undone_reason: Optional[str] = None


class TransactionOut(BaseModel):
    """
    Output model matches silver.transaction_fact shape (plus transaction_fact_pk).
    """
    model_config = ConfigDict(from_attributes=True)

    transaction_fact_pk: str
    customer_id: str
    booking_id: str
    trip_ts: datetime

    booking_value: float
    ride_distance: float

    booking_status: str
    vehicle_type: str
    payment_method: str

    driver_rating: Optional[float] = None
    customer_rating: Optional[float] = None
    trip_undone_reason: Optional[str] = None

class DeleteResult(BaseModel):
    deleted: int