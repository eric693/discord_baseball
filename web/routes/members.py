from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("members", __name__)


@bp.route("/")
@login_required
def index():
    q      = request.args.get("q", "")
    team   = request.args.get("team", "")
    page   = int(request.args.get("page", 1))
    limit  = 30
    offset = (page - 1) * limit
    params = []
    where  = []
    if q:
        where.append("(username LIKE ? OR discord_id LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if team:
        where.append("team=?"); params.append(team)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    with db() as c:
        total = c.execute(f"SELECT COUNT(*) as n FROM members {w}", params).fetchone()["n"]
        rows  = c.execute(f"SELECT * FROM members {w} ORDER BY points DESC LIMIT ? OFFSET ?",
                          params + [limit, offset]).fetchall()
        teams = c.execute("SELECT DISTINCT team FROM members WHERE team IS NOT NULL").fetchall()
    return render_template("members/index.html",
        members=list(rows), total=total, page=page, limit=limit,
        q=q, team=team, teams=[t["team"] for t in teams])


@bp.route("/<discord_id>")
@login_required
def detail(discord_id):
    with db() as c:
        member = c.execute("SELECT * FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        if not member:
            flash("找不到此用戶"); return redirect(url_for("members.index"))
        txns = c.execute(
            "SELECT * FROM point_transactions WHERE discord_id=? ORDER BY created_at DESC LIMIT 20",
            (discord_id,)).fetchall()
        viols = c.execute(
            "SELECT * FROM violations WHERE discord_id=? ORDER BY created_at DESC LIMIT 15",
            (discord_id,)).fetchall()
        ratings = c.execute(
            "SELECT * FROM ratings WHERE rated_id=? ORDER BY created_at DESC LIMIT 10",
            (discord_id,)).fetchall()
    return render_template("members/detail.html", member=member, txns=list(txns),
                           violations=list(viols), ratings=list(ratings))


@bp.route("/<discord_id>/adjust_points", methods=["POST"])
@admin_required
def adjust_points(discord_id):
    amount = int(request.form.get("amount", 0))
    reason = request.form.get("reason", "後台調整")
    with db() as c:
        c.execute("UPDATE members SET points=MAX(0,points+?) WHERE discord_id=?", (amount, discord_id))
        c.execute("INSERT INTO point_transactions(discord_id,amount,reason) VALUES(?,?,?)",
                  (discord_id, amount, f"[後台] {reason}"))
    flash(f"已{"給予" if amount>0 else "扣除"} {abs(amount)} 點")
    return redirect(url_for("members.detail", discord_id=discord_id))


@bp.route("/<discord_id>/toggle_ban", methods=["POST"])
@admin_required
def toggle_ban(discord_id):
    with db() as c:
        row = c.execute("SELECT is_banned FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        new = 0 if row["is_banned"] else 1
        c.execute("UPDATE members SET is_banned=? WHERE discord_id=?", (new, discord_id))
    flash("已更新封禁狀態")
    return redirect(url_for("members.detail", discord_id=discord_id))


@bp.route("/<discord_id>/toggle_vip", methods=["POST"])
@admin_required
def toggle_vip(discord_id):
    with db() as c:
        row = c.execute("SELECT is_vip FROM members WHERE discord_id=?", (discord_id,)).fetchone()
        new = 0 if row["is_vip"] else 1
        c.execute("UPDATE members SET is_vip=? WHERE discord_id=?", (new, discord_id))
    flash("已更新 VIP 狀態")
    return redirect(url_for("members.detail", discord_id=discord_id))
