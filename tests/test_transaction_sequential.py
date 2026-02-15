from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

import httpx
import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class TestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    test_url: str = Field(..., alias="TEST_URL")


def _base_url() -> str:
    s = TestSettings()
    return s.test_url.rstrip("/")


def _endpoint(path: str) -> str:
    return f"{_base_url()}{path}"


API_PREFIX = "/api/v1"
TXN_PATH = f"{API_PREFIX}/transactions"


def _assert_rating_range(val: Optional[float]) -> None:
    if val is None:
        return
    assert 0 <= val <= 5


def _assert_transaction_shape(t: Dict[str, Any]) -> None:
    assert "transaction_id" in t
    assert "customer_id" in t
    assert "booking_id" in t
    assert "trip_ts" in t

    assert "booking_value" in t
    assert "ride_distance" in t

    assert "booking_status" in t
    assert "vehicle_type" in t
    assert "payment_method" in t

    _assert_rating_range(t.get("driver_rating"))
    _assert_rating_range(t.get("customer_rating"))

    # PK rule
    assert t["transaction_id"] == f'{t["customer_id"]}|{t["booking_id"]}'


@pytest.mark.order(1)
def test_transactions_crud_sequence():
    """
    Sequential test:
    Create, Read, Delete, Read, Create, Update, Read
    """
    customer_id = f"CID{uuid.uuid4().hex[:10].upper()}"

    with httpx.Client(timeout=20.0) as client:
        # --- 1) CREATE ---
        create_payload = {
            "customer_id": customer_id,
            "ride_distance": 12.5,
        }
        r = client.post(_endpoint(TXN_PATH), json=create_payload)
        assert r.status_code == 201, r.text
        created_1 = r.json()
        _assert_transaction_shape(created_1)

        assert created_1["customer_id"] == customer_id
        assert created_1["booking_id"].startswith("CNR")
        assert created_1["booking_status"] == "Completed"
        assert created_1["vehicle_type"] == "Auto"
        assert created_1["payment_method"] == "cash"
        assert created_1["ride_distance"] == 12.5
        assert created_1.get("trip_undone_reason") is None  # completed should have none

        booking_id_1 = created_1["booking_id"]

        # --- 2) READ (customer only -> multiple ok) ---
        r = client.get(_endpoint(TXN_PATH), params={"customer_id": customer_id})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) >= 1
        for row in rows:
            _assert_transaction_shape(row)
            assert row["customer_id"] == customer_id

        # --- 2b) READ (booking only -> INVALID) ---
        r = client.get(_endpoint(TXN_PATH), params={"booking_id": booking_id_1})
        assert r.status_code == 422, r.text  # per your rule

        # --- 2c) READ (both -> single ok) ---
        r = client.get(_endpoint(TXN_PATH), params={"customer_id": customer_id, "booking_id": booking_id_1})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) in (0, 1)
        if rows:
            _assert_transaction_shape(rows[0])
            assert rows[0]["booking_id"] == booking_id_1

        # --- 3) DELETE (both -> delete single) ---
        r = client.delete(_endpoint(TXN_PATH), params={"customer_id": customer_id, "booking_id": booking_id_1})
        assert r.status_code == 200, r.text
        deleted = r.json()
        assert "deleted" in deleted
        assert deleted["deleted"] in (0, 1)  # if already gone, still acceptable

        # --- 4) READ (both) should be empty now ---
        r = client.get(_endpoint(TXN_PATH), params={"customer_id": customer_id, "booking_id": booking_id_1})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows == []

        # --- 5) CREATE again (for update scenario) ---
        create_payload2 = {
            "customer_id": customer_id,
            "ride_distance": 7.0,
            "booking_status": "Completed",
            "payment_method": "cash",
            "vehicle_type": "Auto",
            # try ratings
            "driver_rating": 4.5,
        }
        r = client.post(_endpoint(TXN_PATH), json=create_payload2)
        assert r.status_code == 201, r.text
        created_2 = r.json()
        _assert_transaction_shape(created_2)
        booking_id_2 = created_2["booking_id"]
        assert created_2["driver_rating"] == 4.5

        # --- 6) UPDATE (requires BOTH ids, and at least 1 field) ---
        # Update distance -> should recompute booking_value on server side
        update_payload = {
            "ride_distance": 10.0,
            "payment_method": "card",  # also update a string field
            "customer_rating": 5.0,
        }
        r = client.patch(
            _endpoint(TXN_PATH),
            params={"customer_id": customer_id, "booking_id": booking_id_2},
            json=update_payload,
        )
        assert r.status_code == 200, r.text
        updated = r.json()
        _assert_transaction_shape(updated)
        assert updated["booking_id"] == booking_id_2
        assert updated["ride_distance"] == 10.0
        assert updated["payment_method"] == "card"
        assert updated["customer_rating"] == 5.0
        assert updated["booking_status"] == "Completed"
        assert updated.get("trip_undone_reason") is None

        # --- 6b) UPDATE with NO FIELDS should be invalid ---
        r = client.patch(
            _endpoint(TXN_PATH),
            params={"customer_id": customer_id, "booking_id": booking_id_2},
            json={},
        )
        assert r.status_code == 422, r.text

        # --- 7) READ (both) confirm updated state ---
        r = client.get(_endpoint(TXN_PATH), params={"customer_id": customer_id, "booking_id": booking_id_2})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list)
        assert len(rows) == 1
        got = rows[0]
        _assert_transaction_shape(got)
        assert got["ride_distance"] == 10.0
        assert got["payment_method"] == "card"
        assert got["customer_rating"] == 5.0

        # Optional cleanup: delete everything for that customer
        r = client.delete(_endpoint(TXN_PATH), params={"customer_id": customer_id})
        assert r.status_code == 200, r.text
