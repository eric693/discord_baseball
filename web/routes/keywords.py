from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("keywords", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        kws = c.execute("SELECT * FROM keywords ORDER BY created_at DESC").fetchall()
    return render_template("keywords/index.html", keywords=list(kws))


@bp.route("/add", methods=["POST"])
@admin_required
def add():
    trigger  = request.form.get("trigger", "").strip()
    response = request.form.get("response", "").strip()
    if not trigger or not response:
        flash("觸發詞與回應皆為必填"); return redirect(url_for("keywords.index"))
    with db() as c:
        c.execute("INSERT OR REPLACE INTO keywords(trigger,response,is_active) VALUES(?,?,1)", (trigger, response))
    flash(f"關鍵字「{trigger}」已儲存")
    return redirect(url_for("keywords.index"))


@bp.route("/<int:kid>/toggle", methods=["POST"])
@admin_required
def toggle(kid):
    with db() as c:
        row = c.execute("SELECT is_active FROM keywords WHERE id=?", (kid,)).fetchone()
        c.execute("UPDATE keywords SET is_active=? WHERE id=?", (0 if row["is_active"] else 1, kid))
    flash("狀態已更新"); return redirect(url_for("keywords.index"))


@bp.route("/<int:kid>/delete", methods=["POST"])
@admin_required
def delete(kid):
    with db() as c:
        c.execute("DELETE FROM keywords WHERE id=?", (kid,))
    flash("已刪除"); return redirect(url_for("keywords.index"))
