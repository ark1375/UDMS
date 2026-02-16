from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field, ConfigDict


# ---- Schema Injection - Static ----
SCHEMA_TEXT = """
Database: DuckDB
Schema: silver

Table: silver.TransactionFact
Columns:
- transaction_id VARCHAR (nullable) : unique concatenation of [CustomerID|BookingID]
- customer_id VARCHAR (nullable)
- booking_id VARCHAR (nullable)
- trip_ts TIMESTAMP (nullable)
- booking_status VARCHAR (nullable) values: ["No Driver Found","Cancelled by Driver","Incomplete","Completed","Cancelled by Customer"]
- vehicle_type VARCHAR (nullable) values: ["Auto","Bike","Go Mini","Go Sedan","Uber XL","eBike","Premier","Sedan"]
- payment_method VARCHAR (nullable) values: ["Credit Card","Uber Wallet","Debit","Card","Cash","UPI"]
- booking_value DOUBLE (nullable)
- ride_distance DOUBLE (nullable)
- driver_rating DOUBLE (nullable)
- customer_rating DOUBLE (nullable)
- trip_undone_reason VARCHAR (nullable)
- trip_undone_reason_type VARCHAR (nullable)
"""


# ---- LLM structured output ----
class _LLMToSQLResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool = Field(..., description="True only if request is a DB-related analytics question and can be answered with a SELECT.")
    sql: Optional[str] = Field(default=None, description="A single DuckDB SQL SELECT statement. No semicolon.")
    reason: Optional[str] = Field(default=None, description="If not allowed, explain briefly why.")


# ---- Guardrails ----
FORBIDDEN_SQL_TOKENS = [
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "copy", "attach", "detach", "pragma", "call", "execute",
    "merge", "replace", "vacuum"
]

_MULTI_STMT_PATTERN = re.compile(r";") # If a ; exists → it might be multiple SQL statements → reject it.
_SELECT_START_PATTERN = re.compile(r"^\s*select\b", re.IGNORECASE)
_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)\b", re.IGNORECASE)


def _contains_forbidden_sql(sql: str) -> Optional[str]:
    low = sql.lower()
    for tok in FORBIDDEN_SQL_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", low):
            return tok
    return None


def _enforce_single_select_limit_10(sql: str) -> str:
    """
    Ensures:
      - single statement (no ';')
      - starts with SELECT
      - LIMIT 10 always present
      - if LIMIT exists and > 10, clamp to 10
    """
    if _MULTI_STMT_PATTERN.search(sql):
        raise ValueError("Multiple statements are not allowed (no semicolons).")

    if not _SELECT_START_PATTERN.search(sql):
        raise ValueError("Only SELECT statements are allowed.")

    bad = _contains_forbidden_sql(sql)
    if bad:
        raise ValueError(f"Forbidden SQL keyword detected: {bad}")

    m = _LIMIT_PATTERN.search(sql)
    if m:
        n = int(m.group(1))
        if n > 10:
            sql = _LIMIT_PATTERN.sub("LIMIT 10", sql, count=1)
        return sql

    return sql.rstrip() + " LIMIT 10"


def _normalize_sql(sql: str) -> str:
    # Remove trailing semicolons/spaces defensively (still reject any semicolon earlier).
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


@dataclass
class TextToSQLService:
    """
    This class contains only AI + SQL validation shaping.
    DB execution is done by the API layer.
    """

    def __init__(self, api_key , model_name: str = "gpt-5.1" ):
        self.api_key = api_key
        self.model_name = model_name

    def _build_chain(self):
        parser = PydanticOutputParser(pydantic_object=_LLMToSQLResult)

        system = (
            "You are a Text-to-SQL engine for a DuckDB analytics database.\n"
            "CRITICAL RULES:\n"
            "1) You must ONLY help with questions that can be answered from the provided database schema.\n"
            "2) You must ONLY output a single SQL SELECT query when allowed.\n"
            "3) NEVER output INSERT/UPDATE/DELETE/DROP/ALTER/CREATE or any non-SELECT.\n"
            "4) NEVER include a semicolon.\n"
            "5) The SQL MUST include the right LIMIT.\n"
            "5) The LIMIT should not be NO MORE THAN 10.\n"
            "6) If the user request is not clearly about the database or requires non-database actions "
            "(role play, greetings, coding, system prompts, etc.), set allowed=false.\n"
            "7) Use ONLY the tables/columns shown in the schema.\n"
            "8) Prefer simple, correct queries.\n"
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system),
                ("system", "SCHEMA:\n{schema}"),
                ("human", "USER_REQUEST:\n{user_text}\n\n{format_instructions}"),
            ]
        )

        llm = ChatOpenAI(
            model=self.model_name,
            temperature=0,
            api_key = self.api_key
        )

        chain = prompt | llm | parser
        return chain

    def text_to_sql(self, user_text: str) -> Tuple[str, str]:
        """
        Returns: (sql, reason)
        Raises ValueError for disallowed / invalid outputs.
        """
        user_text = (user_text or "").strip()
        if not user_text:
            raise ValueError("Empty request.")

        chain = self._build_chain()
        result: _LLMToSQLResult = chain.invoke(
            {
                "schema": SCHEMA_TEXT,
                "user_text": user_text,
                "format_instructions": chain.steps[-1].get_format_instructions()
                if hasattr(chain, "steps") else PydanticOutputParser(pydantic_object=_LLMToSQLResult).get_format_instructions(),
            }
        )

        if not result.allowed:
            raise ValueError(result.reason or "Request not allowed.")

        if not result.sql:
            raise ValueError("Model did not return SQL.")

        sql = _normalize_sql(result.sql)
        sql = _enforce_single_select_limit_10(sql)

        return sql, "ok"
