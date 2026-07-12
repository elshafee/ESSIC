"""
Database models for the Office Document Numbering System.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """
    Represents an authorized user of the system.
    Stores their TOTP secret for Authenticator App login.
    """
    __tablename__ = "users"

    email       = db.Column(db.String(100), primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    totp_secret = db.Column(db.String(32), nullable=True)
    is_setup    = db.Column(db.Boolean, default=False)
    role        = db.Column(db.String(20), default='user')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    # Encrypted AI provider API keys (stored via cryptography.fernet)
    gemini_api_key   = db.Column(db.Text, nullable=True)
    groq_api_key     = db.Column(db.Text, nullable=True)
    deepseek_api_key = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<User {self.email}>"


class Document(db.Model):
    """
    Represents a processed office document record.
    Stores the generated code number and file references.
    """
    __tablename__ = "documents"

    id               = db.Column(db.Integer, primary_key=True)
    serial_number    = db.Column(db.Integer, nullable=False)          # e.g. 31
    full_code        = db.Column(db.String(100), nullable=False)      # e.g. 0031 ESSIC 05-2026
    month            = db.Column(db.Integer, nullable=False)
    year             = db.Column(db.Integer, nullable=False)
    filename         = db.Column(db.String(255), nullable=False)      # original uploaded filename
    file_title       = db.Column(db.String(255), nullable=True)       # user provided title
    generated_filename = db.Column(db.String(255), nullable=True)     # filename of modified doc
    generated_pdf_filename = db.Column(db.String(255), nullable=True) # filename of generated PDF
    username         = db.Column(db.String(100), nullable=True)       # person who generated
    email            = db.Column(db.String(100), nullable=True)       # person who generated
    status           = db.Column(db.String(50), default='pending')    # pending, approved
    doc_type         = db.Column(db.String(20), nullable=True)        # "letter" or "request"
    sender           = db.Column(db.Text, nullable=True)
    recipient        = db.Column(db.Text, nullable=True)
    subject          = db.Column(db.Text, nullable=True)
    holder_name      = db.Column(db.Text, nullable=True)
    position         = db.Column(db.Text, nullable=True)
    is_internal      = db.Column(db.Boolean, default=False)
    manager_is_sender = db.Column(db.Boolean, default=False)
    raw_draft        = db.Column(db.Text, nullable=True)
    generated_body   = db.Column(db.Text, nullable=True)
    ai_model         = db.Column(db.String(100), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Document id={self.id} code={self.full_code}>"
