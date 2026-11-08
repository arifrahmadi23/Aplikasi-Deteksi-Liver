"""
Routes — Doctor (Pages + Diagnosis API)
Halaman dokter dan API diagnosa.
"""

import traceback
from flask import Blueprint, render_template, request, jsonify, session
from .auth import doctor_required

doctor_bp = Blueprint("doctor", __name__)


# ============================================================
#  DOCTOR PAGE ROUTES
# ============================================================
@doctor_bp.route("/doctor/dashboard")
@doctor_required
def doctor_dashboard():
    """Doctor dashboard."""
    return render_template("doctor_dashboard.html")


@doctor_bp.route("/doctor/results/<int:analysis_id>")
@doctor_required
def doctor_detail(analysis_id):
    """Doctor detail view for a specific analysis."""
    return render_template("doctor_detail.html", analysis_id=analysis_id)


# ============================================================
#  API: DIAGNOSIS (Doctor only)
# ============================================================
@doctor_bp.route("/api/diagnosis", methods=["POST"])
@doctor_required
def api_diagnosis_save():
    """Save or update doctor's diagnosis for an analysis."""
    try:
        data = request.get_json()
        analysis_id = data.get("analysis_id")
        diagnosa = data.get("diagnosa", "").strip()
        tindakan = data.get("tindakan", "").strip()
        catatan = data.get("catatan", "").strip() or None

        if not analysis_id:
            return jsonify({"success": False, "error": "analysis_id harus diisi."}), 400
        if not diagnosa:
            return jsonify({"success": False, "error": "Diagnosa harus diisi."}), 400
        if not tindakan:
            return jsonify({"success": False, "error": "Tindakan harus dipilih."}), 400

        from database import save_diagnosis
        diagnosis_id = save_diagnosis(
            analysis_id=analysis_id,
            doctor_id=session.get("user_id"),
            diagnosa=diagnosa,
            tindakan=tindakan,
            catatan=catatan,
        )

        return jsonify({"success": True, "diagnosis_id": diagnosis_id})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
