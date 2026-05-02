"""
models.py — Database models for the CTFd Support Ticket plugin.

Three tables are created:
  - support_tickets        : The ticket itself.
  - support_ticket_replies : Admin responses to a ticket.
  - support_ticket_attachments : Image attachments (stored as binary blobs).
"""

from datetime import datetime, timezone

from CTFd.models import db


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Status: "open" | "awaiting_response" | "closed"
    status = db.Column(db.String(50), nullable=False, default="open")

    # Ownership — user_id is always set; team_id only in Teams mode.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    team_id = db.Column(
        db.Integer,
        db.ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Optional link to a specific challenge.
    challenge_id = db.Column(
        db.Integer,
        db.ForeignKey("challenges.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    replies = db.relationship(
        "SupportTicketReply",
        backref="ticket",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="SupportTicketReply.created_at",
    )
    attachments = db.relationship(
        "SupportTicketAttachment",
        backref="ticket",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<SupportTicket #{self.id} [{self.status}] {self.title!r}>"


class SupportTicketReply(db.Model):
    __tablename__ = "support_ticket_replies"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The admin who wrote this reply.
    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<SupportTicketReply #{self.id} ticket={self.ticket_id}>"


class SupportTicketAttachment(db.Model):
    __tablename__ = "support_ticket_attachments"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename = db.Column(db.String(255), nullable=False)
    # Image data stored as a binary blob — no filesystem dependency.
    data = db.Column(db.LargeBinary, nullable=False)
    mimetype = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def __repr__(self):
        return f"<SupportTicketAttachment #{self.id} {self.filename!r}>"
