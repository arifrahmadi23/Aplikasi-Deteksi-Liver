"""
Routes — Detection (AI Pipeline + Save + History)
API untuk menjalankan pipeline AI, menyimpan hasil, dan riwayat.
"""

import os
import io
import uuid
import time
import base64

from flask import Blueprint, request, jsonify, session
from PIL import Image

from .auth import login_required, admin_required

detection_bp = Blueprint("detection", __name__)

# Temp storage for detection results (in-memory, keyed by detection_id)
# In production, use Redis or similar. This is fine for single-user usage.
_detection_cache = {}

# Singleton for ML pipeline
_detector = None


# ============================================================
#  HELPERS
# ============================================================
def get_detector():
    """Lazy-load the hybrid detector pipeline."""
    global _detector
    if _detector is None:
        print("[LOADING] AI pipeline (YOLOv11 + ResNet50 + XGBoost)...")
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from pipeline import HybridDetector
        _detector = HybridDetector(
            yolo_path=os.path.join(BASE_DIR, "best.pt"),
            xgb_path=os.path.join(BASE_DIR, "xgb_model.pkl"),
        )
        print("[OK] Pipeline loaded successfully!")
    return _detector


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


# ============================================================
#  API: DETECT (Admin only)
# ============================================================
@detection_bp.route("/api/detect", methods=["POST"])
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

        # Validate image file type (extension + MIME)
        ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'}
        ALLOWED_MIMETYPES = {'image/jpeg', 'image/png', 'image/tiff', 'image/bmp'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                "success": False,
                "error": "Format file tidak didukung! Hanya file gambar (JPG, PNG, TIFF, BMP) yang diperbolehkan."
            }), 400
        if file.content_type and file.content_type not in ALLOWED_MIMETYPES:
            return jsonify({
                "success": False,
                "error": "Tipe file tidak valid! Hanya file gambar (JPG, PNG, TIFF, BMP) yang diperbolehkan."
            }), 400

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
            "db_available": True,
        }

        return jsonify(response)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
#  API: SAVE TO DATABASE (Admin only)
# ============================================================
@detection_bp.route("/api/save", methods=["POST"])
@admin_required
def api_save():
    """Save cached detection results to MySQL database."""
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
@detection_bp.route("/api/history", methods=["GET"])
@login_required
def api_history():
    """Get all saved analyses."""
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


@detection_bp.route("/api/history/<int:analysis_id>", methods=["GET"])
@login_required
def api_history_detail(analysis_id):
    """Get detail of a specific analysis."""
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


@detection_bp.route("/api/history/<int:analysis_id>", methods=["DELETE"])
@admin_required
def api_history_delete(analysis_id):
    """Delete an analysis."""
    try:
        from database import delete_analysis
        delete_analysis(analysis_id)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
