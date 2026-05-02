"""
utils.py — Helper functions for the CTFd Support Ticket plugin.
"""

import csv
import io

from CTFd.utils.user import get_current_user, is_admin

from CTFd.utils import get_config
from CTFd.utils.modes import TEAMS_MODE

# ── Constants ──────────────────────────────────────────────────────────────────

TICKET_CATEGORIES = [
    "Technical Issue",
    "Challenge Clarification",
    "General Enquiry",
    "Other",
]

# Maps status key → (human label, Bootstrap colour class)
TICKET_STATUSES = {
    "open":               ("Open",                   "danger"),
    "admin_response":  ("Admin Response Sent", "warning"),
    "closed":             ("Closed",                 "secondary"),
}

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_IMAGE_MIMETYPES   = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_ATTACHMENT_BYTES      = 5 * 1024 * 1024  # 5 MB

# ── Mode helpers ───────────────────────────────────────────────────────────────

def is_teams_mode():
    """Return True when CTFd is running in Teams mode."""
    return get_config("user_mode") == TEAMS_MODE


# ── Authorisation ──────────────────────────────────────────────────────────────

def user_can_view_ticket(ticket):
    """
    Return True if the currently authenticated user is permitted to view
    *ticket*.  Admins can always see everything; non-admins can only see
    tickets they submitted (or, in Teams mode, tickets their team submitted).
    """
    current_user = get_current_user()
    if is_admin():
        return True
    if ticket.user_id == current_user.id:
        return True
    if (
        is_teams_mode()
        and ticket.team_id is not None
        and ticket.team_id == getattr(current_user, "team_id", None)
    ):
        return True
    return False


# ── Attachment validation ──────────────────────────────────────────────────────

def _sniff_mimetype(data: bytes, ext: str) -> str:
    """
    Detect image MIME type via magic bytes, falling back to the file extension.
    Only the four types we accept are recognised.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # Fall back to extension mapping
    return {
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "gif":  "image/gif",
        "webp": "image/webp",
    }.get(ext, "application/octet-stream")


def validate_and_read_image(file_storage):
    """
    Validate a Werkzeug FileStorage object as an allowed image upload.

    Returns:
        (data: bytes, mimetype: str) on success.

    Raises:
        ValueError with a user-friendly message on failure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No file was provided.")

    original_name = file_storage.filename
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"'.{ext}' is not an allowed file type. "
            "Please upload a PNG, JPG, GIF, or WEBP image."
        )

    data = file_storage.read()

    if len(data) == 0:
        raise ValueError("The uploaded file is empty.")

    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"File size ({len(data) / 1024 / 1024:.1f} MB) exceeds the 5 MB limit."
        )

    mimetype = _sniff_mimetype(data, ext)

    if mimetype not in ALLOWED_IMAGE_MIMETYPES:
        raise ValueError(
            "File content does not match an allowed image format. "
            "Only PNG, JPG, GIF, and WEBP images are accepted."
        )

    return data, mimetype


# ── CSV export ─────────────────────────────────────────────────────────────────

def generate_tickets_csv(tickets) -> str:
    """
    Serialise a list of SupportTicket instances to a CSV string.
    Includes one row per ticket; replies are summarised as a count.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    writer.writerow([
        "ID",
        "Title",
        "Category",
        "Status",
        "Challenge ID",
        "User ID",
        "Team ID",
        "Description",
        "Reply Count",
        "Has Attachment",
        "Created At (UTC)",
        "Updated At (UTC)",
    ])

    for t in tickets:
        writer.writerow([
            t.id,
            t.title,
            t.category,
            TICKET_STATUSES.get(t.status, (t.status,))[0],
            t.challenge_id if t.challenge_id else "",
            t.user_id,
            t.team_id if t.team_id else "",
            t.description,
            len(t.replies),
            "Yes" if t.attachments else "No",
            t.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            t.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    return output.getvalue()
