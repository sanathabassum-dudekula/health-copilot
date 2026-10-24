
import os
from pathlib import Path

import pymupdf as fitz
from PIL import Image, ImageOps

from ..db import SessionLocal
from ..models import Document
from ..storage import download_file

MAX_PAGES, DPI, MAX_EDGE = 10, 170, 2048
MIN_PAGE_TEXT = 200
TEMP_ROOT = Path("/tmp/curamind")


def prepare_file(src: Path, mime: str, out: Path) -> tuple[list[str], str]:
    """Create temporary page images and extract the PDF text layer."""
    out.mkdir(parents=True, exist_ok=True)
    paths, text = [], []

    if mime == "application/pdf":
        with fitz.open(src) as pdf:
            for i, page in enumerate(pdf):
                if i >= MAX_PAGES:
                    break

                page_text = page.get_text()
                text.append(page_text)

                if len(page_text.strip()) < MIN_PAGE_TEXT:
                    image_path = out / f"page{i}.jpg"
                    page.get_pixmap(dpi=DPI).save(str(image_path))
                    paths.append(str(image_path))
    else:
        with Image.open(src) as original:
            img = ImageOps.exif_transpose(original).convert("RGB")
            img.thumbnail((MAX_EDGE, MAX_EDGE))
            image_path = out / "page0.jpg"
            img.save(image_path, quality=85)
            paths.append(str(image_path))

    return paths, "\n".join(text).strip()


def prepare(state):
    document_id = state["document_id"]
    work_dir = TEMP_ROOT / str(document_id)
    work_dir.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as db:
        doc = db.get(Document, document_id)
        if doc is None or not doc.file_path:
            raise FileNotFoundError(
                f"Original file for document {document_id} was not found"
            )
        key = doc.file_path
        mime = doc.mime

    suffix = Path(key).suffix or ".bin"
    local_file = work_dir / f"original{suffix}"

    download_file(key, str(local_file))
    paths, text = prepare_file(local_file, mime, work_dir)

    return {
        "page_paths": paths,
        "text_layer": text,
    }
