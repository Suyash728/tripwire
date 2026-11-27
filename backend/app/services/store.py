"""Run persistence. In-memory by default; Supabase (with Row Level Security) when configured AND the
caller is signed in.

SupabaseRunStore is used only when SUPABASE_URL + SUPABASE_PUBLISHABLE_KEY (legacy name:
SUPABASE_ANON_KEY) are set and the request carries `Authorization: Bearer <supabase user JWT>`.
Each request gets its own client that sends that JWT, so every query runs as the user and RLS
decides what it may touch.
The secret / service_role key is never used here: it bypasses RLS.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from typing import Any, Protocol

TABLE = "runs"


class RunStore(Protocol):
    name: str

    def create(self, run_id: str, text: str) -> None: ...
    def update(self, run_id: str, *, status: str, output: dict[str, Any] | None = None) -> None: ...
    def get(self, run_id: str) -> dict[str, Any] | None: ...


class MemoryRunStore:
    """Process-local store (the template's original behaviour). Lost on restart."""

    name = "memory"

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create(self, run_id: str, text: str) -> None:
        with self._lock:
            self._rows[run_id] = {"id": run_id, "input": text, "status": "pending", "output": None}

    def update(self, run_id: str, *, status: str, output: dict[str, Any] | None = None) -> None:
        with self._lock:
            row = self._rows.setdefault(run_id, {"id": run_id, "input": "", "output": None})
            row["status"] = status
            if output is not None:
                row["output"] = output

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._rows.get(run_id)
            return dict(row) if row else None


def _default_client_factory(url: str, key: str, jwt: str) -> Any:
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    options = SyncClientOptions(
        headers={"Authorization": f"Bearer {jwt}"},
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(url, key, options=options)


class SupabaseRunStore:
    """Writes to public.runs as the signed-in user (see supabase/migrations/*_runs.sql)."""

    name = "supabase"

    def __init__(
        self,
        url: str,
        key: str,
        jwt: str,
        client_factory: Callable[[str, str, str], Any] = _default_client_factory,
    ) -> None:
        self._client = client_factory(url, key, jwt)

    def create(self, run_id: str, text: str) -> None:
        # user_id defaults to auth.uid() in the table, so it always matches the JWT's subject.
        row = {"id": run_id, "input": text, "status": "pending"}
        self._client.table(TABLE).insert(row).execute()

    def update(self, run_id: str, *, status: str, output: dict[str, Any] | None = None) -> None:
        values: dict[str, Any] = {"status": status}
        if output is not None:
            values["output"] = output
        self._client.table(TABLE).update(values).eq("id", run_id).execute()

    def get(self, run_id: str) -> dict[str, Any] | None:
        res = self._client.table(TABLE).select("*").eq("id", run_id).maybe_single().execute()
        return res.data if res is not None else None


MEMORY = MemoryRunStore()


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return token.strip() or None


def supabase_settings() -> tuple[str, str] | None:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY") or os.environ.get("SUPABASE_ANON_KEY") or ""
    key = key.strip()
    return (url, key) if url and key else None


def select_store(
    authorization: str | None,
    client_factory: Callable[[str, str, str], Any] | None = None,
) -> RunStore:
    """Supabase only when configured AND the caller sent a user JWT; otherwise in-memory."""
    settings, token = supabase_settings(), bearer_token(authorization)
    if settings is None or token is None:
        return MEMORY
    factory = client_factory or _default_client_factory
    return SupabaseRunStore(*settings, token, client_factory=factory)
