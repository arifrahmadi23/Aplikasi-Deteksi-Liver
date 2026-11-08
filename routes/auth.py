"""
Routes — Auth (Login, Logout, Decorators)
Berisi decorator autentikasi dan routes login/logout.
"""

import re
from functools import wraps
from flask import (Blueprint, request, jsonify, session,
                   redirect, url_for, render_template)

auth_bp = Blueprint("auth", __name__)


# ============================================================
#  AUTH DECORATORS
# ============================================================
def login_required(f):
    """Decorator: halaman memerlukan login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: halaman khusus admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        if session.get("role") != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya admin."}), 403
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def doctor_required(f):
    """Decorator: halaman khusus dokter."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        if session.get("role") != "dokter":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya dokter."}), 403
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    """Decorator: halaman khusus super admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("auth.login_page"))
        if session.get("role") != "super_admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya super admin."}), 403
            return redirect(url_for("auth.login_page"))
        return f(*args, **kwargs)
    return decorated


# ============================================================
#  HELPER FUNCTIONS
# ============================================================
def validate_patient_data(data):
    """Validate patient data fields. Returns (is_valid, error_message)."""
    nama = data.get("nama", "").strip()
    nik = data.get("nik", "").strip()
    telepon = data.get("telepon", "").strip()

    # Nama: wajib diisi & tidak boleh mengandung angka
    if not nama:
        return False, "Nama pasien harus diisi."
    if re.search(r'\d', nama):
        return False, "Nama tidak boleh mengandung angka."

    # NIK: jika diisi, harus tepat 16 digit angka
    if nik:
        if not re.fullmatch(r'\d{16}', nik):
            return False, "NIK harus tepat 16 digit angka."

    # Telepon: jika diisi, hanya angka & maks 13 karakter
    if telepon:
        if not re.fullmatch(r'\d+', telepon):
            return False, "No. telepon hanya boleh berisi angka."
        if len(telepon) > 13:
            return False, "No. telepon maksimal 13 digit."

    return True, None


# ============================================================
#  AUTH ROUTES
# ============================================================
@auth_bp.route("/")
def root():
    """Render landing page."""
    return render_template("landing.html")


@auth_bp.route("/login")
def login_page():
    """Login page."""
    if "user_id" in session:
        return redirect(url_for("auth.root"))
    return render_template("login.html")


@auth_bp.route("/api/login", methods=["POST"])
def api_login():
    """Login API."""
    from database import get_user_by_username, verify_password

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username dan password harus diisi."}), 400

    user = get_user_by_username(username)

    if not user or not verify_password(user["password_hash"], password):
        return jsonify({"success": False, "error": "Username atau password salah."}), 401

    # Set session
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["nama_lengkap"] = user["nama_lengkap"]

    # Determine redirect URL
    if user["role"] == "super_admin":
        redirect_url = url_for("superadmin.superadmin_users")
    elif user["role"] == "admin":
        redirect_url = url_for("admin.admin_detect")
    else:
        redirect_url = url_for("doctor.doctor_dashboard")

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "nama_lengkap": user["nama_lengkap"],
        },
        "redirect": redirect_url,
    })


@auth_bp.route("/logout")
def logout():
    """Logout."""
    session.clear()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/api/me")
@login_required
def api_me():
    """Get current user info."""
    return jsonify({
        "success": True,
        "user": {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role"),
            "nama_lengkap": session.get("nama_lengkap"),
        }
    })
