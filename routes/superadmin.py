"""
Routes — Super Admin (User Management)
Halaman dan API CRUD untuk manajemen user.
"""

from flask import Blueprint, render_template, request, jsonify, session
from .auth import super_admin_required

superadmin_bp = Blueprint("superadmin", __name__)


# ============================================================
#  SUPER ADMIN PAGE ROUTES
# ============================================================
@superadmin_bp.route("/superadmin/users")
@super_admin_required
def superadmin_users():
    """User management page - Super Admin only."""
    return render_template("users.html")


# ============================================================
#  API: USER MANAGEMENT (Super Admin only)
# ============================================================
@superadmin_bp.route("/api/users", methods=["GET"])
@super_admin_required
def api_users_list():
    """Get all users."""
    try:
        from database import get_all_users
        users = get_all_users()
        result = []
        for u in users:
            item = dict(u)
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            result.append(item)
        return jsonify({"success": True, "users": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@superadmin_bp.route("/api/users", methods=["POST"])
@super_admin_required
def api_users_create():
    """Create new user."""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        role = data.get("role", "").strip()
        nama_lengkap = data.get("nama_lengkap", "").strip()

        if not username:
            return jsonify({"success": False, "error": "Username harus diisi."}), 400
        if not password:
            return jsonify({"success": False, "error": "Password harus diisi."}), 400
        if len(password) < 8:
            return jsonify({"success": False, "error": "Password minimal 8 karakter."}), 400
        if role not in ("admin", "dokter"):
            return jsonify({"success": False, "error": "Role harus admin atau dokter."}), 400
        if not nama_lengkap:
            return jsonify({"success": False, "error": "Nama lengkap harus diisi."}), 400
        if any(char.isdigit() for char in nama_lengkap):
            return jsonify({"success": False, "error": "Nama lengkap tidak boleh mengandung angka."}), 400

        from database import is_username_taken, create_user
        if is_username_taken(username):
            return jsonify({"success": False, "error": "Username sudah digunakan."}), 400

        user_id = create_user(username, password, role, nama_lengkap)
        return jsonify({"success": True, "user_id": user_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@superadmin_bp.route("/api/users/<int:user_id>", methods=["GET"])
@super_admin_required
def api_users_get(user_id):
    """Get single user detail."""
    try:
        from database import get_user_detail
        user = get_user_detail(user_id)
        if not user:
            return jsonify({"success": False, "error": "User tidak ditemukan."}), 404
        item = dict(user)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        return jsonify({"success": True, "user": item})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@superadmin_bp.route("/api/users/<int:user_id>", methods=["PUT"])
@super_admin_required
def api_users_update(user_id):
    """Update user."""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        role = data.get("role", "").strip()
        nama_lengkap = data.get("nama_lengkap", "").strip()
        password = data.get("password", "").strip() or None

        if not username:
            return jsonify({"success": False, "error": "Username harus diisi."}), 400
        if role not in ("admin", "dokter"):
            return jsonify({"success": False, "error": "Role harus admin atau dokter."}), 400
        if not nama_lengkap:
            return jsonify({"success": False, "error": "Nama lengkap harus diisi."}), 400
        if any(char.isdigit() for char in nama_lengkap):
            return jsonify({"success": False, "error": "Nama lengkap tidak boleh mengandung angka."}), 400
        if password and len(password) < 8:
            return jsonify({"success": False, "error": "Password minimal 8 karakter."}), 400

        from database import is_username_taken, update_user, get_user_detail

        # Cek user ada
        existing = get_user_detail(user_id)
        if not existing:
            return jsonify({"success": False, "error": "User tidak ditemukan."}), 404

        # Jangan izinkan edit super_admin
        if existing["role"] == "super_admin":
            return jsonify({"success": False, "error": "Tidak bisa mengedit akun super admin."}), 403

        if is_username_taken(username, exclude_id=user_id):
            return jsonify({"success": False, "error": "Username sudah digunakan."}), 400

        update_user(user_id, username, role, nama_lengkap, password)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@superadmin_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
@super_admin_required
def api_users_delete(user_id):
    """Delete user."""
    try:
        from database import get_user_detail, delete_user as db_delete_user

        # Cek user ada
        existing = get_user_detail(user_id)
        if not existing:
            return jsonify({"success": False, "error": "User tidak ditemukan."}), 404

        # Jangan izinkan hapus super_admin
        if existing["role"] == "super_admin":
            return jsonify({"success": False, "error": "Tidak bisa menghapus akun super admin."}), 403

        # Jangan izinkan hapus diri sendiri
        if user_id == session.get("user_id"):
            return jsonify({"success": False, "error": "Tidak bisa menghapus akun sendiri."}), 400

        db_delete_user(user_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
