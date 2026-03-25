"""
web/routes/api.py — REST API endpoints
- POST /api/vip/grant   (external payment webhook)
- GET  /api/stats       (public stats JSON)
"""
import hashlib, hmac, os, asyncio, json
from flask import Blueprint, request, jsonify
from database import db

bp = Blueprint("api", __name__)

VIP_SECRET = os.getenv("VIP_WEBHOOK_SECRET", "")


def _verify_sig(payload: bytes, sig: str) -> bool:
    if not VIP_SECRET: return False
    expected = "sha256=" + hmac.new(VIP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@bp.route("/vip/grant", methods=["POST"])
def vip_grant():
    sig = request.headers.get("X-Webhook-Signature", "")
    if not _verify_sig(request.data, sig):
        return jsonify({"error": "invalid signature"}), 403
    data = request.get_json(force=True, silent=True) or {}
    discord_id = str(data.get("discord_id", ""))
    if not discord_id:
        return jsonify({"error": "discord_id required"}), 400

    # Try to call bot cog asynchronously
    try:
        from bot import CPBLBot
        # find running bot via import
        import bot as bot_module
        if hasattr(bot_module, "_bot_instance"):
            b = bot_module._bot_instance
            cog = b.cogs.get("VIP")
            if cog:
                future = asyncio.run_coroutine_threadsafe(cog.assign_vip(discord_id), b.loop)
                future.result(timeout=10)
    except Exception as e:
        print(f"[VIP webhook] bot call failed: {e}")
        # fallback: just update DB
        with db() as c:
            c.execute("UPDATE members SET is_vip=1 WHERE discord_id=?", (discord_id,))

    return jsonify({"ok": True, "discord_id": discord_id})


@bp.route("/vip/revoke", methods=["POST"])
def vip_revoke():
    sig = request.headers.get("X-Webhook-Signature", "")
    if not _verify_sig(request.data, sig):
        return jsonify({"error": "invalid signature"}), 403
    data = request.get_json(force=True, silent=True) or {}
    discord_id = str(data.get("discord_id", ""))
    with db() as c:
        c.execute("UPDATE members SET is_vip=0 WHERE discord_id=?", (discord_id,))
    return jsonify({"ok": True})


@bp.route("/stats")
def stats():
    with db() as c:
        return jsonify({
            "total_members": c.execute("SELECT COUNT(*) as n FROM members").fetchone()["n"],
            "active_today":  c.execute("SELECT COUNT(*) as n FROM members WHERE last_active>=date('now')").fetchone()["n"],
            "open_bets":     c.execute("SELECT COUNT(*) as n FROM bet_events WHERE status='open'").fetchone()["n"],
            "total_points":  c.execute("SELECT COALESCE(SUM(points),0) as s FROM members").fetchone()["s"],
        })
