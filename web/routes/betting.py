import json
from flask import Blueprint, render_template, request, redirect, url_for, flash
from web.app import login_required, admin_required
from database import db

bp = Blueprint("betting", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        events = c.execute("SELECT * FROM bet_events ORDER BY created_at DESC LIMIT 30").fetchall()
    enriched = []
    for ev in events:
        with db() as c:
            cnt   = c.execute("SELECT COUNT(*) as n FROM bets WHERE event_id=?", (ev["id"],)).fetchone()["n"]
            total = c.execute("SELECT COALESCE(SUM(amount),0) as s FROM bets WHERE event_id=?", (ev["id"],)).fetchone()["s"]
        enriched.append({"ev": ev, "cnt": cnt, "total": total})
    return render_template("betting/index.html", events=enriched)


@bp.route("/<int:event_id>")
@login_required
def detail(event_id):
    with db() as c:
        ev   = c.execute("SELECT * FROM bet_events WHERE id=?", (event_id,)).fetchone()
        bets = c.execute(
            "SELECT b.*,m.username FROM bets b JOIN members m ON b.discord_id=m.discord_id "
            "WHERE b.event_id=? ORDER BY b.created_at DESC", (event_id,)).fetchall()
    if not ev:
        flash("找不到此賭盤"); return redirect(url_for("betting.index"))
    opts = json.loads(ev["options"]); odds = json.loads(ev["odds"])
    return render_template("betting/detail.html", ev=ev, bets=list(bets), opts=opts, odds=odds)


@bp.route("/create", methods=["POST"])
@admin_required
def create():
    title   = request.form.get("title", "").strip()
    desc    = request.form.get("description", "")
    options = [o.strip() for o in request.form.get("options", "").split(",") if o.strip()]
    odds    = [float(o.strip()) for o in request.form.get("odds", "").split(",") if o.strip()]
    closes  = request.form.get("closes_at") or None
    if not title or not options or len(options) != len(odds):
        flash("標題、選項、賠率為必填，且數量須一致"); return redirect(url_for("betting.index"))
    with db() as c:
        c.execute("INSERT INTO bet_events(title,description,options,odds,closes_at) VALUES(?,?,?,?,?)",
                  (title, desc, json.dumps(options, ensure_ascii=False),
                   json.dumps(dict(zip(options, odds)), ensure_ascii=False), closes))
    flash(f"賭盤「{title}」已開立"); return redirect(url_for("betting.index"))


@bp.route("/<int:event_id>/settle", methods=["POST"])
@admin_required
def settle(event_id):
    result = request.form.get("result", "")
    with db() as c:
        ev = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (event_id,)).fetchone()
        if not ev:
            flash("找不到此賭盤或已結算"); return redirect(url_for("betting.index"))
        opts = json.loads(ev["options"])
        if result not in opts:
            flash(f"無效結果，有效選項：{', '.join(opts)}"); return redirect(url_for("betting.detail", event_id=event_id))
        winners = c.execute("SELECT * FROM bets WHERE event_id=? AND option=? AND status='pending'", (event_id, result)).fetchall()
        losers  = c.execute("SELECT * FROM bets WHERE event_id=? AND option!=? AND status='pending'", (event_id, result)).fetchall()
        for b in winners:
            c.execute("UPDATE members SET points=points+? WHERE discord_id=?", (b["payout"], b["discord_id"]))
            c.execute("INSERT INTO point_transactions(discord_id,amount,reason) VALUES(?,?,?)",
                      (b["discord_id"], b["payout"], f"[後台] 賭盤獲勝派彩：{ev['title']}"))
            c.execute("UPDATE bets SET status='won' WHERE id=?", (b["id"],))
        for b in losers:
            c.execute("UPDATE bets SET status='lost' WHERE id=?", (b["id"],))
        c.execute("UPDATE bet_events SET status='settled',result=?,settled_at=datetime('now') WHERE id=?", (result, event_id))
    flash(f"已結算！獲勝 {len(winners)} 人，落敗 {len(losers)} 人")
    return redirect(url_for("betting.detail", event_id=event_id))


@bp.route("/<int:event_id>/cancel", methods=["POST"])
@admin_required
def cancel(event_id):
    with db() as c:
        ev   = c.execute("SELECT * FROM bet_events WHERE id=? AND status='open'", (event_id,)).fetchone()
        bets = c.execute("SELECT * FROM bets WHERE event_id=? AND status='pending'", (event_id,)).fetchall()
        for b in bets:
            c.execute("UPDATE members SET points=points+? WHERE discord_id=?", (b["amount"], b["discord_id"]))
            c.execute("INSERT INTO point_transactions(discord_id,amount,reason) VALUES(?,?,?)",
                      (b["discord_id"], b["amount"], f"[後台] 賭盤取消退款：{ev['title']}"))
            c.execute("UPDATE bets SET status='refunded' WHERE id=?", (b["id"],))
        c.execute("UPDATE bet_events SET status='cancelled' WHERE id=?", (event_id,))
    flash(f"賭盤已取消，退還 {len(bets)} 筆下注")
    return redirect(url_for("betting.index"))
