import os
import subprocess
import shutil
import requests

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")

# Common LibreOffice paths on macOS / Linux
SOFFICE_PATHS = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    shutil.which("soffice") or "",
]


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Converts a DOCX file to PDF.

    Tries three methods in order:
      1. Gotenberg API  (Docker-based, if running)
      2. LibreOffice     (headless CLI — best Arabic/RTL support)
      3. docx2pdf        (macOS Word wrapper, if Word is installed)

    Returns True if successful, False otherwise.
    """
    if not os.path.exists(docx_path):
        return False

    # ── Method 1: Gotenberg ──────────────────────────────────────────────
    if _try_gotenberg(docx_path, pdf_path):
        return True

    # ── Method 2: LibreOffice headless ───────────────────────────────────
    if _try_libreoffice(docx_path, pdf_path):
        return True

    # ── Method 3: docx2pdf (needs MS Word installed) ─────────────────────
    if _try_docx2pdf(docx_path, pdf_path):
        return True

    print("All PDF conversion methods failed.")
    return False


def _try_gotenberg(docx_path, pdf_path):
    """Attempt conversion via the Gotenberg HTTP API."""
    endpoint = f"{GOTENBERG_URL}/forms/libreoffice/convert"
    try:
        with open(docx_path, "rb") as f:
            files = {"files": (os.path.basename(docx_path), f)}
            response = requests.post(endpoint, files=files, timeout=30)

        if response.status_code == 200:
            with open(pdf_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            print(f"Gotenberg error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Gotenberg unavailable, trying local conversion…")
        return False


def _find_soffice():
    """Locate the LibreOffice soffice binary."""
    for path in SOFFICE_PATHS:
        if path and os.path.isfile(path):
            return path
    return None


def _try_libreoffice(docx_path, pdf_path):
    """Attempt conversion using LibreOffice in headless mode."""
    soffice = _find_soffice()
    if not soffice:
        print("LibreOffice not found on this system.")
        return False

    try:
        # LibreOffice outputs the PDF into --outdir with the same stem name
        out_dir = os.path.dirname(pdf_path) or "."
        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", out_dir,
                docx_path,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"LibreOffice error: {result.stderr}")
            return False

        # LibreOffice names the output after the input file's stem
        stem = os.path.splitext(os.path.basename(docx_path))[0]
        lo_output = os.path.join(out_dir, f"{stem}.pdf")

        if os.path.exists(lo_output):
            # Move to the expected path if different
            if os.path.abspath(lo_output) != os.path.abspath(pdf_path):
                shutil.move(lo_output, pdf_path)
            return True

        print("LibreOffice ran but the output PDF was not found.")
        return False
    except Exception as e:
        print(f"LibreOffice conversion failed: {e}")
        return False


def _try_docx2pdf(docx_path, pdf_path):
    """Attempt conversion using the docx2pdf library (macOS / Windows)."""
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return os.path.exists(pdf_path)
    except Exception as e:
        print(f"docx2pdf conversion failed: {e}")
        return False
