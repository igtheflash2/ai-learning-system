"""Extract text from scanned/image-based PDFs using OCR (rapidocr-onnxruntime + PyMuPDF)."""

import re
import time
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from rapidocr_onnxruntime import RapidOCR

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output_md")


def sanitize_filename(name: str) -> str:
    """Remove or replace characters unsafe for filenames."""
    name = re.sub(r"[\\/:*?\"<>|]", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "untitled"


def ocr_page(page: fitz.Page, engine: RapidOCR, dpi: int = 100) -> str:
    """Render a PDF page to an image and run OCR, returning extracted text."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    # Convert RGBA pixmap to BGR numpy array (what OpenCV / rapidocr expects)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    elif pix.n == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif pix.n == 1:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    result, elapse = engine(img)
    if result is None:
        return ""

    # result is list of [bbox, text, score]
    lines = [item[1] for item in result]
    return "\n".join(lines)


def ocr_pdf(pdf_path: Path, engine: RapidOCR) -> str:
    """Open a PDF, OCR every page, return full markdown body."""
    doc = fitz.open(str(pdf_path))
    pages_text = []
    total = len(doc)

    for page_num in range(total):
        print(f"  Page {page_num+1}/{total}...", end=" ", flush=True)
        t0 = time.time()
        text = ocr_page(doc[page_num], engine)
        elapsed = time.time() - t0
        print(f"({elapsed:.1f}s, {len(text)} chars)", flush=True)
        if text.strip():
            pages_text.append(text)

    doc.close()
    return "\n\n---\n\n".join(pages_text)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in input/.")
        return

    print("Initializing RapidOCR engine (lightweight, ONNX-based)...")
    engine = RapidOCR()
    print("Engine ready.\n")

    total_start = time.time()
    for pdf_path in pdf_files:
        file_start = time.time()
        print(f"Processing: {pdf_path.name}")

        text = ocr_pdf(pdf_path, engine)
        if not text.strip():
            print(f"  Warning: No text extracted from {pdf_path.name}")
            text = "[No extractable text content.]"

        md_name = sanitize_filename(pdf_path.stem + ".md")
        md_path = OUTPUT_DIR / md_name
        md_content = f"# {pdf_path.stem}\n\n{text}\n"
        md_path.write_text(md_content, encoding="utf-8")

        elapsed = time.time() - file_start
        print(f"  Saved ({elapsed:.1f}s): {md_path}")

    total_elapsed = time.time() - total_start
    print(f"\nDone. {len(pdf_files)} PDF(s) converted in {total_elapsed:.1f}s -> {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
