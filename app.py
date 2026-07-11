"""
LiverScope AI — Flask Backend
Pipeline Hybrid: YOLOv11 → ResNet50 → XGBoost
Multi-Actor: Admin (CRUD Pasien + Deteksi) & Dokter (Diagnosa)
Dengan Database MySQL (Laragon)
"""

import os
import io
import uuid
import time
import base64
import json
from functools import wraps
from flask import (Flask, render_template, request, jsonify,
                   send_from_directory, session, redirect, url_for)

from PIL import Image

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

# Temp storage for detection results (in-memory, keyed by detection_id)
# In production, use Redis or similar. This is fine for single-user usage.
_detection_cache = {}

# ============================================================
#  LOAD ML PIPELINE (singleton)
# ============================================================
_detector = None


def get_detector():
    """Lazy-load the hybrid detector pipeline."""
    global _detector
    if _detector is None:
        print("[LOADING] AI pipeline (YOLOv11 + ResNet50 + XGBoost)...")
        from pipeline import HybridDetector
        _detector = HybridDetector(
            yolo_path=os.path.join(BASE_DIR, "best.pt"),
            xgb_path=os.path.join(BASE_DIR, "xgb_model.pkl"),
        )
        print("[OK] Pipeline loaded successfully!")
    return _detector


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
#  AUTH DECORATORS
# ============================================================
def login_required(f):
    """Decorator: halaman memerlukan login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: halaman khusus admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        if session.get("role") != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya admin."}), 403
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def doctor_required(f):
    """Decorator: halaman khusus dokter."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        if session.get("role") != "dokter":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya dokter."}), 403
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    """Decorator: halaman khusus super admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for("login_page"))
        if session.get("role") != "super_admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Akses ditolak. Hanya super admin."}), 403
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ============================================================
#  HELPER FUNCTIONS
# ============================================================
def pil_to_base64(img, fmt="JPEG", quality=90):
    """Convert PIL Image to base64 data URL."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/{fmt.lower()};base64,{b64}"


def serialize_detections(detections):
    """Convert detection results to JSON-serializable format."""
    result = []
    for det in detections:
        d = {
            "bbox": det["bbox"],
            "yolo_class": det["yolo_class"],
            "yolo_conf": det["yolo_conf"],
            "xgb_class": det["xgb_class"],
            "xgb_conf": det["xgb_conf"],
            "crop_url": pil_to_base64(det["crop"]),
        }
        result.append(d)
    return result


def validate_patient_data(data):
    """Validate patient data fields. Returns (is_valid, error_message)."""
    import re

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
@app.route("/")
def root():
    """Render landing page."""
    return render_template("landing.html")



@app.route("/login")
def login_page():
    """Login page."""
    if "user_id" in session:
        return redirect(url_for("root"))
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    """Login API."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503

    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "Username dan password harus diisi."}), 400

    from database import get_user_by_username, verify_password
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
        redirect_url = url_for("superadmin_users")
    elif user["role"] == "admin":
        redirect_url = url_for("admin_detect")
    else:
        redirect_url = url_for("doctor_dashboard")

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


@app.route("/logout")
def logout():
    """Logout."""
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/api/me")
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


# ============================================================
#  ADMIN PAGE ROUTES
# ============================================================
@app.route("/admin/detect")
@admin_required
def admin_detect():
    """Detection page - Admin only."""
    return render_template("index.html")


@app.route("/admin/patients")
@admin_required
def admin_patients():
    """Patient management page - Admin only."""
    return render_template("patients.html")


@app.route("/admin/history")
@admin_required
def admin_history():
    """History page - Admin only."""
    return render_template("history.html")


# ============================================================
#  DOCTOR PAGE ROUTES
# ============================================================
@app.route("/doctor/dashboard")
@doctor_required
def doctor_dashboard():
    """Doctor dashboard."""
    return render_template("doctor_dashboard.html")


@app.route("/doctor/results/<int:analysis_id>")
@doctor_required
def doctor_detail(analysis_id):
    """Doctor detail view for a specific analysis."""
    return render_template("doctor_detail.html", analysis_id=analysis_id)


# ============================================================
#  SUPER ADMIN PAGE ROUTES
# ============================================================
@app.route("/superadmin/users")
@super_admin_required
def superadmin_users():
    """User management page - Super Admin only."""
    return render_template("users.html")


# ============================================================
#  API: USER MANAGEMENT (Super Admin only)
# ============================================================
@app.route("/api/users", methods=["GET"])
@super_admin_required
def api_users_list():
    """Get all users."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/users", methods=["POST"])
@super_admin_required
def api_users_create():
    """Create new user."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/users/<int:user_id>", methods=["GET"])
@super_admin_required
def api_users_get(user_id):
    """Get single user detail."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/users/<int:user_id>", methods=["PUT"])
@super_admin_required
def api_users_update(user_id):
    """Update user."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@super_admin_required
def api_users_delete(user_id):
    """Delete user."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


# ============================================================
#  SERVE UPLOADED IMAGES
# ============================================================
@app.route("/uploads/<path:filepath>")
@login_required
def serve_upload(filepath):
    """Serve images from uploads directory."""
    uploads_dir = os.path.join(BASE_DIR, "uploads")
    return send_from_directory(uploads_dir, filepath)


# ============================================================
#  API: PATIENTS (Admin only)
# ============================================================
@app.route("/api/patients", methods=["GET"])
@admin_required
def api_patients_list():
    """Get all patients."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/patients", methods=["POST"])
@admin_required
def api_patients_create():
    """Create new patient."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/patients/<int:patient_id>", methods=["GET"])
