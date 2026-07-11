"""
Database models for the Office Document Numbering System.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


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
    generated_filename = db.Column(db.String(255), nullable=True)     # filename of modified doc
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Document id={self.id} code={self.full_code}>"
