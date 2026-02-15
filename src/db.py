from __future__ import annotations

import duckdb
from typing import Optional


class DuckDB:

    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def connect(self) -> None:
        if self.conn is None:
            self.conn = duckdb.connect(self.path, read_only=False)
            self.conn.execute("SET timezone='UTC';")

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        if self.conn is None:
            raise RuntimeError("DuckDB connection not initialized.")
        return self.conn