@admin_required
def api_patients_get(patient_id):
    """Get single patient."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/patients/<int:patient_id>", methods=["PUT"])
@admin_required
def api_patients_update(patient_id):
    """Update patient."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
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


@app.route("/api/patients/<int:patient_id>", methods=["DELETE"])
@admin_required
def api_patients_delete(patient_id):
    """Delete patient."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503
    try:
        from database import delete_patient
        delete_patient(patient_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
#  API: DETECT (Admin only)
# ============================================================
@app.route("/api/detect", methods=["POST"])
@admin_required
def api_detect():
    """
    Run the hybrid detection pipeline on an uploaded image.
    Returns JSON with detection results, metrics, and image URLs.
    """
    try:
        # Validate input
        if "image" not in request.files:
            return jsonify({"success": False, "error": "No image uploaded"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "error": "Empty filename"}), 400

        patient_id = request.form.get("patient_id")
        if not patient_id:
            return jsonify({"success": False, "error": "Pilih pasien terlebih dahulu."}), 400

        conf_threshold = 0.05  # Fixed low threshold — filtering by XGBoost confidence is done on frontend

        # Open image
        image = Image.open(file.stream).convert("RGB")

        # Run pipeline
        detector = get_detector()
        start_time = time.time()
        detections = detector.detect(image, conf_threshold=conf_threshold)
        elapsed = time.time() - start_time

        # Calculate metrics
        from utils import calculate_summary_metrics, draw_detections, get_class_distribution
        from pipeline import CLASS_DESCRIPTIONS, CLASS_COLORS_HEX

        metrics = calculate_summary_metrics(detections)
        annotated_image = draw_detections(image, detections, use_xgb_label=True)
        distribution = get_class_distribution(detections, use_xgb=True)

        # Generate unique detection ID for caching
        detection_id = uuid.uuid4().hex[:12]

        # Cache for later save
        _detection_cache[detection_id] = {
            "filename": file.filename,
            "original_image": image,
            "annotated_image": annotated_image,
            "detections": detections,
            "metrics": metrics,
            "processing_time": elapsed,
            "conf_threshold": conf_threshold,
            "patient_id": int(patient_id),
        }

        # Build response
        response = {
            "success": True,
            "detection_id": detection_id,
            "processing_time": round(elapsed, 2),
            "metrics": metrics,
            "original_image": pil_to_base64(image),
            "annotated_image": pil_to_base64(annotated_image),
            "detections": serialize_detections(detections),
            "distribution": distribution,
            "class_colors": CLASS_COLORS_HEX,
            "class_descriptions": CLASS_DESCRIPTIONS,
            "db_available": _db_ready,
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
#  API: SAVE TO DATABASE (Admin only)
# ============================================================
@app.route("/api/save", methods=["POST"])
@admin_required
def api_save():
    """Save cached detection results to MySQL database."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia. Pastikan Laragon/MySQL berjalan."}), 503

    try:
        data = request.get_json()
        detection_id = data.get("detection_id")

        if not detection_id or detection_id not in _detection_cache:
            return jsonify({"success": False, "error": "Hasil deteksi tidak ditemukan atau sudah expired."}), 404

        cached = _detection_cache[detection_id]

        from database import save_analysis
        analysis_id = save_analysis(
            filename=cached["filename"],
            original_image=cached["original_image"],
            annotated_image=cached["annotated_image"],
            detections=cached["detections"],
            metrics=cached["metrics"],
            processing_time=cached["processing_time"],
            conf_threshold=cached["conf_threshold"],
            patient_id=cached.get("patient_id"),
            created_by=session.get("user_id"),
        )

        # Clean up cache
        del _detection_cache[detection_id]

        return jsonify({"success": True, "analysis_id": analysis_id})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
#  API: HISTORY
# ============================================================
@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    """Get all saved analyses."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503

    try:
        from database import get_all_analyses
        analyses = get_all_analyses()

        # Serialize datetime fields
        result = []
        for a in analyses:
            item = dict(a)
            if item.get("created_at"):
                item["created_at"] = item["created_at"].isoformat()
            result.append(item)

        return jsonify({"success": True, "analyses": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history/<int:analysis_id>", methods=["GET"])
@login_required
def api_history_detail(analysis_id):
    """Get detail of a specific analysis."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503

    try:
        from database import get_analysis_detail
        analysis, detections, diagnosis = get_analysis_detail(analysis_id)

        if analysis is None:
            return jsonify({"success": False, "error": "Analisis tidak ditemukan."}), 404

        # Serialize
        a = dict(analysis)
        if a.get("created_at"):
            a["created_at"] = a["created_at"].isoformat()
        if a.get("patient_dob"):
            a["patient_dob"] = a["patient_dob"].isoformat()

        dets = [dict(d) for d in detections]

        diag = None
        if diagnosis:
            diag = dict(diagnosis)
            if diag.get("created_at"):
                diag["created_at"] = diag["created_at"].isoformat()
            if diag.get("updated_at"):
                diag["updated_at"] = diag["updated_at"].isoformat()

        return jsonify({
            "success": True,
            "analysis": a,
            "detections": dets,
            "diagnosis": diag,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history/<int:analysis_id>", methods=["DELETE"])
@admin_required
def api_history_delete(analysis_id):
    """Delete an analysis."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503

    try:
        from database import delete_analysis
        delete_analysis(analysis_id)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
#  API: DIAGNOSIS (Doctor only)
# ============================================================
@app.route("/api/diagnosis", methods=["POST"])
@doctor_required
def api_diagnosis_save():
    """Save or update doctor's diagnosis for an analysis."""
    if not _db_ready:
        return jsonify({"success": False, "error": "Database tidak tersedia."}), 503

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
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


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
