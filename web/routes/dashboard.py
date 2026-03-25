from flask import Blueprint, render_template
from web.app import login_required
from database import db

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    with db() as c:
        total_members  = c.execute("SELECT COUNT(*) as n FROM members").fetchone()["n"]
        active_today   = c.execute("SELECT COUNT(*) as n FROM members WHERE last_active>=date('now')").fetchone()["n"]
        total_points   = c.execute("SELECT COALESCE(SUM(points),0) as s FROM members").fetchone()["s"]
        open_bets      = c.execute("SELECT COUNT(*) as n FROM bet_events WHERE status='open'").fetchone()["n"]
        open_tickets   = c.execute("SELECT COUNT(*) as n FROM support_tickets WHERE status='open'").fetchone()["n"]
        banned_count   = c.execute("SELECT COUNT(*) as n FROM members WHERE is_banned=1").fetchone()["n"]
        vip_count      = c.execute("SELECT COUNT(*) as n FROM members WHERE is_vip=1").fetchone()["n"]

        team_dist = c.execute(
            "SELECT COALESCE(team,'未選隊') as team, COUNT(*) as cnt FROM members GROUP BY team ORDER BY cnt DESC"
        ).fetchall()

        daily_active = c.execute(
            "SELECT date(last_active) as day, COUNT(*) as cnt FROM members "
            "WHERE last_active>=date('now','-13 days') GROUP BY day ORDER BY day"
        ).fetchall()

        daily_pts = c.execute(
            "SELECT date(created_at) as day, SUM(CASE WHEN amount>0 THEN amount ELSE 0 END) as earned, "
            "SUM(CASE WHEN amount<0 THEN ABS(amount) ELSE 0 END) as spent "
            "FROM point_transactions WHERE created_at>=date('now','-13 days') GROUP BY day ORDER BY day"
        ).fetchall()

        recent_txns = c.execute(
            "SELECT t.amount,t.reason,t.created_at,m.username FROM point_transactions t "
            "JOIN members m ON t.discord_id=m.discord_id ORDER BY t.created_at DESC LIMIT 8"
        ).fetchall()

        recent_bets = c.execute(
            "SELECT e.title,COUNT(b.id) as cnt,SUM(b.amount) as vol FROM bets b "
            "JOIN bet_events e ON b.event_id=e.id GROUP BY e.id ORDER BY e.created_at DESC LIMIT 5"
        ).fetchall()

    return render_template("dashboard.html",
        total_members=total_members, active_today=active_today,
        total_points=total_points,  open_bets=open_bets,
        open_tickets=open_tickets,  banned_count=banned_count,
        vip_count=vip_count,
        team_dist=list(team_dist),
        daily_active=list(daily_active),
        daily_pts=list(daily_pts),
        recent_txns=list(recent_txns),
        recent_bets=list(recent_bets),
    )
