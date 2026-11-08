"""
Routes — Admin (Pages + Patient API)
Halaman admin dan API CRUD pasien.
"""

from flask import Blueprint, render_template, request, jsonify
from .auth import admin_required, validate_patient_data

admin_bp = Blueprint("admin", __name__)


# ============================================================
#  ADMIN PAGE ROUTES
# ============================================================
@admin_bp.route("/admin/detect")
@admin_required
def admin_detect():
    """Detection page - Admin only."""
    return render_template("index.html")


@admin_bp.route("/admin/patients")
@admin_required
def admin_patients():
    """Patient management page - Admin only."""
    return render_template("patients.html")


@admin_bp.route("/admin/history")
@admin_required
def admin_history():
    """History page - Admin only."""
    return render_template("history.html")


# ============================================================
#  API: PATIENTS (Admin only)
# ============================================================
@admin_bp.route("/api/patients", methods=["GET"])
@admin_required
def api_patients_list():
    """Get all patients."""
    try:
        from database import get_all_patients
        patients = get_all_patients()
        result = []
        for p in patients:
            item = dict(p)
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            if item.get("updated_at"):
                item["updated_at"] = item["updated_at"].isoformat()
            if item.get("tanggal_lahir"):
                item["tanggal_lahir"] = item["tanggal_lahir"].isoformat()
            result.append(item)
        return jsonify({"success": True, "patients": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/patients", methods=["POST"])
@admin_required
def api_patients_create():
    """Create new patient."""
    try:
        data = request.get_json()

        # Validasi data pasien
        is_valid, error_msg = validate_patient_data(data)
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        nama = data.get("nama", "").strip()
        from database import create_patient
        patient_id = create_patient(
            nama=nama,
            nik=data.get("nik", "").strip() or None,
            tanggal_lahir=data.get("tanggal_lahir") or None,
            jenis_kelamin=data.get("jenis_kelamin", "Laki-laki"),
            alamat=data.get("alamat", "").strip() or None,
            telepon=data.get("telepon", "").strip() or None,
        )
        return jsonify({"success": True, "patient_id": patient_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/patients/<int:patient_id>", methods=["GET"])
@admin_required
def api_patients_get(patient_id):
    """Get single patient."""
    try:
        from database import get_patient
        patient = get_patient(patient_id)
        if not patient:
            return jsonify({"success": False, "error": "Pasien tidak ditemukan."}), 404
        item = dict(patient)
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()
        if item.get("updated_at"):
            item["updated_at"] = item["updated_at"].isoformat()
        if item.get("tanggal_lahir"):
            item["tanggal_lahir"] = item["tanggal_lahir"].isoformat()
        return jsonify({"success": True, "patient": item})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/patients/<int:patient_id>", methods=["PUT"])
@admin_required
def api_patients_update(patient_id):
    """Update patient."""
    try:
        data = request.get_json()

        # Validasi data pasien
        is_valid, error_msg = validate_patient_data(data)
        if not is_valid:
            return jsonify({"success": False, "error": error_msg}), 400

        nama = data.get("nama", "").strip()
        from database import update_patient
        update_patient(
            patient_id=patient_id,
            nama=nama,
            nik=data.get("nik", "").strip() or None,
            tanggal_lahir=data.get("tanggal_lahir") or None,
            jenis_kelamin=data.get("jenis_kelamin", "Laki-laki"),
            alamat=data.get("alamat", "").strip() or None,
            telepon=data.get("telepon", "").strip() or None,
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/api/patients/<int:patient_id>", methods=["DELETE"])
@admin_required
def api_patients_delete(patient_id):
    """Delete patient."""
    try:
        from database import delete_patient
        delete_patient(patient_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
