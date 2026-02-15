from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
import secrets

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from .models import TransactionCreate, TransactionUpdate, TransactionOut, DeleteResult


router = APIRouter(tags=["transactions"])


def _make_booking_id() -> str:
    # Prefix CNR + 10 hex chars (stable length, low collision risk)
    return f"CNR{secrets.token_hex(5).upper()}"


def _make_pk(customer_id: str, booking_id: str) -> str:
    return f"{customer_id}|{booking_id}"


def _validate_business_rules(booking_status: str, ride_distance: Optional[float], booking_value: Optional[float], trip_undone_reason: Optional[str]) -> None:
    """
    Rules you stated:
    - Completed trip must have PRICE and DISTANCE
    - Completed trips should not have Trip Undone Reason
    """
    if booking_status == "Completed":
        if ride_distance is None or ride_distance <= 0:
            raise HTTPException(status_code=422, detail="Completed trips must have ride_distance > 0.")
        if booking_value is None or booking_value <= 0:
            raise HTTPException(status_code=422, detail="Completed trips must have booking_value > 0.")
        if trip_undone_reason is not None:
            raise HTTPException(status_code=422, detail="Completed trips must not have trip_undone_reason.")


@router.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionCreate, request: Request):
    db = request.app.state.db
    settings = request.app.state.settings

    booking_id = _make_booking_id()
    transaction_id = _make_pk(payload.customer_id, booking_id)

    booking_value = float(payload.ride_distance) * float(settings.rate_per_distance)

    # Enforce rule about completed vs undone reason
    _validate_business_rules(
        booking_status=payload.booking_status,
        ride_distance=payload.ride_distance,
        booking_value=booking_value,
        trip_undone_reason=payload.trip_undone_reason,
    )

    conn = db.get_connection()

    try:
        conn.execute(
            """
            INSERT INTO silver.TransactionFact (
                transaction_id,
                customer_id,
                booking_id,
                trip_ts,
                booking_value,
                ride_distance,
                driver_rating,
                customer_rating,
                booking_status,
                vehicle_type,
                payment_method,
                trip_undone_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                transaction_id,
                payload.customer_id,
                booking_id,
                payload.trip_ts,
                booking_value,
                payload.ride_distance,
                payload.driver_rating,
                payload.customer_rating,
                payload.booking_status,
                payload.vehicle_type,
                payload.payment_method,
                payload.trip_undone_reason,
            ],
        )
    except Exception as e:
        # likely PK conflict or schema mismatch
        raise HTTPException(status_code=500, detail=f"Insert failed: {str(e)}")

    row = conn.execute(
        """
        SELECT
          transaction_id, customer_id, booking_id, trip_ts,
          booking_value, ride_distance,
          booking_status, vehicle_type, payment_method,
          driver_rating, customer_rating, trip_undone_reason
        FROM silver.TransactionFact
        WHERE transaction_id = ?
        """,
        [transaction_id],
    ).fetchone()

    if not row:
        raise HTTPException(status_code=500, detail="Insert succeeded but record not found.")

    return TransactionOut(
        transaction_id=row[0],
        customer_id=row[1],
        booking_id=row[2],
        trip_ts=row[3],
        booking_value=row[4],
        ride_distance=row[5],
        booking_status=row[6],
        vehicle_type=row[7],
        payment_method=row[8],
        driver_rating=row[9],
        customer_rating=row[10],
        trip_undone_reason=row[11],
    )


@router.get("/transactions", response_model=List[TransactionOut])
def read_transactions(
    request: Request,
    customer_id: Optional[str] = Query(default=None),
    booking_id: Optional[str] = Query(default=None),
):
    """
    READ rules:
    - booking_id=None, customer_id=123 => valid (returns all for customer)
    - booking_id=..., customer_id=None => NOT valid
    - booking_id=..., customer_id=... => valid (returns single or 0/1 row)
    - both None => NOT valid
    """
    if customer_id is None and booking_id is None:
        raise HTTPException(status_code=422, detail="Provide customer_id, or (customer_id + booking_id).")
    if customer_id is None and booking_id is not None:
        raise HTTPException(status_code=422, detail="booking_id alone is not valid. Provide customer_id as well.")

    db = request.app.state.db
    conn = db.get_connection()

    if booking_id is None:
        rows = conn.execute(
            """
            SELECT
              transaction_id, customer_id, booking_id, trip_ts,
              booking_value, ride_distance,
              booking_status, vehicle_type, payment_method,
              driver_rating, customer_rating, trip_undone_reason
            FROM silver.TransactionFact
            WHERE customer_id = ?
            ORDER BY trip_ts DESC
            """,
            [customer_id],
        ).fetchall()
    else:
        pk = _make_pk(customer_id, booking_id)
        rows = conn.execute(
            """
            SELECT
              transaction_id, customer_id, booking_id, trip_ts,
              booking_value, ride_distance,
              booking_status, vehicle_type, payment_method,
              driver_rating, customer_rating, trip_undone_reason
            FROM silver.TransactionFact
            WHERE transaction_id = ?
            """,
            [pk],
        ).fetchall()

    return [
        TransactionOut(
            transaction_id=r[0],
            customer_id=r[1],
            booking_id=r[2],
            trip_ts=r[3],
            booking_value=r[4],
            ride_distance=r[5],
            booking_status=r[6],
            vehicle_type=r[7],
            payment_method=r[8],
            driver_rating=r[9],
            customer_rating=r[10],
            trip_undone_reason=r[11],
        )
        for r in rows
    ]


@router.patch("/transactions", response_model=TransactionOut)
def update_transaction(
    payload: TransactionUpdate,
    request: Request,
    customer_id: str = Query(..., min_length=1),
    booking_id: str = Query(..., min_length=1),
):
    """
    UPDATE rules:
    - customer_id + booking_id are mandatory
    - at least one updatable field must be provided
    - booking_id and customer_id cannot change
    - enforce business logic (completed must have price & distance; completed has no undone reason)
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided for update.")

    db = request.app.state.db
    conn = db.get_connection()
    settings = request.app.state.settings

    pk = f"{customer_id}|{booking_id}"

    existing = conn.execute(
        """
        SELECT
          transaction_id, customer_id, booking_id, trip_ts,
          booking_value, ride_distance,
          booking_status, vehicle_type, payment_method,
          driver_rating, customer_rating, trip_undone_reason
        FROM silver.TransactionFact
        WHERE transaction_id = ?
        """,
        [pk],
    ).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    # Build "next state" for validation + derived fields
    next_booking_status = update_data.get("booking_status", existing[6])
    next_ride_distance = update_data.get("ride_distance", existing[5])
    next_trip_undone_reason = update_data.get("trip_undone_reason", existing[11])

    # booking_value is derived from distance * constant (always recompute if distance changes)
    next_booking_value = existing[4]
    if "ride_distance" in update_data:
        next_booking_value = float(next_ride_distance) * float(settings.rate_per_distance)

    _validate_business_rules(
        booking_status=next_booking_status,
        ride_distance=next_ride_distance,
        booking_value=next_booking_value,
        trip_undone_reason=next_trip_undone_reason,
    )

    # If status becomes Completed, also force booking_value to match policy (distance * constant)
    if next_booking_status == "Completed":
        next_booking_value = float(next_ride_distance) * float(settings.rate_per_distance)

    # Apply updates (explicit list so we stay safe)
    set_clauses = []
    params: list[Any] = []

    def set_col(col: str, val: Any):
        set_clauses.append(f"{col} = ?")
        params.append(val)

    if "trip_ts" in update_data:
        set_col("trip_ts", update_data["trip_ts"])
    if "booking_status" in update_data:
        set_col("booking_status", next_booking_status)
    if "vehicle_type" in update_data:
        set_col("vehicle_type", update_data["vehicle_type"])
    if "payment_method" in update_data:
        set_col("payment_method", update_data["payment_method"])
    if "ride_distance" in update_data:
        set_col("ride_distance", next_ride_distance)
        set_col("booking_value", next_booking_value)  # derived
    if "driver_rating" in update_data:
        set_col("driver_rating", update_data["driver_rating"])
    if "customer_rating" in update_data:
        set_col("customer_rating", update_data["customer_rating"])
    if "trip_undone_reason" in update_data:
        set_col("trip_undone_reason", next_trip_undone_reason)

    if not set_clauses:
        raise HTTPException(status_code=422, detail="No valid updatable fields provided.")

    params.append(pk)

    try:
        conn.execute(
            f"""
            UPDATE silver.TransactionFact
            SET {", ".join(set_clauses)}
            WHERE transaction_id = ?
            """,
            params,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

    row = conn.execute(
        """
        SELECT
          transaction_id, customer_id, booking_id, trip_ts,
          booking_value, ride_distance,
          booking_status, vehicle_type, payment_method,
          driver_rating, customer_rating, trip_undone_reason
        FROM silver.TransactionFact
        WHERE transaction_id = ?
        """,
        [pk],
    ).fetchone()

    return TransactionOut(
        transaction_id=row[0],
        customer_id=row[1],
        booking_id=row[2],
        trip_ts=row[3],
        booking_value=row[4],
        ride_distance=row[5],
        booking_status=row[6],
        vehicle_type=row[7],
        payment_method=row[8],
        driver_rating=row[9],
        customer_rating=row[10],
        trip_undone_reason=row[11],
    )



@router.delete("/transactions", response_model=DeleteResult)
def delete_transactions(
    request: Request,
    customer_id: Optional[str] = Query(default=None),
    booking_id: Optional[str] = Query(default=None),
):
    """
    DELETE rules mirror READ:
    - customer-only => delete all for customer
    - both => delete one
    - booking-only invalid
    - both None invalid
    """
    if customer_id is None and booking_id is None:
        raise HTTPException(status_code=422, detail="Provide customer_id, or (customer_id + booking_id).")
    if customer_id is None and booking_id is not None:
        raise HTTPException(status_code=422, detail="booking_id alone is not valid. Provide customer_id as well.")

    db = request.app.state.db
    conn = db.get_connection()

    if booking_id is None:
        # count first
        cnt = conn.execute(
            "SELECT count(*) FROM silver.TransactionFact WHERE customer_id = ?",
            [customer_id],
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM silver.TransactionFact WHERE customer_id = ?",
            [customer_id],
        )
        return DeleteResult(deleted=int(cnt))

    pk = f"{customer_id}|{booking_id}"
    cnt = conn.execute(
        "SELECT count(*) FROM silver.TransactionFact WHERE transaction_id = ?",
        [pk],
    ).fetchone()[0]
    conn.execute(
        "DELETE FROM silver.TransactionFact WHERE transaction_id = ?",
        [pk],
    )
    return DeleteResult(deleted=int(cnt))
