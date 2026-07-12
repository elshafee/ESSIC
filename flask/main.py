import base64
import io
import os
import sys
from datetime import datetime
from functools import wraps

import pyotp
import qrcode
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, abort, session, \
    jsonify
from sqlalchemy import true
from werkzeug.utils import secure_filename

# Allow imports from project root
sys.path.insert(0, os.path.dirname(__file__))

from models import db, Document, User
from services.numbering import get_next_serial, build_full_code
from services.word_editor import replace_placeholder

# Load environment variables
load_dotenv()

# ─── App Configuration ────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
GENERATED_FOLDER = os.path.join(DATA_DIR, "generated")
ALLOWED_EXT = {"docx"}

app = Flask(__name__)
app.secret_key = "essic-doc-numbering-secret-2026"
supabase_url = os.environ.get("SUPABASE_DB_URL")
if supabase_url:
    if supabase_url.startswith("postgres://"):
        supabase_url = supabase_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif supabase_url.startswith("postgresql://"):
        supabase_url = supabase_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = supabase_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(DATA_DIR, 'documents.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["GENERATED_FOLDER"] = GENERATED_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB limit

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(GENERATED_FOLDER, exist_ok=True)

_admin_raw = os.environ.get("ADMIN_EMAILS", "mkhassan@horus.edu.eg,aelshafee@horus.edu.eg")
ADMIN_EMAILS = {e.strip().lower() for e in _admin_raw.split(",") if e.strip()}

# Allowed users — comma-separated emails in .env
_allowed_raw = os.environ.get("ALLOWED_EMAILS", "mkhassan@horus.edu.eg,aelshafee@horus.edu.eg")
ALLOWED_EMAILS = {e.strip().lower() for e in _allowed_raw.split(",") if e.strip()}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.context_processor
def inject_globals():
    is_admin = False
    if 'user' in session:
        user_email = session['user'].get('email', '')
        if user_email in ADMIN_EMAILS:
            is_admin = True
        else:
            user = User.query.filter_by(email=user_email).first()
            if user and user.role == 'admin':
                is_admin = True
    return dict(is_admin=is_admin)


def is_current_user_admin():
    user_email = session.get('user', {}).get('email', '')
    if not user_email: return False
    if user_email in ADMIN_EMAILS:
        return True
    user = User.query.filter_by(email=user_email).first()
    return user and user.role == 'admin'


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_current_user_admin():
            flash("You do not have permission to access this page.", "danger")
            return redirect(url_for('documents'))
        return f(*args, **kwargs)

    return decorated_function


db.init_app(app)

with app.app_context():
    db.create_all()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash("Please enter your email.", "warning")
            return redirect(url_for('login'))

        # Check if user exists in DB
        user = User.query.filter_by(email=email).first()

        if not user and email not in ALLOWED_EMAILS:
            flash("This email address is not authorized to access this system. Please ask an admin to add you.",
                  "danger")
            return redirect(url_for('login'))

        if not user:
            # First time logging in: Create user and generate TOTP secret
            name = email.split('@')[0]
            totp_secret = pyotp.random_base32()
            is_admin = email in ADMIN_EMAILS
            user = User(email=email, name=name, totp_secret=totp_secret, is_setup=False,
                        role='admin' if is_admin else 'user')
            db.session.add(user)
            db.session.commit()

        session['pending_email'] = email

        if not user.is_setup:
            return redirect(url_for('setup'))
        else:
            return redirect(url_for('verify'))

    return render_template('login.html')


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'user' in session:
        return redirect(url_for('index'))

    email = session.get('pending_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user or user.is_setup:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            user.is_setup = True
            db.session.commit()

            session.pop('pending_email', None)
            session['user'] = {'name': user.name, 'email': user.email}
            return redirect(url_for('index'))
        else:
            flash("Invalid code. Please try again.", "danger")

    # Generate QR code URL
    totp_uri = pyotp.totp.TOTP(user.totp_secret).provisioning_uri(name=email, issuer_name="ESSIC Document System")

    # Generate QR code image as base64
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template('setup.html', qr_b64=qr_b64, secret=user.totp_secret, email=email)


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'user' in session:
        return redirect(url_for('index'))

    email = session.get('pending_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user or not user.is_setup:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(code):
            session.pop('pending_email', None)
            session['user'] = {'name': user.name, 'email': user.email}
            return redirect(url_for('index'))
        else:
            flash("Invalid authenticator code. Please try again.", "danger")

    return render_template('verify.html', email=email)


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Upload page — user uploads a .docx template and gets a numbered document, or generates directly from default template."""
    if request.method == "POST":
        action_type = request.form.get("action_type", "upload")

        if action_type == "upload":
            file = request.files.get("docx_file")

            if not file or file.filename == "":
                flash("Please select a Word document (.docx) to upload.", "warning")
                return redirect(url_for("index"))

            if not allowed_file(file.filename):
                flash("Only .docx files are accepted.", "danger")
                return redirect(url_for("index"))

            file_title = request.form.get("file_title", "").strip()

            # Save uploaded file
            original_name = secure_filename(file.filename)
            upload_path = os.path.join(UPLOAD_FOLDER, original_name)
            file.save(upload_path)

        elif action_type == "direct_template":
            file_title = request.form.get("file_title", "Direct Template Report").strip()
            upload_path = os.path.join(BASE_DIR, "template_essic.docx")
            original_name = "template_essic.docx"

            if not os.path.exists(upload_path):
                flash("Default template (template_essic.docx) not found.", "danger")
                return redirect(url_for("index"))
        else:
            flash("Invalid action.", "danger")
            return redirect(url_for("index"))

        # Generate document number
        now = datetime.now()
        month, year = now.month, now.year
        serial = get_next_serial(month, year)
        full_code = build_full_code(serial, month, year)

        # Process Word document
        if action_type == "direct_template":
            timestamp = now.strftime("%Y%md_%H%M%S")
            generated_name = f"Direct_{timestamp}_{full_code.replace(' ', '_')}.docx"
        else:
            generated_name = f"{full_code.replace(' ', '_')}.docx"

        generated_path = os.path.join(GENERATED_FOLDER, generated_name)

        try:
            if action_type == "upload":
                replace_placeholder(upload_path, generated_path, full_code)
            elif action_type == "direct_template":
                from services.word_editor import replace_placeholders
                from services.ai_generator import normalize_recipient

                recipient = request.form.get("recipient", "")
                subject = request.form.get("subject", "")
                holder_name = request.form.get("holder_name", "")
                position = request.form.get("position", "")
                full_body = request.form.get("full_body", "")
                sender = request.form.get("sender", "")
                is_internal = request.form.get("is_internal") == "1"
                manager_is_sender = request.form.get("manager_is_sender") == "1"

                # Determine sender value for template
                sender_value = ""
                sender_top = 'مدير مركز الخدمات الإلكترونية والإبداع العلمي (ESSIC)\u200F'

                # If external OR manager is sender -> sender_value stays empty (manager signature kept)
                # Only if internal AND NOT manager -> employee signature used
                if is_internal and not manager_is_sender and sender:
                    sender_value = f"مقدمه لسيادتكم\n{sender}\u200F"
                    sender_top = f"{sender}\u200F"

                remove_manager = (is_internal and not manager_is_sender)
                replace_placeholders(upload_path, generated_path, {
                    "{{CODE_NUMBER}}": full_code,
                    "{{SEND_TO}}": (normalize_recipient(recipient) + "\u200F") if recipient else "",
                    "{{SUBJECT}}": subject + "\u200F",
                    "{{STACK_HOLDER}}": holder_name + "\u200F",
                    "{{POSITION}}": position + "\u200F",
                    "{{BODY_TEXT}}": full_body + "\u200F",
                    "{{SENDER}}": sender_value,
                    "{{SENDER_TOP}}": sender_top,
                }, remove_manager_sig=remove_manager)

            # Attempt PDF generation
            from services.pdf_converter import convert_docx_to_pdf
            generated_pdf_name = generated_name.replace(".docx", ".pdf")
            generated_pdf_path = os.path.join(GENERATED_FOLDER, generated_pdf_name)
            pdf_success = convert_docx_to_pdf(generated_path, generated_pdf_path)
            if not pdf_success:
                generated_pdf_name = None
        except Exception as e:
            flash(f"Error processing document: {e}", "danger")
            return redirect(url_for("index"))

        user_data = session.get('user', {})
        user_email = user_data.get('email', '')
        is_admin = is_current_user_admin()

        status = 'approved' if is_admin else 'pending'

        if status == 'approved':
            # Upload to OneDrive using the onedrive service
            from services.onedrive import upload_file_to_share
            if os.environ.get("ONEDRIVE_SHARE_URL"):
                success = upload_file_to_share(generated_path, generated_name)
                if generated_pdf_name:
                    upload_file_to_share(generated_pdf_path, generated_pdf_name)
                if success:
                    flash("Document generated and successfully uploaded to OneDrive!", "success")
                else:
                    flash("Document generated locally, but OneDrive upload failed. Please check your credentials.",
                          "warning")
            else:
                flash("Document generated locally. (OneDrive upload not configured.)", "info")
        else:
            flash("Document uploaded successfully. It is pending admin approval.", "info")

        # Save record to database
        doc = Document(serial_number=serial, full_code=full_code, month=month, year=year, filename=original_name,
                       file_title=file_title, generated_filename=generated_name,
                       generated_pdf_filename=generated_pdf_name, username=user_data.get('name', 'Unknown'),
                       email=user_email, status=status)

        if action_type == "direct_template":
            doc.doc_type = "direct"
            doc.sender = request.form.get("sender", "")
            doc.recipient = request.form.get("recipient", "")
            doc.subject = request.form.get("subject", "")
            doc.holder_name = request.form.get("holder_name", "")
            doc.position = request.form.get("position", "")
            doc.is_internal = request.form.get("is_internal") == "1"
            doc.manager_is_sender = request.form.get("manager_is_sender") == "1"
            doc.generated_body = request.form.get("full_body", "")

        db.session.add(doc)
        db.session.commit()

        if status == 'approved':
            flash(f"Document number <strong>{full_code}</strong> generated successfully!", "success")
            return redirect(url_for("documents", auto_download=doc.id))
        return redirect(url_for("documents"))

    # Build preview code for the current moment
    now_preview = datetime.now()
    next_serial = get_next_serial(now_preview.month, now_preview.year)
    preview_code = build_full_code(next_serial, now_preview.month, now_preview.year)
    return render_template("index.html", preview_code=preview_code)


@app.route("/documents")
@login_required
def documents():
    """Documents history page — list all processed documents."""
    user_email = session.get('user', {}).get('email', '')
    is_admin = is_current_user_admin()
    if is_admin:
        all_docs = Document.query.order_by(Document.created_at.desc()).all()
    else:
        all_docs = Document.query.filter_by(email=user_email).order_by(Document.created_at.desc()).all()
    return render_template("documents.html", documents=all_docs, now=datetime.now(), is_admin=is_admin)


@app.route("/download/<int:doc_id>")
@login_required
def download(doc_id):
    """Download the generated (numbered) document."""
    doc = Document.query.get_or_404(doc_id)
    if not doc.generated_filename:
        abort(404)
    return send_from_directory(GENERATED_FOLDER, doc.generated_filename, as_attachment=True,
                               download_name=doc.generated_filename, )


@app.route("/download_pdf/<int:doc_id>")
@login_required
def download_pdf(doc_id):
    """Download the generated PDF document."""
    doc = Document.query.get_or_404(doc_id)
    if not doc.generated_pdf_filename:
        flash("No PDF file available for this document.", "warning")
        return redirect(url_for("documents"))
    return send_from_directory(GENERATED_FOLDER, doc.generated_pdf_filename, as_attachment=True,
                               download_name=doc.generated_pdf_filename, )


@app.route("/preview_document", methods=["POST"])
@login_required
def preview_document():
    action_type = request.form.get("action_type")

    import tempfile
    from services.word_editor import replace_placeholder, replace_placeholders
    from services.ai_generator import normalize_recipient
    from services.pdf_converter import convert_docx_to_pdf
    from flask import send_file, jsonify

    now = datetime.now()
    serial = get_next_serial(now.month, now.year)
    full_code = build_full_code(serial, now.month, now.year)

    temp_dir = tempfile.mkdtemp()
    temp_docx_path = os.path.join(temp_dir, "preview.docx")
    temp_pdf_path = os.path.join(temp_dir, "preview.pdf")

    try:
        if action_type == "upload":
            file = request.files.get("document")
            if not file or file.filename == "":
                return jsonify({"success": False, "error": "No file uploaded"}), 400

            upload_path = os.path.join(temp_dir, "upload.docx")
            file.save(upload_path)
            replace_placeholder(upload_path, temp_docx_path, full_code)

        elif action_type == "direct_template":
            upload_path = os.path.join(BASE_DIR, "template_essic.docx")
            if not os.path.exists(upload_path):
                return jsonify({"success": False, "error": "Template not found"}), 404

            recipient = request.form.get("recipient", "")
            subject = request.form.get("subject", "")
            holder_name = request.form.get("holder_name", "")
            position = request.form.get("position", "")
            full_body = request.form.get("full_body", "")
            sender = request.form.get("sender", "")
            is_internal = request.form.get("is_internal") == "1"
            manager_is_sender = request.form.get("manager_is_sender") == "1"

            sender_value = ""
            sender_top = 'مدير مركز الخدمات الإلكترونية والإبداع العلمي (ESSIC)\u200F'
            if is_internal and not manager_is_sender and sender:
                sender_value = f"مقدمه لسيادتكم\n{sender}\u200F"
                sender_top = f"{sender}\u200F"

            replace_placeholders(upload_path, temp_docx_path, {
                "{{CODE_NUMBER}}": full_code,
                "{{SEND_TO}}": (normalize_recipient(recipient) + "\u200F") if recipient else "",
                "{{SUBJECT}}": subject + "\u200F",
                "{{STACK_HOLDER}}": holder_name + "\u200F",
                "{{POSITION}}": position + "\u200F",
                "{{BODY_TEXT}}": full_body + "\u200F",
                "{{SENDER}}": sender_value,
                "{{SENDER_TOP}}": sender_top,
            }, remove_manager_sig=(is_internal and not manager_is_sender))
        else:
            return jsonify({"success": False, "error": "Invalid action type"}), 400

        pdf_success = convert_docx_to_pdf(temp_docx_path, temp_pdf_path)
        if not pdf_success:
            return jsonify({"success": False, "error": "Failed to generate PDF preview. Is Gotenberg running?"}), 500

        return send_file(temp_pdf_path, mimetype='application/pdf')

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/edit/<int:doc_id>", methods=["GET", "POST"])
@login_required
def edit(doc_id):
    """Edit a document's serial number and regenerate its full code."""
    doc = Document.query.get_or_404(doc_id)

    user_email = session.get('user', {}).get('email', '')
    is_admin = is_current_user_admin()
    if not is_admin and doc.email != user_email:
        flash("You do not have permission to modify this document.", "danger")
        return redirect(url_for("documents"))

    if request.method == "POST":
        try:
            new_serial = int(request.form["serial_number"])
            if new_serial < 1:
                raise ValueError
        except (ValueError, KeyError):
            flash("Serial number must be a positive integer.", "danger")
            return redirect(url_for("edit", doc_id=doc_id))

        full_body = doc.generated_body
        if doc.doc_type == "direct":
            doc.recipient = request.form.get("recipient", doc.recipient)
            doc.subject = request.form.get("subject", doc.subject)
            doc.holder_name = request.form.get("holder_name", doc.holder_name)
            doc.position = request.form.get("position", doc.position)
            doc.sender = request.form.get("sender", doc.sender)
            doc.is_internal = request.form.get("is_internal") == "1"
            doc.manager_is_sender = request.form.get("manager_is_sender") == "1"
            full_body = request.form.get("full_body", doc.generated_body)
            doc.generated_body = full_body

        # Regenerate full code with new serial
        new_full_code = build_full_code(new_serial, doc.month, doc.year)

        if new_serial != doc.serial_number:
            existing = Document.query.filter_by(month=doc.month, year=doc.year, serial_number=new_serial).first()
            if existing:
                flash(f"Serial number {new_serial} is already used for this month. Please choose another.", "danger")
                return redirect(url_for("edit", doc_id=doc_id))

        # Re-process the Word document with the new code
        upload_path = os.path.join(UPLOAD_FOLDER, doc.filename)
        # If it was generated via direct entry and we don't have the uploaded file, fallback to template
        if doc.doc_type == "direct" and not os.path.exists(upload_path):
            upload_path = os.path.join(BASE_DIR, "template_essic.docx")

        if not os.path.exists(upload_path):
            flash("Original uploaded file not found. Cannot regenerate document.", "danger")
            return redirect(url_for("documents"))

        # Remove old generated file
        if doc.generated_filename:
            old_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
            if os.path.exists(old_path):
                os.remove(old_path)

        if doc.generated_pdf_filename:
            old_pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
            if os.path.exists(old_pdf_path):
                os.remove(old_pdf_path)

        stem = doc.filename.rsplit(".", 1)[0]
        new_generated_name = f"{stem}__{new_full_code.replace(' ', '_')}.docx"
        new_generated_path = os.path.join(GENERATED_FOLDER, new_generated_name)

        try:
            if doc.doc_type == "direct":
                from services.word_editor import replace_placeholders
                from services.ai_generator import normalize_recipient

                body_to_use = full_body
                sender_value = ""
                sender_top = 'مدير مركز الخدمات الإلكترونية والإبداع العلمي (ESSIC)\u200F'

                if doc.is_internal and not doc.manager_is_sender and doc.sender:
                    sender_value = f"مقدمه لسيادتكم\n{doc.sender}\u200F"
                    sender_top = f"{doc.sender}\u200F"

                replace_placeholders(upload_path, new_generated_path, {
                    "{{CODE_NUMBER}}": new_full_code,
                    "{{SEND_TO}}": (normalize_recipient(doc.recipient) + "\u200F") if doc.recipient else "",
                    "{{SUBJECT}}": doc.subject + "\u200F",
                    "{{STACK_HOLDER}}": (doc.holder_name or "") + "\u200F",
                    "{{POSITION}}": (doc.position or "") + "\u200F",
                    "{{BODY_TEXT}}": (body_to_use or "") + "\u200F",
                    "{{SENDER}}": sender_value,
                    "{{SENDER_TOP}}": sender_top,
                }, remove_manager_sig=(doc.is_internal and not doc.manager_is_sender))
            else:
                from services.word_editor import replace_placeholder
                replace_placeholder(upload_path, new_generated_path, new_full_code)

            from services.pdf_converter import convert_docx_to_pdf
            new_generated_pdf_name = new_generated_name.replace(".docx", ".pdf")
            new_generated_pdf_path = os.path.join(GENERATED_FOLDER, new_generated_pdf_name)
            pdf_success = convert_docx_to_pdf(new_generated_path, new_generated_pdf_path)
            if pdf_success:
                doc.generated_pdf_filename = new_generated_pdf_name
            else:
                doc.generated_pdf_filename = None
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
@login_required
def delete(doc_id):
    """Delete a document record and its generated file."""
    doc = Document.query.get_or_404(doc_id)

    user_email = session.get('user', {}).get('email', '')
    is_admin = is_current_user_admin()
    if not is_admin and doc.email != user_email:
        flash("You do not have permission to delete this document.", "danger")
        return redirect(url_for("documents"))

    # Remove generated files from disk
    if doc.generated_filename:
        gen_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(gen_path):
            os.remove(gen_path)

    if doc.generated_pdf_filename:
        gen_pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
        if os.path.exists(gen_pdf_path):
            os.remove(gen_pdf_path)

    db.session.delete(doc)
    db.session.commit()

    flash("Document record deleted.", "info")
    return redirect(url_for("documents"))


@app.route("/approve/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def approve(doc_id):
    """Approve a pending document and upload to OneDrive."""

    doc = Document.query.get_or_404(doc_id)
    if doc.status == 'approved':
        flash("Document is already approved.", "info")
        return redirect(url_for("documents"))

    doc.status = 'approved'

    # If the document is missing a PDF, try to generate one now
    if doc.generated_filename and not doc.generated_pdf_filename:
        generated_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        if os.path.exists(generated_path):
            from services.pdf_converter import convert_docx_to_pdf
            pdf_name = doc.generated_filename.replace(".docx", ".pdf")
            pdf_path = os.path.join(GENERATED_FOLDER, pdf_name)
            if convert_docx_to_pdf(generated_path, pdf_path):
                doc.generated_pdf_filename = pdf_name

    # Trigger OneDrive upload
    if doc.generated_filename:
        generated_path = os.path.join(GENERATED_FOLDER, doc.generated_filename)
        from services.onedrive import upload_file_to_share
        if os.environ.get("ONEDRIVE_SHARE_URL") and os.path.exists(generated_path):
            success = upload_file_to_share(generated_path, doc.generated_filename)
            # Also upload the PDF if available
            if doc.generated_pdf_filename:
                pdf_path = os.path.join(GENERATED_FOLDER, doc.generated_pdf_filename)
                if os.path.exists(pdf_path):
                    upload_file_to_share(pdf_path, doc.generated_pdf_filename)
            if success:
                flash(f"Document {doc.full_code} approved and uploaded to OneDrive!", "success")
            else:
                flash(f"Document {doc.full_code} approved, but OneDrive upload failed.", "warning")
        else:
            flash(f"Document {doc.full_code} approved (OneDrive not configured or file missing).", "success")
    else:
        flash(f"Document {doc.full_code} approved.", "success")

    db.session.commit()
    return redirect(url_for("documents"))


@app.route("/reject/<int:doc_id>", methods=["POST"])
@login_required
@admin_required
def reject(doc_id):
    """Reject a pending document."""
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'pending':
        flash("Only pending documents can be rejected.", "warning")
        return redirect(url_for("documents"))

    doc.status = 'rejected'
    db.session.commit()
    flash(f"Document {doc.full_code} has been rejected.", "info")
    return redirect(url_for("documents"))


@app.route("/users")
@login_required
@admin_required
def users():
    """User Management Page."""
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=all_users)


@app.route("/users/role/<email>", methods=["POST"])
@login_required
@admin_required
def toggle_user_role(email):
    user = User.query.filter_by(email=email).first_or_404()
    if user.email in ADMIN_EMAILS:
        flash("Cannot change role of a root admin.", "warning")
    else:
        user.role = 'admin' if user.role == 'user' else 'user'
        db.session.commit()
        flash(f"User {email} is now {user.role}.", "success")
    return redirect(url_for("users"))


@app.route("/users/delete/<email>", methods=["POST"])
@login_required
@admin_required
def delete_user(email):
    user = User.query.filter_by(email=email).first_or_404()
    if user.email in ADMIN_EMAILS:
        flash("Cannot delete a root admin.", "warning")
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f"User {email} has been deleted.", "info")
    return redirect(url_for("users"))


@app.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    role = request.form.get("role", "user").strip()

    if not name or not email:
        flash("Name and email are required.", "warning")
        return redirect(url_for("users"))

    if User.query.filter_by(email=email).first():
        flash("A user with this email already exists.", "warning")
        return redirect(url_for("users"))

    totp_secret = pyotp.random_base32()
    user = User(email=email, name=name, totp_secret=totp_secret, is_setup=False, role=role)
    db.session.add(user)
    db.session.commit()
    flash(f"User {name} added successfully.", "success")
    return redirect(url_for("users"))


@app.route("/users/edit/<email>", methods=["POST"])
@login_required
@admin_required
def edit_user(email):
    user = User.query.filter_by(email=email).first_or_404()

    name = request.form.get("name", "").strip()
    role = request.form.get("role", user.role).strip()
    reset_otp = request.form.get("reset_otp") == "on"

    if name:
        user.name = name

    if user.email not in ADMIN_EMAILS:
        user.role = role
    elif role != 'admin':
        flash("Cannot remove admin role from a root admin.", "warning")

    if reset_otp:
        user.totp_secret = pyotp.random_base32()
        user.is_setup = False
        flash(f"Authenticator reset for {user.name}.", "info")

    db.session.commit()
    flash(f"User {user.email} updated successfully.", "success")
    return redirect(url_for("users"))


# ── AI Content Generator Routes ─────────────────────────────────────────────
#
# Placeholder contract with the .docx/.pages letterhead template:
#   {{CODE_NUMBER}}  -> document code, e.g. "0031 ESSIC 05-2026"
#   {{SEND_TO}}      -> recipient office/department (normalized Arabic)
#   {{SUBJECT}}      -> subject line
#   {{STACK_HOLDER}} -> recipient's formal name/title line, e.g.
#                       "السيد الأستاذ الدكتور / محمد عبدالعال – الموقر"
#   {{POSITION}}     -> recipient's position, e.g. "نائب رئيس جامعة حورس - مصر"
#   {{BODY_TEXT}}    -> generated letter body ONLY (paragraphs, no header/signature)
#
# NOTE: these exact token names (SEND_TO / STACK_HOLDER, in this word order)
# must match whatever .docx/.pages template is actually uploaded. A previous
# version of this code used {{TO_SEND}}/{{HOLDER_STACK}} based on an older
# template file, which didn't match the token names in the template actually
# used in production — those two fields were left unreplaced as literal
# "{{TO_SEND}}"/"{{HOLDER_STACK}}" text. Always grep the real template's XML
# for `{{[A-Z_]*}}` before assuming a placeholder's exact name/order.
#
# The template already renders sender info and the closing signature as
# static content, so those are never re-embedded into {{BODY_TEXT}}.

from services.ai_generator import (generate_arabic_text, build_full_document_text,
                                   get_available_models, normalize_recipient)
from services.word_editor import replace_placeholders


@app.route("/ai/new")
@login_required
def ai_step1():
    return render_template("ai_step1.html")


@app.route("/ai/compose/<doc_type>")
@login_required
def ai_step2(doc_type):
    if doc_type not in ("letter", "request"):
        return redirect(url_for("ai_step1"))
    return render_template("ai_step2.html", doc_type=doc_type, models=get_available_models())


@app.route("/ai/generate", methods=["POST"])
@login_required
def ai_generate():
    doc_type = request.form.get("doc_type", "letter")
    sender = request.form.get("sender", "").strip()
    recipient = request.form.get("recipient", "").strip()
    subject = request.form.get("subject", "").strip()
    holder_name = request.form.get("holder_name", "").strip()
    position = request.form.get("position", "").strip()
    raw_draft = request.form.get("raw_draft", "").strip()
    model = request.form.get("model")

    if not all([sender, recipient, subject, holder_name, position, raw_draft]):
        flash("يرجى ملء جميع الحقول المطلوبة.", "warning")
        return redirect(url_for("ai_step2", doc_type=doc_type))

    user_email = session['user']['email']
    result = generate_arabic_text(doc_type=doc_type, sender=sender, recipient=recipient, subject=subject,
                                  raw_draft=raw_draft, user_email=user_email)

    if not result["success"]:
        flash(f"خطأ في توليد المحتوى: {result['error']}", "danger")
        return redirect(url_for("ai_step2", doc_type=doc_type))

    if result.get("warning"):
        flash(result["warning"], "warning")

    full_body = build_full_document_text(generated_body=result["text"])

    return render_template("ai_step3.html", doc_type=doc_type, sender=sender, recipient=recipient, subject=subject,
                           holder_name=holder_name, position=position, raw_draft=raw_draft,
                           generated_body=result["text"], full_body=full_body, model=model,
                           models=get_available_models(), )


@app.route("/ai/finalize", methods=["POST"])
@login_required
def ai_finalize():
    doc_type = request.form.get("doc_type", "letter")
    sender = request.form.get("sender", "")
    recipient = request.form.get("recipient", "")
    subject = request.form.get("subject", "")
    holder_name = request.form.get("holder_name", "")
    position = request.form.get("position", "")
    raw_draft = request.form.get("raw_draft", "")
    full_body = request.form.get("full_body", "")
    model = request.form.get("model")

    file = request.files.get("docx_file")
    if not file or file.filename == "":
        flash("يرجى رفع ملف القالب (.docx).", "warning")
        return redirect(url_for("ai_step1"))
    if not allowed_file(file.filename):
        flash("يُقبل ملفات .docx فقط.", "danger")
        return redirect(url_for("ai_step1"))

    original_name = secure_filename(file.filename)
    upload_path = os.path.join(UPLOAD_FOLDER, original_name)
    file.save(upload_path)

    now = datetime.utcnow()
    serial = get_next_serial(now.month, now.year)
    code = build_full_code(serial, now.month, now.year)

    stem = original_name.rsplit(".", 1)[0]
    gen_name = f"{stem}__{code.replace(' ', '_')}.docx"
    gen_path = os.path.join(GENERATED_FOLDER, gen_name)

    try:
        replace_placeholders(upload_path, gen_path, {
            "{{CODE_NUMBER}}": code,
            "{{SEND_TO}}": normalize_recipient(recipient),
            "{{SUBJECT}}": subject,
            "{{STACK_HOLDER}}": holder_name,
            "{{POSITION}}": position,
            "{{BODY_TEXT}}": full_body,
            "{{SENDER}}": sender,
        })

        from services.pdf_converter import convert_docx_to_pdf
        gen_pdf_name = gen_name.replace(".docx", ".pdf")
        gen_pdf_path = os.path.join(GENERATED_FOLDER, gen_pdf_name)
        pdf_success = convert_docx_to_pdf(gen_path, gen_pdf_path)
        if not pdf_success:
            gen_pdf_name = None

    except Exception as e:
        flash(f"خطأ في معالجة المستند: {e}", "danger")
        return redirect(url_for("ai_step1"))

    user_email = session['user']['email']
    user_name = session['user']['name']
    status = 'approved' if is_current_user_admin() else 'pending'

    doc = Document(serial_number=serial, full_code=code, month=now.month, year=now.year, doc_type=doc_type,
                   sender=sender, recipient=recipient, subject=subject, holder_name=holder_name, position=position,
                   raw_draft=raw_draft, generated_body=full_body,
                   filename=original_name, generated_filename=gen_name, generated_pdf_filename=gen_pdf_name,
                   ai_model=model, username=user_name, email=user_email,
                   status=status, )
    db.session.add(doc)
    db.session.commit()

    if status == 'approved':
        from services.onedrive import upload_file_to_onedrive
        try:
            upload_file_to_onedrive(gen_path, gen_name)
        except Exception as e:
            flash(f"Error uploading to OneDrive: {e}", "danger")

    flash(f"تم إنشاء المستند بنجاح — الرمز: <strong>Code No {code}</strong>", "success")
    return redirect(url_for("documents"))


@app.route("/api/ai/regenerate", methods=["POST"])
@login_required
def api_ai_regenerate():
    data = request.get_json()
    user_email = session['user']['email']
    result = generate_arabic_text(doc_type=data.get("doc_type", "letter"), sender=data.get("sender", ""),
                                  recipient=data.get("recipient", ""), subject=data.get("subject", ""),
                                  raw_draft=data.get("raw_draft", ""), user_email=user_email)
    if result["success"]:
        full_body = build_full_document_text(generated_body=result["text"])
        return jsonify({"success": True, "body": result["text"], "full_body": full_body,
                        "warning": result.get("warning")})
    return jsonify({"success": False, "error": result["error"]})


# ─── Entry Point ─────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    user_email = session['user']['email']
    user = User.query.filter_by(email=user_email).first()

    if not user:
        flash("User not found in database.", "danger")
        return redirect(url_for('documents'))

    from services.ai_generator import encrypt_api_key, get_user_keys

    if request.method == "POST":
        gemini = request.form.get("gemini_key", "").strip()
        groq = request.form.get("groq_key", "").strip()
        deepseek = request.form.get("deepseek_key", "").strip()

        user.gemini_api_key = encrypt_api_key(gemini) if gemini else ""
        user.groq_api_key = encrypt_api_key(groq) if groq else ""
        user.deepseek_api_key = encrypt_api_key(deepseek) if deepseek else ""

        db.session.commit()
        flash("API Keys saved securely.", "success")
        return redirect(url_for('settings_page'))

    user_keys = get_user_keys(user_email)
    return render_template("settings.html", user_keys=user_keys)


if __name__ == "__main__":
    app.run(debug=true, host="0.0.0.0", port=5010)