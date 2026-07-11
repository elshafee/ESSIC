"""
app.py — Office Document Numbering System
Flask entry point: routes, file handling, database operations.
"""

import os
import sys
from datetime import datetime
from flask import Flask, render_template, request, redirect,url_for, flash, send_from_directory, abort

from werkzeug.utils import secure_filename

# Allow imports from project root
sys.path.insert(0, os.path.dirname(__file__))

from models import db, Document
from services.numbering import get_next_serial, build_full_code
from services.word_editor import replace_placeholder

# ─── App Configuration ────────────────────────────────────────────────────────

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER   = os.path.join(BASE_DIR, "uploads")
GENERATED_FOLDER = os.path.join(BASE_DIR, "generated")
ALLOWED_EXT     = {"docx"}

app = Flask(__name__)
app.secret_key = "essic-doc-numbering-secret-2026"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'documents.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GENERATED_FOLDER"] = GENERATED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB limit

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

db.init_app(app)

with app.app_context():
    db.create_all()

# ─── Helpers ─────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def index():
    """Upload page — user uploads a .docx template and gets a numbered document."""
    if request.method == "POST":
        file = request.files.get("docx_file")

        if not file or file.filename == "":
            flash("Please select a Word document (.docx) to upload.", "warning")
            return redirect(url_for("index"))

        if not allowed_file(file.filename):
            flash("Only .docx files are accepted.", "danger")
            return redirect(url_for("index"))

        # Save uploaded file
        original_name = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, original_name)
        file.save(upload_path)

        # Generate document number
        now = datetime.now()
        month, year = now.month, now.year
        serial = get_next_serial(month, year)
        full_code = build_full_code(serial, month, year)

        # Process Word document
        stem = original_name.rsplit(".", 1)[0]
        generated_name = f"{stem}__{full_code.replace(' ', '_')}.docx"
        generated_path = os.path.join(GENERATED_FOLDER, generated_name)

        try:
            replace_placeholder(upload_path, generated_path, full_code)
        except Exception as e:
            flash(f"Error processing document: {e}", "danger")
            return redirect(url_for("index"))

        # Save record to database
        doc = Document(
            serial_number=serial,
            full_code=full_code,
            month=month,
            year=year,
            filename=original_name,
            generated_filename=generated_name,
        )
        db.session.add(doc)
        db.session.commit()

        flash(f"Document number <strong>{full_code}</strong> generated successfully!", "success")
        return redirect(url_for("documents"))

    # Build preview code for the current moment
    now_preview = datetime.now()
    next_serial = get_next_serial(now_preview.month, now_preview.year)
    preview_code = build_full_code(next_serial, now_preview.month, now_preview.year)
    return render_template("index.html", preview_code=preview_code)


@app.route("/documents")
def documents():
    """Documents history page — list all processed documents."""
    all_docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("documents.html", documents=all_docs, now=datetime.now())


@app.route("/download/<int:doc_id>")
def download(doc_id):
    """Download the generated (numbered) document."""
    doc = Document.query.get_or_404(doc_id)
    if not doc.generated_filename:
        abort(404)
    return send_from_directory(
        GENERATED_FOLDER,
        doc.generated_filename,
        as_attachment=True,
        download_name=doc.generated_filename,
    )


@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
def edit(doc_id):
    """Edit a document's serial number and regenerate its full code."""
    doc = Document.query.get_or_404(doc_id)

    if request.method == "POST":
        try:
            new_serial = int(request.form["serial_number"])
            if new_serial < 1:
                raise ValueError
        except (ValueError, KeyError):
            flash("Serial number must be a positive integer.", "danger")
            return redirect(url_for("edit", doc_id=doc_id))

        # Regenerate full code with new serial
        new_full_code = build_full_code(new_serial, doc.month, doc.year)

        # Re-process the Word document with the new code
        upload_path = os.path.join(UPLOAD_FOLDER, doc.filename)
        if not os.path.exists(upload_path):
            flash("Original uploaded file not found. Cannot regenerate document.", "danger")
            return redirect(url_for("documents"))

        # Remove old generated file
        if doc.generated_filename:
            old_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
            if os.path.exists(old_path):
                os.remove(old_path)

        stem = doc.filename.rsplit(".", 1)[0]
        new_generated_name = f"{stem}__{new_full_code.replace(' ', '_')}.docx"
        new_generated_path = os.path.join(GENERATED_FOLDER, new_generated_name)

        try:
            replace_placeholder(upload_path, new_generated_path, new_full_code)
        except Exception as e:
            flash(f"Error regenerating document: {e}", "danger")
            return redirect(url_for("documents"))

        doc.serial_number = new_serial
        doc.full_code = new_full_code
        doc.generated_filename = new_generated_name
        db.session.commit()

        flash(f"Document updated to <strong>{new_full_code}</strong>.", "success")
        return redirect(url_for("documents"))

    return render_template("edit.html", doc=doc)


@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete(doc_id):
    """Delete a document record and its generated file."""
    doc = Document.query.get_or_404(doc_id)

    # Remove generated file from disk
    if doc.generated_filename:
        gen_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(gen_path):
            os.remove(gen_path)

    db.session.delete(doc)
    db.session.commit()

    flash("Document record deleted.", "info")
    return redirect(url_for("documents"))


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5010)
