import os
import subprocess
import shutil
import requests

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "").rstrip("/")

# Common LibreOffice paths on macOS / Linux — only relevant for local dev,
# never present on Vercel's serverless runtime.
SOFFICE_PATHS = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    shutil.which("soffice") or "",
]

# Detect whether we're running as a Vercel serverless function.
IS_SERVERLESS = bool(os.environ.get("VERCEL"))


def convert_docx_to_pdf(docx_path, pdf_path):
    """
    Converts a DOCX file to PDF.

    On Vercel (serverless): only Gotenberg can work — there is no writable
    filesystem for a LibreOffice install and no Word/COM available for
    docx2pdf. GOTENBERG_URL must point to a reachable, hosted Gotenberg
    instance (e.g. deployed via Railway/Render/Fly.io).

    Locally (dev machine): falls back to a local LibreOffice install if
    Gotenberg isn't configured, since that's often already installed.

    Returns True if successful, False otherwise.
    """
    if not os.path.exists(docx_path):
        print(f"DOCX not found at {docx_path}")
        return False

    if not GOTENBERG_URL:
        print(
            "GOTENBERG_URL is not set. Set it to a hosted Gotenberg instance "
            "(e.g. https://your-gotenberg.up.railway.app) via Vercel env vars."
        )
    elif _try_gotenberg(docx_path, pdf_path):
        return True

    # Local-dev-only fallback. On Vercel this always fails fast since no
    # soffice binary exists in the serverless filesystem.
    if not IS_SERVERLESS and _try_libreoffice(docx_path, pdf_path):
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
    except requests.exceptions.RequestException as e:
        print(f"Gotenberg unreachable at {GOTENBERG_URL}: {e}")
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