from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("moderation", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        viols   = c.execute(
            "SELECT v.*,m.username FROM violations v JOIN members m ON v.discord_id=m.discord_id "
            "ORDER BY v.created_at DESC LIMIT 50").fetchall()
        tickets = c.execute(
            "SELECT t.*,m.username FROM support_tickets t JOIN members m ON t.discord_id=m.discord_id "
            "WHERE t.status='open' ORDER BY t.created_at DESC").fetchall()
    return render_template("mod/index.html", violations=list(viols), tickets=list(tickets))


@bp.route("/ticket/<int:tid>/close", methods=["POST"])
@login_required
def close_ticket(tid):
    from flask import session
    note = request.form.get("note", "")
    with db() as c:
        c.execute("UPDATE support_tickets SET status='closed',assigned_to=?,closed_at=datetime('now') WHERE id=?",
                  (str(session.get("admin_username")), tid))
        if note:
            c.execute("INSERT INTO violations(discord_id,type,detail,mod_id) SELECT discord_id,'ticket_note',?,? FROM support_tickets WHERE id=?",
                      (note, str(session.get("admin_username")), tid))
    flash(f"工單 #{tid} 已關閉")
    return redirect(url_for("moderation.index"))
