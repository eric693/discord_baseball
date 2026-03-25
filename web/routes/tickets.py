from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("tickets", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        listings = c.execute(
            "SELECT t.*,m.username,m.credit_score FROM ticket_listings t "
            "JOIN members m ON t.discord_id=m.discord_id "
            "WHERE t.status='active' ORDER BY t.created_at DESC LIMIT 50").fetchall()
    return render_template("tickets/index.html", listings=list(listings))


@bp.route("/<int:lid>/close", methods=["POST"])
@admin_required
def close_listing(lid):
    with db() as c:
        c.execute("UPDATE ticket_listings SET status='closed' WHERE id=?", (lid,))
    flash(f"票券 #{lid} 已下架"); return redirect(url_for("tickets.index"))
