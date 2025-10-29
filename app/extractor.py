import io
import subprocess
import tempfile
from typing import Tuple

from pdfminer.high_level import extract_text
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfparser import PDFSyntaxError

def pdf_to_text_bytes(pdf_bytes: bytes) -> Tuple[str, bool]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf_bytes)
            f.flush()
            text = extract_text(f.name) or ""
        if text.strip():
            return text.strip(), False
    except (PDFSyntaxError, PDFTextExtractionNotAllowed, Exception):
        pass

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["pdftoppm", "-r", "300", "-png", "-", f"{tmpdir}/page"],
                input=pdf_bytes,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            # OCR sur chaque page
            import os, glob
            pages = sorted(glob.glob(f"{tmpdir}/page-*.png"))
            ocr_texts = []
            for img in pages:
                res = subprocess.run(
                    ["tesseract", img, "stdout", "-l", "fra+eng"],
                    capture_output=True,
                    check=True,
                )
                ocr_texts.append(res.stdout.decode("utf-8", errors="ignore"))
            full = "\n".join(ocr_texts).strip()
            return full, True
    except Exception:
        return "", True

