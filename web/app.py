"""
web/app.py — Flask Admin Panel factory
"""
import os, hashlib
from flask import Flask, session, redirect, url_for
from functools import wraps


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Only super_admin / admin role can access."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("auth.login"))
        if session.get("admin_role") not in ("admin", "super_admin"):
            from flask import abort
            abort(403)
        return f(*args, **kwargs)
    return decorated


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-CHANGE-ME")

    _seed_admin()

    from web.routes.auth       import bp as auth_bp
    from web.routes.dashboard  import bp as dash_bp
    from web.routes.members    import bp as mbr_bp
    from web.routes.shop       import bp as shop_bp
    from web.routes.betting    import bp as bet_bp
    from web.routes.moderation import bp as mod_bp
    from web.routes.keywords   import bp as kw_bp
    from web.routes.draft      import bp as draft_bp
    from web.routes.tickets    import bp as tix_bp
    from web.routes.api        import bp as api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dash_bp)
    app.register_blueprint(mbr_bp,    url_prefix="/members")
    app.register_blueprint(shop_bp,   url_prefix="/shop")
    app.register_blueprint(bet_bp,    url_prefix="/betting")
    app.register_blueprint(mod_bp,    url_prefix="/mod")
    app.register_blueprint(kw_bp,     url_prefix="/keywords")
    app.register_blueprint(draft_bp,  url_prefix="/draft")
    app.register_blueprint(tix_bp,    url_prefix="/tickets")
    app.register_blueprint(api_bp,    url_prefix="/api")

    return app


def _seed_admin():
    from database import db
    u  = os.getenv("ADMIN_USERNAME", "admin")
    pw = os.getenv("ADMIN_PASSWORD", "admin")
    ph = hashlib.sha256(pw.encode()).hexdigest()
    with db() as c:
        c.execute("INSERT OR IGNORE INTO admins(username,password_hash,role) VALUES(?,?,?)",
                  (u, ph, "super_admin"))
