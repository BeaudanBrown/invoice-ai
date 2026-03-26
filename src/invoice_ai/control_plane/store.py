from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import uuid

from ..config import RuntimeConfig
from ..erp.schemas import ToolRequest, ToolResponse
from .models import (
    ArtifactRecord,
    IdempotencyKeyRecord,
    IngestIndexRecord,
    JobEventRecord,
    JobRecord,
    JobStatus,
    MemorySuggestionIndexRecord,
    RequestLifecycleStatus,
    RequestRecord,
    RequestSource,
    ReviewActionRecord,
    ReviewRecord,
    ReviewStatus,
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_hash(payload: dict[str, object]) -> str:
    return sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return sha256(path.read_bytes()).hexdigest()


class ControlPlaneStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @classmethod
    def from_runtime_config(cls, config: RuntimeConfig) -> "ControlPlaneStore":
        return cls(config.paths.control_plane_db_path)

    def ensure(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    operator_id TEXT,
                    dry_run INTEGER NOT NULL,
                    request_body_hash TEXT NOT NULL,
                    request_body_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    finished_at TEXT,
                    response_body_hash TEXT,
                    error_count INTEGER NOT NULL,
                    warning_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    job_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    summary_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS job_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    result_fingerprint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retention_marker TEXT,
                    PRIMARY KEY (key, scope)
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    request_id TEXT,
                    review_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_json TEXT NOT NULL,
                    target_summary TEXT,
                    artifact_dir TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_actions (
                    action_id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    operator_id TEXT,
                    note TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    parent_kind TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    request_id TEXT,
                    artifact_kind TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_hash TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ingest_index (
                    ingest_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    source_fingerprint TEXT,
                    supplier_hint TEXT,
                    external_invoice_reference TEXT,
                    linked_review_id TEXT,
                    linked_erp_doctype TEXT,
                    linked_erp_name TEXT,
                    record_dir TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS memory_suggestions (
                    suggestion_id TEXT PRIMARY KEY,
                    scope TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    linked_review_id TEXT,
                    current_document_path TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    @contextmanager
    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _request_record_from_row(row: sqlite3.Row) -> RequestRecord:
        return RequestRecord(
            request_id=str(row["request_id"]),
            source=RequestSource(str(row["source"])),
            tool_name=str(row["tool_name"]),
            operator_id=None if row["operator_id"] is None else str(row["operator_id"]),
            dry_run=bool(row["dry_run"]),
            request_body_hash=str(row["request_body_hash"]),
            request_body=json.loads(str(row["request_body_json"])),
            status=RequestLifecycleStatus(str(row["status"])),
            created_at=str(row["created_at"]),
            finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
            response_body_hash=(
                None
                if row["response_body_hash"] is None
                else str(row["response_body_hash"])
            ),
            error_count=int(row["error_count"]),
            warning_count=int(row["warning_count"]),
        )

    @staticmethod
    def _job_record_from_row(row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=str(row["job_id"]),
            request_id=str(row["request_id"]),
            job_kind=str(row["job_kind"]),
            status=JobStatus(str(row["status"])),
            started_at=str(row["started_at"]),
            finished_at=None if row["finished_at"] is None else str(row["finished_at"]),
            summary=json.loads(str(row["summary_json"])),
        )

    @staticmethod
    def _job_event_record_from_row(row: sqlite3.Row) -> JobEventRecord:
        return JobEventRecord(
            event_id=str(row["event_id"]),
            job_id=str(row["job_id"]),
            request_id=str(row["request_id"]),
            event_type=str(row["event_type"]),
            payload=json.loads(str(row["payload_json"])),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _review_record_from_row(row: sqlite3.Row) -> ReviewRecord:
        return ReviewRecord(
            review_id=str(row["review_id"]),
            request_id=None if row["request_id"] is None else str(row["request_id"]),
            review_kind=str(row["review_kind"]),
            status=ReviewStatus(str(row["status"])),
            target=json.loads(str(row["target_json"])),
            target_summary=(
                None if row["target_summary"] is None else str(row["target_summary"])
            ),
            artifact_dir=None if row["artifact_dir"] is None else str(row["artifact_dir"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _review_action_record_from_row(row: sqlite3.Row) -> ReviewActionRecord:
        return ReviewActionRecord(
            action_id=str(row["action_id"]),
            review_id=str(row["review_id"]),
            action_type=str(row["action_type"]),
            operator_id=None if row["operator_id"] is None else str(row["operator_id"]),
            note=None if row["note"] is None else str(row["note"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _artifact_record_from_row(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=str(row["artifact_id"]),
            parent_kind=str(row["parent_kind"]),
            parent_id=str(row["parent_id"]),
            request_id=None if row["request_id"] is None else str(row["request_id"]),
            artifact_kind=str(row["artifact_kind"]),
            path=str(row["path"]),
            content_hash=None if row["content_hash"] is None else str(row["content_hash"]),
            created_at=str(row["created_at"]),
        )

    def record_request_start(
        self,
        *,
        request: ToolRequest,
        source: RequestSource,
        operator_id: str | None = None,
    ) -> None:
        record = RequestRecord(
            request_id=request.request_id,
            source=source,
            tool_name=request.tool_name,
            operator_id=operator_id,
            dry_run=request.dry_run,
            request_body_hash=_json_hash(request.as_dict()),
            request_body=request.as_dict(),
            status=RequestLifecycleStatus.RUNNING,
            created_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO requests (
                    request_id, source, tool_name, operator_id, dry_run,
                    request_body_hash, request_body_json, status, created_at,
                    finished_at, response_body_hash, error_count, warning_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.request_id,
                    record.source,
                    record.tool_name,
                    record.operator_id,
                    int(record.dry_run),
                    record.request_body_hash,
                    json.dumps(record.request_body, sort_keys=True),
                    record.status,
                    record.created_at,
                    None,
                    None,
                    0,
                    0,
                ),
            )

    def record_request_finish(self, *, response: ToolResponse) -> None:
        payload = response.as_dict()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE requests
                SET status = ?, finished_at = ?, response_body_hash = ?, error_count = ?, warning_count = ?
                WHERE request_id = ?
                """,
                (
                    RequestLifecycleStatus(response.status),
                    _utcnow(),
                    _json_hash(payload),
                    len(response.errors),
                    len(response.warnings),
                    response.request_id,
                ),
            )

    def record_request_internal_error(self, *, request_id: str, message: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE requests
                SET status = ?, finished_at = ?, error_count = COALESCE(error_count, 0) + 1
                WHERE request_id = ?
                """,
                (RequestLifecycleStatus.INTERNAL_ERROR, _utcnow(), request_id),
            )
            connection.execute(
                """
                INSERT INTO job_events (event_id, job_id, request_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    f"event-{uuid.uuid4().hex}",
                    request_id,
                    request_id,
                    "internal_error",
                    json.dumps({"message": message}, sort_keys=True),
                    _utcnow(),
                ),
            )

    def start_job(self, *, request_id: str, job_kind: str, summary: dict[str, object] | None = None) -> str:
        job_id = request_id
        record = JobRecord(
            job_id=job_id,
            request_id=request_id,
            job_kind=job_kind,
            status=JobStatus.RUNNING,
            started_at=_utcnow(),
            summary=dict(summary or {}),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO jobs (
                    job_id, request_id, job_kind, status, started_at, finished_at, summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.request_id,
                    record.job_kind,
                    record.status,
                    record.started_at,
                    None,
                    json.dumps(record.summary, sort_keys=True),
                ),
            )
        return job_id

    def record_job_event(
        self,
        *,
        job_id: str,
        request_id: str,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        record = JobEventRecord(
            event_id=f"event-{uuid.uuid4().hex}",
            job_id=job_id,
            request_id=request_id,
            event_type=event_type,
            payload=dict(payload or {}),
            created_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_events (event_id, job_id, request_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id,
                    record.job_id,
                    record.request_id,
                    record.event_type,
                    json.dumps(record.payload, sort_keys=True),
                    record.created_at,
                ),
            )

    def finish_job(
        self,
        *,
        job_id: str,
        status: JobStatus,
        summary: dict[str, object] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, finished_at = ?, summary_json = ?
                WHERE job_id = ?
                """,
                (
                    status,
                    _utcnow(),
                    json.dumps(dict(summary or {}), sort_keys=True),
                    job_id,
                ),
            )

    def record_idempotency_result(
        self,
        *,
        key: str,
        scope: str,
        request_id: str,
        result_fingerprint: str,
        retention_marker: str | None = None,
    ) -> None:
        record = IdempotencyKeyRecord(
            key=key,
            scope=scope,
            request_id=request_id,
            result_fingerprint=result_fingerprint,
            created_at=_utcnow(),
            retention_marker=retention_marker,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO idempotency_keys (
                    key, scope, request_id, result_fingerprint, created_at, retention_marker
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.key,
                    record.scope,
                    record.request_id,
                    record.result_fingerprint,
                    record.created_at,
                    record.retention_marker,
                ),
            )

    def record_review(
        self,
        *,
        review_id: str,
        request_id: str | None,
        review_kind: str,
        status: ReviewStatus,
        target: dict[str, object],
        target_summary: str | None = None,
        artifact_dir: str | None = None,
    ) -> None:
        existing_created_at = _utcnow()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT created_at FROM reviews WHERE review_id = ?",
                (review_id,),
            ).fetchone()
            if row is not None:
                existing_created_at = str(row[0])
            record = ReviewRecord(
                review_id=review_id,
                request_id=request_id,
                review_kind=review_kind,
                status=status,
                target=target,
                target_summary=target_summary,
                artifact_dir=artifact_dir,
                created_at=existing_created_at,
                updated_at=_utcnow(),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO reviews (
                    review_id, request_id, review_kind, status, target_json, target_summary,
                    artifact_dir, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.review_id,
                    record.request_id,
                    record.review_kind,
                    record.status,
                    json.dumps(record.target, sort_keys=True),
                    record.target_summary,
                    record.artifact_dir,
                    record.created_at,
                    record.updated_at,
                ),
            )

    def record_review_action(
        self,
        *,
        review_id: str,
        action_type: str,
        operator_id: str | None = None,
        note: str | None = None,
    ) -> None:
        record = ReviewActionRecord(
            action_id=f"review-action-{uuid.uuid4().hex}",
            review_id=review_id,
            action_type=action_type,
            operator_id=operator_id,
            note=note,
            created_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO review_actions (action_id, review_id, action_type, operator_id, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.action_id,
                    record.review_id,
                    record.action_type,
                    record.operator_id,
                    record.note,
                    record.created_at,
                ),
            )

    def record_artifact(
        self,
        *,
        parent_kind: str,
        parent_id: str,
        artifact_kind: str,
        path: Path,
        request_id: str | None = None,
    ) -> None:
        record = ArtifactRecord(
            artifact_id=f"artifact-{uuid.uuid4().hex}",
            parent_kind=parent_kind,
            parent_id=parent_id,
            request_id=request_id,
            artifact_kind=artifact_kind,
            path=str(path),
            content_hash=_file_hash(path),
            created_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, parent_kind, parent_id, request_id, artifact_kind, path, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.parent_kind,
                    record.parent_id,
                    record.request_id,
                    record.artifact_kind,
                    record.path,
                    record.content_hash,
                    record.created_at,
                ),
            )

    def upsert_ingest_index(
        self,
        *,
        ingest_id: str,
        request_id: str,
        source_fingerprint: str | None = None,
        supplier_hint: str | None = None,
        external_invoice_reference: str | None = None,
        linked_review_id: str | None = None,
        linked_erp_doctype: str | None = None,
        linked_erp_name: str | None = None,
        record_dir: str | None = None,
    ) -> None:
        record = IngestIndexRecord(
            ingest_id=ingest_id,
            request_id=request_id,
            source_fingerprint=source_fingerprint,
            supplier_hint=supplier_hint,
            external_invoice_reference=external_invoice_reference,
            linked_review_id=linked_review_id,
            linked_erp_doctype=linked_erp_doctype,
            linked_erp_name=linked_erp_name,
            record_dir=record_dir,
            updated_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO ingest_index (
                    ingest_id, request_id, source_fingerprint, supplier_hint, external_invoice_reference,
                    linked_review_id, linked_erp_doctype, linked_erp_name, record_dir, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.ingest_id,
                    record.request_id,
                    record.source_fingerprint,
                    record.supplier_hint,
                    record.external_invoice_reference,
                    record.linked_review_id,
                    record.linked_erp_doctype,
                    record.linked_erp_name,
                    record.record_dir,
                    record.updated_at,
                ),
            )

    def find_duplicate_ingests(
        self,
        *,
        source_fingerprint: str | None = None,
        supplier_hint: str | None = None,
        external_invoice_reference: str | None = None,
        exclude_request_id: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, str | None]]:
        clauses: list[str] = []
        params: list[object] = []

        if source_fingerprint is not None:
            clauses.append("source_fingerprint = ?")
            params.append(source_fingerprint)
        if supplier_hint is not None and external_invoice_reference is not None:
            clauses.append("(supplier_hint = ? AND external_invoice_reference = ?)")
            params.extend([supplier_hint, external_invoice_reference])

        if not clauses:
            return []

        query = """
            SELECT ingest_id, request_id, source_fingerprint, supplier_hint,
                   external_invoice_reference, linked_review_id, linked_erp_doctype,
                   linked_erp_name, record_dir, updated_at
            FROM ingest_index
            WHERE ({where_clause})
        """
        if exclude_request_id is not None:
            query += " AND request_id != ?"
            params.append(exclude_request_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                query.format(where_clause=" OR ".join(clauses)),
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_ingest_index(self, *, ingest_id: str) -> dict[str, str | None] | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT ingest_id, request_id, source_fingerprint, supplier_hint,
                       external_invoice_reference, linked_review_id, linked_erp_doctype,
                       linked_erp_name, record_dir, updated_at
                FROM ingest_index
                WHERE ingest_id = ?
                """,
                (ingest_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def upsert_memory_suggestion(
        self,
        *,
        suggestion_id: str,
        scope: str,
        slug: str,
        status: ReviewStatus,
        linked_review_id: str | None = None,
        current_document_path: str | None = None,
    ) -> None:
        record = MemorySuggestionIndexRecord(
            suggestion_id=suggestion_id,
            scope=scope,
            slug=slug,
            status=status,
            linked_review_id=linked_review_id,
            current_document_path=current_document_path,
            updated_at=_utcnow(),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_suggestions (
                    suggestion_id, scope, slug, status, linked_review_id, current_document_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.suggestion_id,
                    record.scope,
                    record.slug,
                    record.status,
                    record.linked_review_id,
                    record.current_document_path,
                    record.updated_at,
                ),
            )

    def list_requests(
        self,
        *,
        limit: int = 50,
        status: RequestLifecycleStatus | None = None,
        tool_name: str | None = None,
        operator_id: str | None = None,
    ) -> tuple[RequestRecord, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(str(status))
        if tool_name is not None:
            clauses.append("tool_name = ?")
            params.append(tool_name)
        if operator_id is not None:
            clauses.append("operator_id = ?")
            params.append(operator_id)

        query = """
            SELECT request_id, source, tool_name, operator_id, dry_run, request_body_hash,
                   request_body_json, status, created_at, finished_at, response_body_hash,
                   error_count, warning_count
            FROM requests
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._request_record_from_row(row) for row in rows)

    def get_request(self, *, request_id: str) -> RequestRecord | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT request_id, source, tool_name, operator_id, dry_run, request_body_hash,
                       request_body_json, status, created_at, finished_at, response_body_hash,
                       error_count, warning_count
                FROM requests
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return None if row is None else self._request_record_from_row(row)

    def list_jobs(
        self,
        *,
        limit: int = 50,
        status: JobStatus | None = None,
        job_kind: str | None = None,
        request_id: str | None = None,
    ) -> tuple[JobRecord, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(str(status))
        if job_kind is not None:
            clauses.append("job_kind = ?")
            params.append(job_kind)
        if request_id is not None:
            clauses.append("request_id = ?")
            params.append(request_id)
        query = """
            SELECT job_id, request_id, job_kind, status, started_at, finished_at, summary_json
            FROM jobs
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._job_record_from_row(row) for row in rows)

    def get_job(self, *, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT job_id, request_id, job_kind, status, started_at, finished_at, summary_json
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()
        return None if row is None else self._job_record_from_row(row)

    def list_job_events(self, *, job_id: str, limit: int = 200) -> tuple[JobEventRecord, ...]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT event_id, job_id, request_id, event_type, payload_json, created_at
                FROM job_events
                WHERE job_id = ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (job_id, limit),
            ).fetchall()
        return tuple(self._job_event_record_from_row(row) for row in rows)

    def list_reviews(
        self,
        *,
        limit: int = 50,
        status: ReviewStatus | None = None,
        review_kind: str | None = None,
    ) -> tuple[ReviewRecord, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(str(status))
        if review_kind is not None:
            clauses.append("review_kind = ?")
            params.append(review_kind)
        query = """
            SELECT review_id, request_id, review_kind, status, target_json, target_summary,
                   artifact_dir, created_at, updated_at
            FROM reviews
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._review_record_from_row(row) for row in rows)

    def get_review(self, *, review_id: str) -> ReviewRecord | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT review_id, request_id, review_kind, status, target_json, target_summary,
                       artifact_dir, created_at, updated_at
                FROM reviews
                WHERE review_id = ?
                """,
                (review_id,),
            ).fetchone()
        return None if row is None else self._review_record_from_row(row)

    def list_review_actions(self, *, review_id: str) -> tuple[ReviewActionRecord, ...]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT action_id, review_id, action_type, operator_id, note, created_at
                FROM review_actions
                WHERE review_id = ?
                ORDER BY created_at ASC
                """,
                (review_id,),
            ).fetchall()
        return tuple(self._review_action_record_from_row(row) for row in rows)

    def list_artifacts(
        self,
        *,
        parent_kind: str | None = None,
        parent_id: str | None = None,
        request_id: str | None = None,
    ) -> tuple[ArtifactRecord, ...]:
        clauses: list[str] = []
        params: list[object] = []
        if parent_kind is not None:
            clauses.append("parent_kind = ?")
            params.append(parent_kind)
        if parent_id is not None:
            clauses.append("parent_id = ?")
            params.append(parent_id)
        if request_id is not None:
            clauses.append("request_id = ?")
            params.append(request_id)
        query = """
            SELECT artifact_id, parent_kind, parent_id, request_id, artifact_kind,
                   path, content_hash, created_at
            FROM artifacts
        """
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._artifact_record_from_row(row) for row in rows)
