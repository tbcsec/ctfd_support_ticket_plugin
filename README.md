# CTFd Support Ticket Plugin

A support ticket system plugin for [CTFd](https://ctfd.io/), designed for remote CTF competitions where participants need to communicate with the administrative team. Participants can submit tickets, attach screenshots, and receive guidance from admins — all without leaving the platform.

---

## Features

- **Ticket submission** — participants can open tickets with a title, category, optional challenge link, description, and a screenshot attachment
- **Team-aware visibility** — in Teams mode, all members of a team can see their team's tickets; in User mode, tickets are private to the submitter
- **Admin shared inbox** — any admin can view, respond to, and close any ticket
- **Status workflow** — tickets move through `Open → Awaiting User Response → Closed` automatically as admins reply
- **In-platform notifications** — a live badge in the admin navbar shows the current open ticket count, with a toast notification firing when new tickets are submitted
- **Image-only attachments** — participants can attach screenshots (PNG, JPG, GIF, WEBP — max 5 MB); file type is validated by magic bytes, not just extension
- **CSV export** — admins can download a full export of all tickets for post-competition review
- **Time since last update** — the admin ticket list shows both the absolute timestamp and a human-readable relative time for each ticket's last update
- **No external dependencies** — everything runs on CTFd's existing stack with no additional packages required

---

## Requirements

- CTFd (tested against the current stable release)
- Python 3.11+
- No additional pip packages required

---

## Installation

1. Clone or download this repository into your CTFd plugins directory:

```bash
cd /opt/CTFd/CTFd/plugins
git clone https://github.com/yourusername/ctfd-support-tickets support
```

2. Restart CTFd:

```bash
docker compose restart ctfd
# or however you manage your CTFd instance
```

3. The plugin will create its database tables automatically on first startup. No manual migration step is required.

4. A **Support Tickets** link will appear in the admin navbar. Participants will see a **Support** link in the main site navbar.

---

## Plugin Structure

```
support/
├── __init__.py                      # Plugin entrypoint — all routes and load()
├── models.py                        # SQLAlchemy models
├── utils.py                         # Auth helpers, image validation, CSV builder
├── config.json                      # Plugin name registration
├── requirements.txt                 # Empty — no extra dependencies
├── assets/
│   ├── admin_support.js             # Admin badge + toast notification polling
│   └── user_support.js             # Injects Support link into user navbar
└── templates/
    ├── support/
    │   ├── ticket_list.html         # User: list of their tickets
    │   ├── ticket_new.html          # User: new ticket form
    │   └── ticket_view.html         # User: ticket detail + close button
    └── admin/
        ├── support_list.html        # Admin: all tickets with filtering
        └── support_view.html        # Admin: ticket detail + reply form
```

---

## Database Schema

The plugin creates three tables, all prefixed with `support_`:

**`support_tickets`**

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `title` | String(255) | |
| `category` | String(100) | One of the four hardcoded categories |
| `description` | Text | |
| `status` | String(50) | `open`, `awaiting_response`, or `closed` |
| `user_id` | FK → users | Submitting user |
| `team_id` | FK → teams | Nullable — set in Teams mode only |
| `challenge_id` | FK → challenges | Nullable — optional challenge link |
| `created_at` | DateTime (UTC) | |
| `updated_at` | DateTime (UTC) | |

**`support_ticket_replies`**

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `ticket_id` | FK → support_tickets | |
| `admin_id` | FK → users | Admin who sent the reply |
| `content` | Text | |
| `created_at` | DateTime (UTC) | |

**`support_ticket_attachments`**

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `ticket_id` | FK → support_tickets | |
| `filename` | String(255) | Original filename |
| `data` | LargeBinary | Image stored as a binary blob |
| `mimetype` | String(100) | Validated MIME type |
| `uploaded_at` | DateTime (UTC) | |

---

## Routes

### Participant-facing

| Method | Path | Description |
|---|---|---|
| GET | `/support` | List the current user's (or team's) tickets |
| GET | `/support/new` | New ticket form |
| POST | `/support/new` | Submit a new ticket |
| GET | `/support/<id>` | View a ticket and its replies |
| POST | `/support/<id>/close` | Close a ticket (owner only) |
| GET | `/support/attachments/<id>` | Serve an image attachment |

### Admin-facing

| Method | Path | Description |
|---|---|---|
| GET | `/admin/support` | All tickets, filterable by status |
| GET | `/admin/support/<id>` | View ticket, post reply, close |
| POST | `/admin/support/<id>/reply` | Submit an admin reply |
| POST | `/admin/support/<id>/close` | Close a ticket |
| GET | `/admin/support/export` | Download CSV export of all tickets |
| GET | `/api/support/open_count` | JSON — current open ticket count (admin only) |

---

## Ticket Categories

The following categories are hardcoded:

- Technical Issue
- Challenge Clarification
- General Enquiry
- Other

---

## Configuration

There is no admin configuration UI at this time. The following constants can be adjusted directly in the source files before deployment:

| Constant | File | Default | Description |
|---|---|---|---|
| `TICKET_CATEGORIES` | `utils.py` | See above | Hardcoded list of ticket categories |
| `ALLOWED_IMAGE_EXTENSIONS` | `utils.py` | png, jpg, jpeg, gif, webp | Accepted file extensions |
| `MAX_ATTACHMENT_BYTES` | `utils.py` | 5 MB | Maximum attachment file size |

---

## Screenshots

<img width="843" height="845" alt="Screenshot from 2026-05-03 19-44-25" src="https://github.com/user-attachments/assets/2f22e9ee-71c3-462f-92ee-8f3d68da8933" />

<img width="1196" height="410" alt="Screenshot from 2026-05-03 19-49-56" src="https://github.com/user-attachments/assets/27b0f63b-d6be-447e-8b77-b698f72799e9" />

<img width="1196" height="658" alt="Screenshot from 2026-05-03 19-48-09" src="https://github.com/user-attachments/assets/41ff41d5-43d4-4470-a82e-d09019ded472" />

<img width="943" height="861" alt="Screenshot from 2026-05-03 19-50-41" src="https://github.com/user-attachments/assets/a56eb808-6851-4e61-83ee-666552122e66" />

---

## Contributing

Issues and pull requests are welcome. Please open an issue before starting significant work so we can discuss the approach first.

---

## Licence

MIT Licence.
