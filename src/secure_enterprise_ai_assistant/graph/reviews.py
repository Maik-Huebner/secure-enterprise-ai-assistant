"""Pending human approvals of decision briefs (four-eyes principle)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ReviewRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    case_id: str
    requested_by: str
    requested_at: str
    status: Literal["pending", "approved", "rejected"] = "pending"
    reviewed_by: str | None = None
    reviewed_at: str | None = None


class ReviewStore:
    """Small JSON index of review threads; the draft itself lives in the graph checkpoint."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, ReviewRecord]:
        if not self.path.is_file():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {item["thread_id"]: ReviewRecord.model_validate(item) for item in payload}

    def _save(self, records: dict[str, ReviewRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([record.model_dump() for record in records.values()], indent=2),
            encoding="utf-8",
        )

    def open(self, thread_id: str, case_id: str, requested_by: str) -> ReviewRecord:
        record = ReviewRecord(
            thread_id=thread_id,
            case_id=case_id,
            requested_by=requested_by,
            requested_at=datetime.now(tz=UTC).isoformat(),
        )
        with self._lock:
            records = self._load()
            records[thread_id] = record
            self._save(records)
        return record

    def get(self, thread_id: str) -> ReviewRecord | None:
        return self._load().get(thread_id)

    def pending(self) -> list[ReviewRecord]:
        return [record for record in self._load().values() if record.status == "pending"]

    def close(self, thread_id: str, approved: bool, reviewer: str) -> ReviewRecord:
        with self._lock:
            records = self._load()
            record = records[thread_id].model_copy(
                update={
                    "status": "approved" if approved else "rejected",
                    "reviewed_by": reviewer,
                    "reviewed_at": datetime.now(tz=UTC).isoformat(),
                }
            )
            records[thread_id] = record
            self._save(records)
        return record
