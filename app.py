"""
LiverScope AI — Flask Backend (Entry Point)
Pipeline Hybrid: YOLOv11 → ResNet50 → XGBoost
Multi-Actor: Admin (CRUD Pasien + Deteksi) & Dokter (Diagnosa)
Dengan Database MySQL (Laragon)
"""

import os
from flask import Flask, request, send_from_directory

# ============================================================
#  FLASK APP SETUP
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    template_folder=os.path.join(BASE_DIR, "templates"),
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload
app.secret_key = "liverscope-ai-secret-key-2026"


@app.after_request
def add_header(response):
    """
    Disable caching for all dynamic pages and APIs to prevent back-button
    access to secure pages after logout, while keeping static assets cached.
    """
    # Do not affect static files or uploaded images/media
    if request.path.startswith("/static") or request.path.startswith("/uploads"):
        return response

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# ============================================================
#  REGISTER BLUEPRINTS
# ============================================================
from routes import register_blueprints
register_blueprints(app)


# ============================================================
#  INIT DATABASE (best effort)
# ============================================================
_db_ready = False

try:
    from database import init_db
    init_db()
    _db_ready = True
    print("[OK] Database MySQL connected!")
except Exception as e:
    print(f"[WARN] Database unavailable: {e}")
    print("   Detection will work, but save/history features are disabled.")


# ============================================================
#  SERVE UPLOADED IMAGES
# ============================================================
@app.route("/uploads/<path:filepath>")
def serve_upload(filepath):
    """Serve images from uploads directory."""
    from routes.auth import login_required

    @login_required
    def _serve():
        uploads_dir = os.path.join(BASE_DIR, "uploads")
        return send_from_directory(uploads_dir, filepath)

    return _serve()


# ============================================================
#  MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  LiverScope AI v2.0")
    print("  Hybrid Detection: YOLOv11 > ResNet50 > XGBoost")
    print("  Multi-Actor: Super Admin, Admin & Dokter")
    print("=" * 50)

    # Pre-load the model
    print("\n[LOADING] Pre-loading AI models...")
    try:
        from routes.detection import get_detector
        get_detector()
    except Exception as e:
        print(f"[WARN] Model pre-load failed: {e}")
        print("   Models will be loaded on first request.")

    print(f"\n[SERVER] Starting on http://localhost:5000")
    print("   Default login:")
    print("     Super Admin : superadmin/superadmin123")
    print("     Admin       : admin/admin123")
    print("     Dokter      : dokter/dokter123")
    print("   Press Ctrl+C to stop.\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
