"""
Database — Analysis Functions
Menyimpan, mengambil, dan menghapus hasil analisis deteksi.
"""

import os
import uuid
from datetime import datetime

from .connection import get_connection, _ensure_dirs, BASE_DIR, ORIGINAL_DIR, ANNOTATED_DIR, CROPS_DIR


def save_analysis(filename, original_image, annotated_image, detections,
                  metrics, processing_time, conf_threshold,
                  patient_id=None, created_by=None):
    """
    Simpan hasil analisis ke database dan gambar ke folder.

    Args:
        filename: Nama file asli
        original_image: PIL Image gambar asli
        annotated_image: PIL Image gambar dengan bounding box
        detections: List hasil dari HybridDetector.detect()
        metrics: Dict dari calculate_summary_metrics()
        processing_time: Waktu proses (detik)
        conf_threshold: Confidence threshold yang digunakan
        patient_id: ID pasien (opsional)
        created_by: ID user yang melakukan deteksi (opsional)

    Returns:
        analysis_id: ID record yang disimpan
    """
    _ensure_dirs()

    # Generate unique ID untuk file
    uid = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]

    # Simpan gambar asli
    orig_filename = f"{uid}_original.jpg"
    orig_path = os.path.join(ORIGINAL_DIR, orig_filename)
    original_image.save(orig_path, "JPEG", quality=95)

    # Simpan gambar annotated
    annot_filename = f"{uid}_annotated.jpg"
    annot_path = os.path.join(ANNOTATED_DIR, annot_filename)
    annotated_image.save(annot_path, "JPEG", quality=95)

    # Simpan ke database
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Insert analysis
            cursor.execute("""
                INSERT INTO `analyses`
                    (`patient_id`, `created_by`, `filename`, `image_path`, `annotated_image_path`,
                     `total_detections`, `avg_conf_yolo`, `avg_conf_xgb`,
                     `agreement_rate`, `processing_time`, `conf_threshold`,
                     `dominant_class`)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                patient_id,
                created_by,
                filename,
                f"uploads/original/{orig_filename}",
                f"uploads/annotated/{annot_filename}",
                metrics["total_deteksi"],
                metrics["rata_conf_yolo"],
                metrics["rata_conf_xgb"],
                metrics["agreement_rate"],
                processing_time,
                conf_threshold,
                metrics["kelas_dominan"],
            ))
            analysis_id = cursor.lastrowid

            # Insert detections
            for i, det in enumerate(detections):
                # Simpan crop image
                crop_filename = f"{uid}_crop_{i}.jpg"
                crop_path = os.path.join(CROPS_DIR, crop_filename)
                det["crop"].save(crop_path, "JPEG", quality=90)

                cursor.execute("""
                    INSERT INTO `detections`
                        (`analysis_id`, `yolo_class`, `yolo_conf`,
                         `xgb_class`, `xgb_conf`,
                         `bbox_x1`, `bbox_y1`, `bbox_x2`, `bbox_y2`,
                         `crop_image_path`)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    analysis_id,
                    det["yolo_class"],
                    det["yolo_conf"],
                    det["xgb_class"],
                    det["xgb_conf"],
                    det["bbox"][0], det["bbox"][1],
                    det["bbox"][2], det["bbox"][3],
                    f"uploads/crops/{crop_filename}",
                ))

        conn.commit()
        return analysis_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_all_analyses():
    """Ambil semua riwayat analisis dengan info pasien, terbaru di atas."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT a.*, p.nama as patient_name, p.nik as patient_nik,
                       u.nama_lengkap as created_by_name,
                       CASE WHEN dd.id IS NOT NULL THEN 1 ELSE 0 END as has_diagnosis
                FROM `analyses` a
                LEFT JOIN `patients` p ON a.patient_id = p.id
                LEFT JOIN `users` u ON a.created_by = u.id
                LEFT JOIN `doctor_diagnoses` dd ON a.id = dd.analysis_id
                ORDER BY a.`created_at` DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()


def get_analysis_detail(analysis_id):
    """Ambil detail satu analisis beserta deteksi-deteksinya."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Ambil analysis dengan info pasien
            cursor.execute("""
                SELECT a.*, p.nama as patient_name, p.nik as patient_nik,
                       p.tanggal_lahir as patient_dob, p.jenis_kelamin as patient_gender,
                       p.alamat as patient_alamat, p.telepon as patient_telepon,
                       u.nama_lengkap as created_by_name
                FROM `analyses` a
                LEFT JOIN `patients` p ON a.patient_id = p.id
                LEFT JOIN `users` u ON a.created_by = u.id
                WHERE a.`id` = %s
            """, (analysis_id,))
            analysis = cursor.fetchone()

            if analysis is None:
                return None, [], None

            # Ambil detections
            cursor.execute(
                "SELECT * FROM `detections` WHERE `analysis_id` = %s ORDER BY `id`",
                (analysis_id,)
            )
            detections = cursor.fetchall()

            # Ambil diagnosis (jika ada)
            cursor.execute("""
                SELECT dd.*, u.nama_lengkap as doctor_name
                FROM `doctor_diagnoses` dd
                LEFT JOIN `users` u ON dd.doctor_id = u.id
                WHERE dd.`analysis_id` = %s
            """, (analysis_id,))
            diagnosis = cursor.fetchone()

            return analysis, detections, diagnosis
    finally:
        conn.close()


def delete_analysis(analysis_id):
    """Hapus analisis beserta gambar terkait dari database dan folder."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Ambil path gambar sebelum hapus
            cursor.execute("SELECT `image_path`, `annotated_image_path` FROM `analyses` WHERE `id` = %s", (analysis_id,))
            analysis = cursor.fetchone()

            cursor.execute("SELECT `crop_image_path` FROM `detections` WHERE `analysis_id` = %s", (analysis_id,))
            crops = cursor.fetchall()

            # Hapus dari database (CASCADE akan hapus detections juga)
            cursor.execute("DELETE FROM `analyses` WHERE `id` = %s", (analysis_id,))
        conn.commit()

        # Hapus file gambar
        if analysis:
            for key in ["image_path", "annotated_image_path"]:
                path = os.path.join(BASE_DIR, analysis[key]) if analysis[key] else None
                if path and os.path.exists(path):
                    os.remove(path)

        for crop in crops:
            path = os.path.join(BASE_DIR, crop["crop_image_path"]) if crop["crop_image_path"] else None
            if path and os.path.exists(path):
                os.remove(path)

        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_analysis_count():
    """Hitung total jumlah analisis."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM `analyses`")
            result = cursor.fetchone()
            return result["total"] if result else 0
    finally:
        conn.close()
