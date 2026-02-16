from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request

from .models import TextQueryRequest, TextQueryResponse

router = APIRouter(tags=["textquery"])


@router.post("/textquery", response_model=TextQueryResponse)
def run_text_query(payload: TextQueryRequest, request: Request):
    """
    Endpoint: /api/v1/textquery (after router is included with prefix=/api/v1)

    Rules enforced:
    - Only DB-related questions allowed (LLM classifier behavior + hard constraints).
    - Only SELECT allowed (hard guardrails).
    - Must include LIMIT 10 (hard guardrails).
    - Always returns <= 10 rows.
    """
    db = request.app.state.db
    conn = db.get_connection()

    try:
        sql, _ = request.app.ttss.text_to_sql(payload.text)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        cursor = conn.execute(sql)
        cols = [d[0] for d in cursor.description] if cursor.description else []
        data = cursor.fetchmany(10)  # belt-and-suspenders; SQL already has LIMIT 10
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL execution failed: {str(e)}")

    rows: List[Dict[str, Any]] = [dict(zip(cols, r)) for r in data]

    return TextQueryResponse(sql=sql, columns=cols, rows=rows)
