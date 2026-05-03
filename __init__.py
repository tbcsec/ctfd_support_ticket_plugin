"""
__init__.py — CTFd Support Ticket Plugin

Drop this folder into CTFd/plugins/ and restart CTFd.
CTFd will call load(app) automatically.

Routes registered
─────────────────
User-facing:
  GET  /support                           List current user's / team's tickets
  GET  /support/new                       New ticket form
  POST /support/new                       Submit a new ticket
  GET  /support/<id>                      View a ticket and its replies
  POST /support/<id>/close                Close a ticket (owner or admin)
  GET  /support/attachments/<id>          Serve an image attachment

Admin:
  GET  /admin/support                     All tickets (filterable by status)
  GET  /admin/support/<id>               View ticket + reply/close controls
  POST /admin/support/<id>/reply         Post an admin reply
  POST /admin/support/<id>/close         Close a ticket
  GET  /admin/support/export             Download CSV of all tickets
  GET  /api/support/open_count           JSON — open ticket count (admin only)
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import threading
import time

from flask import (
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from CTFd.utils.user import get_current_user
from jinja2 import ChoiceLoader, FileSystemLoader
from CTFd.utils.plugins import register_script, register_admin_script
from CTFd.models import Challenges, Users, db
from CTFd.plugins import register_plugin_assets_directory, register_admin_plugin_menu_bar
from CTFd.utils.decorators import admins_only, authed_only

from .models import SupportTicket, SupportTicketAttachment, SupportTicketReply
from .utils import (
    TICKET_CATEGORIES,
    TICKET_STATUSES,
    generate_tickets_csv,
    is_teams_mode,
    user_can_view_ticket,
    validate_and_read_image,
)

# Absolute path to this plugin's directory
_PLUGIN_DIR = Path(__file__).parent.resolve()

def load(app):
    # ── 1. Ensure our DB tables exist ─────────────────────────────────────────
    app.db.create_all()

    # ── 2. Register static assets (JS for admin badge / toast) ───────────────
    register_plugin_assets_directory(
        app,
        base_path="/plugins/support/assets/",
        admins_only=False,  # the JS file checks the URL itself
        endpoint="support_assets",
    )
    register_admin_plugin_menu_bar(title="Support Tickets", route="/admin/support")
    register_script("/plugins/support/assets/user_support.js")
    register_admin_script("/plugins/support/assets/admin_support.js")
    # ── 3. Add our templates directory to Jinja2's search path ───────────────
    #       We prepend it so our templates are found first; they then
    #       {% extend "base.html" %} from CTFd's own loader.
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(_PLUGIN_DIR / "templates")),
        app.jinja_loader,
    ])

    @app.template_filter("time_since")
    def time_since_filter(dt):
        # Make the stored naive datetime timezone-aware before comparing
        dt_aware = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt_aware
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return "just now"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = total_seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ctx():
        """Common template context injected into every render call."""
        return dict(categories=TICKET_CATEGORIES, statuses=TICKET_STATUSES)
    

    # ═════════════════════════════════════════════════════════════════════════
    # User-facing routes
    # ═════════════════════════════════════════════════════════════════════════

    @app.route("/support", methods=["GET"])
    @authed_only
    def support_ticket_list():
        current_user = get_current_user()
        if is_teams_mode() and getattr(current_user, "team_id", None):
            tickets = (
                SupportTicket.query
                .filter_by(team_id=current_user.team_id)
                .order_by(SupportTicket.created_at.desc())
                .all()
            )
        else:
            tickets = (
                SupportTicket.query
                .filter_by(user_id=current_user.id)
                .order_by(SupportTicket.created_at.desc())
                .all()
            )
        return render_template(
            "support/ticket_list.html",
            tickets=tickets,
            **_ctx(),
        )

    @app.route("/support/new", methods=["GET", "POST"])
    @authed_only
    def support_new_ticket():
        current_user = get_current_user()
        visible_challenges = (
            Challenges.query
            .filter_by(state="visible")
            .order_by(Challenges.name)
            .all()
        )

        if request.method == "POST":
            title        = request.form.get("title", "").strip()
            category     = request.form.get("category", "").strip()
            challenge_id = request.form.get("challenge_id") or None
            description  = request.form.get("description", "").strip()
            attachment   = request.files.get("attachment")

            errors = []

            # ── Field validation ──────────────────────────────────────────
            if not title:
                errors.append("A ticket title is required.")
            elif len(title) > 255:
                errors.append("Title must be 255 characters or fewer.")

            if not category:
                errors.append("Please select a category.")
            elif category not in TICKET_CATEGORIES:
                errors.append("Invalid category selected.")

            if not description:
                errors.append("A description is required.")

            # ── Attachment validation (optional field) ────────────────────
            att_data    = None
            att_mime    = None
            att_fname   = None
            has_attachment = attachment and attachment.filename

            if has_attachment:
                try:
                    att_data, att_mime = validate_and_read_image(attachment)
                    att_fname = attachment.filename
                except ValueError as exc:
                    errors.append(str(exc))

            # ── If validation failed, re-render form with errors ──────────
            if errors:
                for msg in errors:
                    flash(msg, "danger")
                return render_template(
                    "support/ticket_new.html",
                    challenges=visible_challenges,
                    form_data=request.form,
                    **_ctx(),
                )

            # ── Persist ticket ────────────────────────────────────────────
            ticket = SupportTicket(
                title=title,
                category=category,
                description=description,
                status="open",
                user_id=current_user.id,
                team_id=(
                    getattr(current_user, "team_id", None)
                    if is_teams_mode()
                    else None
                ),
                challenge_id=int(challenge_id) if challenge_id else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(ticket)
            db.session.flush()  # populate ticket.id before adding related rows

            if att_data is not None:
                attachment_row = SupportTicketAttachment(
                    ticket_id=ticket.id,
                    filename=att_fname,
                    data=att_data,
                    mimetype=att_mime,
                )
                db.session.add(attachment_row)

            # ── In-platform notification for admins ───────────────────────
            #    CTFd's Notifications model broadcasts via SSE to all
            #    connected clients.  We use it to alert the admin team.
            try:
                from CTFd.models import Notifications  # noqa: PLC0415

                notif = Notifications(
                    title="[Support] New ticket opened",
                    content=(
                        f'A new support ticket has been submitted: '
                        f'"{title}" (Category: {category}). '
                        f'View it in the admin panel under Plugins → Support Tickets.'
                    ),
                )
                db.session.add(notif)
            except Exception:
                # Degrade gracefully if the model is unavailable in this CTFd version.
                pass

            db.session.commit()

            flash("Your support ticket has been submitted successfully.", "success")
            return redirect(url_for("support_view_ticket", ticket_id=ticket.id))

        # GET — show blank form
        return render_template(
            "support/ticket_new.html",
            challenges=visible_challenges,
            form_data={},
            **_ctx(),
        )

    @app.route("/support/<int:ticket_id>", methods=["GET"])
    @authed_only
    def support_view_ticket(ticket_id):
        ticket = SupportTicket.query.get_or_404(ticket_id)
        if not user_can_view_ticket(ticket):
            abort(403)

        challenge = (
            Challenges.query.get(ticket.challenge_id)
            if ticket.challenge_id
            else None
        )
        submitter = Users.query.get(ticket.user_id)

        return render_template(
            "support/ticket_view.html",
            ticket=ticket,
            challenge=challenge,
            submitter=submitter,
            **_ctx(),
        )

    @app.route("/support/<int:ticket_id>/close", methods=["POST"])
    @authed_only
    def support_close_ticket(ticket_id):
        ticket = SupportTicket.query.get_or_404(ticket_id)
        if not user_can_view_ticket(ticket):
            abort(403)

        if ticket.status == "closed":
            flash("This ticket is already closed.", "info")
        else:
            ticket.status = "closed"
            ticket.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Ticket marked as closed.", "success")

        return redirect(url_for("support_view_ticket", ticket_id=ticket.id))

    @app.route("/support/attachments/<int:attachment_id>")
    @authed_only
    def support_get_attachment(attachment_id):
        att    = SupportTicketAttachment.query.get_or_404(attachment_id)
        ticket = SupportTicket.query.get_or_404(att.ticket_id)

        if not user_can_view_ticket(ticket):
            abort(403)

        response = make_response(att.data)
        response.headers["Content-Type"]        = att.mimetype
        response.headers["Content-Disposition"] = (
            f'inline; filename="{att.filename}"'
        )
        return response

    # ═════════════════════════════════════════════════════════════════════════
    # Admin routes
    # ═════════════════════════════════════════════════════════════════════════

    @app.route("/admin/support", methods=["GET"])
    @admins_only
    def admin_support_list():
        status_filter = request.args.get("status", "").strip()
        query = SupportTicket.query

        if status_filter and status_filter in TICKET_STATUSES:
            query = query.filter_by(status=status_filter)

        tickets    = query.order_by(SupportTicket.created_at.desc()).all()
        open_count = SupportTicket.query.filter_by(status="open").count()

        user_ids = {t.user_id for t in tickets}
        users = {
            u.id: u
            for u in Users.query.filter(Users.id.in_(user_ids)).all()
        }

        return render_template(
            "admin/support_list.html",
            tickets=tickets,
            status_filter=status_filter,
            open_count=open_count,
            users=users,
            **_ctx(),
        )

    @app.route("/admin/support/<int:ticket_id>", methods=["GET"])
    @admins_only
    def admin_support_view(ticket_id):
        ticket    = SupportTicket.query.get_or_404(ticket_id)
        challenge = (
            Challenges.query.get(ticket.challenge_id)
            if ticket.challenge_id
            else None
        )
        submitter = Users.query.get(ticket.user_id)

        return render_template(
            "admin/support_view.html",
            ticket=ticket,
            challenge=challenge,
            submitter=submitter,
            **_ctx(),
        )

    @app.route("/admin/support/<int:ticket_id>/reply", methods=["POST"])
    @admins_only
    def admin_support_reply(ticket_id):
        current_user = get_current_user()
        ticket  = SupportTicket.query.get_or_404(ticket_id)
        content = request.form.get("content", "").strip()
        existing_reply = SupportTicketReply.query.filter_by(
            ticket_id=ticket.id,
        ).count()

        if not content:
            flash("Reply content cannot be empty.", "danger")
            return redirect(url_for("admin_support_view", ticket_id=ticket_id))

        if ticket.status == "closed":
            flash(
                "This ticket is closed. Re-open it before replying.",
                "warning",
            )
            return redirect(url_for("admin_support_view", ticket_id=ticket_id))
        
        # limit replies to 10 per ticket
        if existing_reply >= 10:
            flash("This ticket has reached the maximum number of replies.", "warning")
            return redirect(url_for("admin_support_view", ticket_id=ticket_id))

        reply = SupportTicketReply(
            ticket_id=ticket.id,
            admin_id=current_user.id,
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(reply)

        ticket.status     = "admin_response"
        ticket.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Reply sent successfully.", "success")
        return redirect(url_for("admin_support_view", ticket_id=ticket_id))

    @app.route("/admin/support/<int:ticket_id>/close", methods=["POST"])
    @admins_only
    def admin_support_close(ticket_id):
        ticket = SupportTicket.query.get_or_404(ticket_id)

        if ticket.status == "closed":
            flash("Ticket is already closed.", "info")
        else:
            ticket.status     = "closed"
            ticket.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Ticket closed.", "success")

        return redirect(url_for("admin_support_view", ticket_id=ticket_id))

    @app.route("/admin/support/export", methods=["GET"])
    @admins_only
    def admin_support_export():
        tickets  = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
        csv_data = generate_tickets_csv(tickets)

        filename = (
            f"support_tickets_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
        )
        response = make_response(csv_data)
        response.headers["Content-Type"]        = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    # ── Lightweight JSON API (used by the admin badge JS) ─────────────────────

    @app.route("/api/support/open_count", methods=["GET"])
    @admins_only
    def support_open_count_api():
        count = SupportTicket.query.filter_by(status="open").count()
        return jsonify({"open_count": count})

