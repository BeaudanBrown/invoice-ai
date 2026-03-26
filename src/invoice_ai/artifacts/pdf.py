from __future__ import annotations

from pathlib import Path

from .models import QuotePreview, SalesInvoicePreview


class QuotePreviewRenderer:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def render(self, preview: QuotePreview) -> Path:
        target_dir = self.artifacts_dir / "quotes" / preview.draft_key
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / "preview.pdf"
        output_path.write_bytes(self._pdf_bytes(preview))
        return output_path

    def _pdf_bytes(self, preview: QuotePreview) -> bytes:
        text_lines = [
            f"Quote Preview: {preview.title}",
            f"Customer: {preview.customer}",
            f"Company: {preview.company}",
            "",
        ]
        for item in preview.items:
            text_lines.append(
                f"{item.description or item.item_code} | qty {item.qty:g} | "
                f"rate {item.rate:.2f} | amount {item.amount:.2f}"
            )
        text_lines.extend(
            [
                "",
                f"Total ({preview.currency}): {preview.total:.2f}",
            ]
        )
        if preview.notes:
            text_lines.extend(["", f"Notes: {preview.notes}"])

        stream_lines = ["BT", "/F1 12 Tf", "50 760 Td", "14 TL"]
        first = True
        for line in text_lines:
            escaped = _pdf_escape(line)
            if first:
                stream_lines.append(f"({escaped}) Tj")
                first = False
            else:
                stream_lines.append(f"T* ({escaped}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("utf-8")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode("utf-8")
            + stream
            + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        return _build_pdf(objects)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(objects: list[bytes]) -> bytes:
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    cursor = len(chunks[0])
    for index, obj in enumerate(objects, start=1):
        entry = f"{index} 0 obj\n".encode("utf-8") + obj + b"\nendobj\n"
        offsets.append(cursor)
        chunks.append(entry)
        cursor += len(entry)

    xref_offset = cursor
    xref_lines = [f"xref\n0 {len(offsets)}\n", "0000000000 65535 f \n"]
    xref_lines.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("utf-8")

    chunks.append("".join(xref_lines).encode("utf-8"))
    chunks.append(trailer)
    return b"".join(chunks)


class SalesInvoicePreviewRenderer:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def render(self, preview: SalesInvoicePreview) -> Path:
        target_dir = self.artifacts_dir / "sales_invoices" / preview.draft_key
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / "preview.pdf"
        output_path.write_bytes(self._pdf_bytes(preview))
        return output_path

    def _pdf_bytes(self, preview: SalesInvoicePreview) -> bytes:
        text_lines = [
            f"Sales Invoice Preview: {preview.title}",
            f"Customer: {preview.customer}",
            f"Company: {preview.company}",
            "",
        ]
        for item in preview.items:
            text_lines.append(
                f"{item.description or item.item_code} | qty {item.qty:g} | "
                f"rate {item.rate:.2f} | amount {item.amount:.2f}"
            )
        text_lines.extend(
            [
                "",
                f"Total ({preview.currency}): {preview.total:.2f}",
            ]
        )
        if preview.notes:
            text_lines.extend(["", f"Notes: {preview.notes}"])

        stream_lines = ["BT", "/F1 12 Tf", "50 760 Td", "14 TL"]
        first = True
        for line in text_lines:
            escaped = _pdf_escape(line)
            if first:
                stream_lines.append(f"({escaped}) Tj")
                first = False
            else:
                stream_lines.append(f"T* ({escaped}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("utf-8")

        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode("utf-8")
            + stream
            + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]

        return _build_pdf(objects)
