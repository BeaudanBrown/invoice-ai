from __future__ import annotations

from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import quote

from ..config import RuntimeConfig
from ..erp.schemas import ToolResponse
from .models import UIArtifactView, UIReviewView, UISummaryView, UITurnResponse


@dataclass(frozen=True)
class ArtifactLinkBuilder:
    config: RuntimeConfig

    def build(self, *, kind: str, path: str) -> UIArtifactView:
        file_path = Path(path)
        label = _artifact_label(kind)
        if not file_path.exists() or not file_path.is_file():
            return UIArtifactView(
                kind=kind,
                label=label,
                file_name=file_path.name or kind,
                available=False,
            )

        relative_path = self._relative_state_path(file_path)
        if relative_path is None:
            return UIArtifactView(
                kind=kind,
                label=label,
                file_name=file_path.name,
                content_type=_content_type(file_path),
                available=False,
            )

        encoded = quote(relative_path.as_posix(), safe="/")
        return UIArtifactView(
            kind=kind,
            label=label,
            file_name=file_path.name,
            content_type=_content_type(file_path),
            url=f"/api/artifacts/file/{encoded}",
            download_url=f"/api/artifacts/file/{encoded}?download=1",
            available=True,
        )

    def _relative_state_path(self, path: Path) -> Path | None:
        resolved = path.resolve()
        if not any(_is_relative_to(resolved, root.resolve()) for root in _allowed_roots(self.config)):
            return None
        try:
            return resolved.relative_to(self.config.paths.state_dir.resolve())
        except ValueError:
            return None


def present_turn_response(
    *,
    config: RuntimeConfig,
    response: ToolResponse,
) -> UITurnResponse:
    builder = ArtifactLinkBuilder(config)
    stage = str(response.data.get("stage") or response.status)
    artifacts = tuple(
        builder.build(kind=str(item.get("kind", "artifact")), path=str(item.get("path", "")))
        for item in response.data.get("artifacts", [])
        if isinstance(item, dict) and item.get("path")
    )
    reviews = tuple(_collect_reviews(builder=builder, response=response))
    current_artifact = _pick_current_artifact(artifacts)
    return UITurnResponse(
        request_id=response.request_id,
        status=str(response.status),
        stage=stage,
        summary=UISummaryView(
            text=_summary_text(response=response, stage=stage),
            stage=stage,
            status=str(response.status),
        ),
        conversation_state=dict(response.data.get("conversation_state", {})),
        artifacts=artifacts,
        current_artifact=current_artifact,
        reviews=reviews,
        erp_refs=tuple(
            item
            for item in response.data.get("erp_refs", [])
            if isinstance(item, dict)
        ),
        warnings=tuple(str(item) for item in response.warnings),
        errors=tuple(error.as_dict() for error in response.errors),
    )


def _collect_reviews(
    *,
    builder: ArtifactLinkBuilder,
    response: ToolResponse,
) -> list[UIReviewView]:
    reviews: list[UIReviewView] = []
    approval = response.approval
    if approval is not None:
        review_artifacts = []
        for kind, path in approval.artifacts.as_dict().items():
            if path is None:
                continue
            review_artifacts.append(builder.build(kind=kind, path=path))
        reviews.append(
            UIReviewView(
                review_id=approval.approval_id,
                kind=approval.action,
                status="pending",
                summary=approval.summary,
                actions=("accept", "reject"),
                artifacts=tuple(review_artifacts),
            )
        )

    for item in response.data.get("memory_reviews", []):
        if not isinstance(item, dict):
            continue
        approval_payload = item.get("approval")
        if not isinstance(approval_payload, dict):
            continue
        review_artifacts = []
        for artifact in item.get("artifacts", []):
            if not isinstance(artifact, dict) or not artifact.get("path"):
                continue
            review_artifacts.append(
                builder.build(
                    kind=str(artifact.get("kind", "artifact")),
                    path=str(artifact["path"]),
                )
            )
        review_id = str(approval_payload.get("approval_id", ""))
        if not review_id:
            continue
        if any(existing.review_id == review_id for existing in reviews):
            continue
        reviews.append(
            UIReviewView(
                review_id=review_id,
                kind=str(approval_payload.get("action", "review")),
                status="pending",
                summary=str(approval_payload.get("summary", "Review required")),
                actions=("accept", "reject"),
                artifacts=tuple(review_artifacts),
            )
        )
    return reviews


def _summary_text(*, response: ToolResponse, stage: str) -> str:
    if response.status == "approval_required" and response.approval is not None:
        return response.approval.summary
    if response.errors:
        return response.errors[0].message

    summaries = {
        "quotation_draft_created": "Created a draft quotation and generated a preview PDF.",
        "quotation_draft_revised": "Updated the current quotation and generated a new preview PDF.",
        "sales_invoice_draft_created": "Created a draft sales invoice and generated a preview PDF.",
        "sales_invoice_draft_created_from_quotation": "Created a draft sales invoice from the current quote and generated a preview PDF.",
        "sales_invoice_draft_revised": "Updated the current sales invoice and generated a new preview PDF.",
        "purchase_invoice_draft_created": "Created a draft purchase invoice from the supplier document.",
        "extract_review": "I need review before I can trust the extracted supplier document details.",
        "ingest_review": "I need review before I can write this supplier document into ERPNext.",
        "review_queue_listed": "Loaded the current review queue.",
        "review_detail_loaded": "Loaded the requested review.",
        "review_accepted": "Accepted the review and applied the update.",
        "review_rejected": "Rejected the review.",
        "memory_review": "Prepared the memory update for review.",
    }
    if stage in summaries:
        return summaries[stage]

    request_kind = str(response.data.get("request_kind", "request"))
    if response.status == "success":
        return f"Completed the {request_kind.replace('_', ' ')} request."
    return f"The {request_kind.replace('_', ' ')} request needs attention."


def _pick_current_artifact(
    artifacts: tuple[UIArtifactView, ...],
) -> UIArtifactView | None:
    for preferred_kind in (
        "sales_invoice_preview_pdf",
        "quote_preview_pdf",
        "summary_markdown_path",
        "summary_markdown",
    ):
        for artifact in artifacts:
            if artifact.kind == preferred_kind and artifact.available:
                return artifact
    for artifact in artifacts:
        if artifact.available:
            return artifact
    return None


def _artifact_label(kind: str) -> str:
    labels = {
        "quote_preview_pdf": "Quote PDF",
        "sales_invoice_preview_pdf": "Invoice PDF",
        "summary_markdown": "Review Summary",
        "summary_markdown_path": "Review Summary",
        "request_json": "Request JSON",
        "request_json_path": "Request JSON",
        "diff_json": "Review Diff",
        "diff_json_path": "Review Diff",
        "ingest_record_dir": "Ingest Record",
    }
    return labels.get(kind, kind.replace("_", " ").title())


def _content_type(path: Path) -> str | None:
    guessed, _ = guess_type(str(path))
    return guessed


def _allowed_roots(config: RuntimeConfig) -> tuple[Path, ...]:
    return (
        config.paths.approvals_dir,
        config.paths.artifacts_dir,
        config.paths.documents_dir,
        config.paths.ingest_dir,
        config.paths.memory_dir,
        config.paths.revisions_dir,
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
