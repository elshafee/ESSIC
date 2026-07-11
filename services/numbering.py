"""
services/numbering.py

Handles auto-incrementing document number generation.
Numbers reset every month/year combination.

Format: 0031 ESSIC 05-2026
"""

from models import db, Document


OFFICE_CODE = "ESSIC"


def get_next_serial(month: int, year: int) -> int:
    """
    Returns the next sequential serial number for the given month/year.
    Resets to 1 when a new month or year begins.
    """
    last = (
        db.session.query(Document)
        .filter_by(month=month, year=year)
        .order_by(Document.serial_number.desc())
        .first()
    )
    return (last.serial_number + 1) if last else 1


def build_full_code(serial: int, month: int, year: int) -> str:
    """
    Builds the formatted document code string.
    Example: 0031 ESSIC 05-2026
    """
    return f"{serial:04d} {OFFICE_CODE} {month:02d}-{year}"
