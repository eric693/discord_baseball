import io, csv
from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("draft", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        sessions = c.execute("SELECT * FROM draft_sessions ORDER BY created_at DESC").fetchall()
    return render_template("draft/index.html", sessions=list(sessions))


@bp.route("/<int:sid>")
@login_required
def detail(sid):
    with db() as c:
        sess    = c.execute("SELECT * FROM draft_sessions WHERE id=?", (sid,)).fetchone()
        teams   = c.execute("SELECT * FROM draft_teams WHERE session_id=? ORDER BY pick_order", (sid,)).fetchall()
        players = c.execute("SELECT * FROM draft_players WHERE session_id=? ORDER BY COALESCE(pick_number,9999),id", (sid,)).fetchall()
    return render_template("draft/detail.html", sess=sess, teams=list(teams), players=list(players))


@bp.route("/create", methods=["POST"])
@admin_required
def create():
    title  = request.form.get("title","").strip()
    rounds = int(request.form.get("rounds", 3))
    tpp    = int(request.form.get("time_per_pick", 180))
    with db() as c:
        c.execute("INSERT INTO draft_sessions(title,rounds,time_per_pick) VALUES(?,?,?)", (title, rounds, tpp))
    flash(f"選秀「{title}」已建立"); return redirect(url_for("draft.index"))


@bp.route("/<int:sid>/import_players", methods=["POST"])
@admin_required
def import_players(sid):
    f = request.files.get("csv_file")
    if not f:
        flash("請選擇 CSV 檔案"); return redirect(url_for("draft.detail", sid=sid))
    stream  = io.StringIO(f.stream.read().decode("utf-8-sig"), newline="")
    reader  = csv.reader(stream)
    count   = 0
    with db() as c:
        for row in reader:
            if not row or not row[0].strip(): continue
            name  = row[0].strip()
            pos   = row[1].strip() if len(row)>1 else ""
            org   = row[2].strip() if len(row)>2 else ""
            stats = row[3].strip() if len(row)>3 else ""
            c.execute("INSERT INTO draft_players(session_id,name,position,team_origin,stats) VALUES(?,?,?,?,?)",
                      (sid, name, pos, org, stats))
            count += 1
    flash(f"成功匯入 {count} 位球員"); return redirect(url_for("draft.detail", sid=sid))
