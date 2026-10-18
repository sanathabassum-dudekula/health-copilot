
import base64
import mimetypes
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage

from ..config import settings
from .llm import invoke_with_retry, structured
from .prepare import prepare_file
from .schemas import DocumentClassification


CLASSIFICATION_PROMPT = """
Determine whether this upload is a genuine medical or clinical document
intended to record a person's health, care, examination, or treatment.

Examples of medical documents:
- Prescriptions and medication instructions
- Laboratory and diagnostic reports, including imaging reports
- Discharge summaries and clinical notes
- Fracture, injury, and other hospital reports
- Antenatal, pregnancy, reproductive, and women's-health records
- Other genuine patient medical records, even if their exact type is unfamiliar

Examples of non-medical documents:
- Electricity, water, phone, or internet bills
- Shopping receipts, restaurant bills, and ordinary invoices
- Bank statements, utility payment receipts, and unrelated forms
- Blank pages or documents with no identifiable medical content

Rules:
- Examine the actual visible content and extracted text, not just the filename.
- A hospital name or medical-looking logo alone does not make a document medical.
- Do not require a document to match a predefined medical category.
- If evidence is insufficient or the document is ambiguous, set confidence low.
- Do not extract diagnoses or give medical advice during this screening.

Extracted PDF text (may be empty):
{text_layer}
"""


def classify_document(data: bytes, mime: str) -> DocumentClassification:
    """Screen uploaded content before creating its permanent record."""
    with tempfile.TemporaryDirectory(prefix="trinexa-screen-") as temp:
        root = Path(temp)
        suffix = ".pdf" if mime == "application/pdf" else (
            ".png" if mime == "image/png" else ".jpg"
        )
        source = root / f"upload{suffix}"
        source.write_bytes(data)

        page_paths, text_layer = prepare_file(
            source, mime, root / "pages", render_all_pages=True
        )

        content = [{
            "type": "text",
            "text": CLASSIFICATION_PROMPT.format(
                text_layer=text_layer or "(no readable PDF text)"
            ),
        }]

        for page_path in page_paths:
            with open(page_path, "rb") as image_file:
                encoded = base64.b64encode(
                    image_file.read()
                ).decode("ascii")

            content.append({
                "type": "image",
                "base64": encoded,
                "mime_type": mimetypes.guess_type(page_path)[0]
                or "image/jpeg",
            })

        result = invoke_with_retry(
            structured(settings.VISION_MODEL, DocumentClassification),
            [HumanMessage(content=content)],
        )

        if result is None:
            raise ValueError("Document screening returned no result")

        return result
