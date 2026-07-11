"""
Database Module - MySQL (Laragon/phpMyAdmin)
Menyimpan dan mengelola riwayat analisis deteksi histopatologi liver.
Mendukung multi-aktor: Super Admin, Admin, dan Dokter.
"""

import os
import pymysql
from datetime import datetime
from PIL import Image
import io
import uuid
from werkzeug.security import generate_password_hash, check_password_hash


# Konfigurasi database (Laragon default)
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

DB_NAME = "liver_detection"

# Folder penyimpanan gambar
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ORIGINAL_DIR = os.path.join(UPLOAD_DIR, "original")
ANNOTATED_DIR = os.path.join(UPLOAD_DIR, "annotated")
CROPS_DIR = os.path.join(UPLOAD_DIR, "crops")


def _ensure_dirs():
    """Buat folder uploads jika belum ada."""
    for d in [UPLOAD_DIR, ORIGINAL_DIR, ANNOTATED_DIR, CROPS_DIR]:
        os.makedirs(d, exist_ok=True)


def get_connection(use_db=True):
    """Buat koneksi ke MySQL."""
    config = DB_CONFIG.copy()
    if use_db:
        config["database"] = DB_NAME
    return pymysql.connect(**config)


def init_db():
    """Buat database dan tabel jika belum ada."""
    _ensure_dirs()

    # Buat database
    conn = get_connection(use_db=False)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    # Buat tabel
    conn = get_connection(use_db=True)
    try:
        with conn.cursor() as cursor:
            # Tabel users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `users` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `username` VARCHAR(100) NOT NULL UNIQUE,
                    `password_hash` VARCHAR(255) NOT NULL,
                    `role` ENUM('super_admin', 'admin', 'dokter') NOT NULL,
                    `nama_lengkap` VARCHAR(255) NOT NULL,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Migrasi: tambah super_admin ke ENUM role (untuk DB yang sudah ada)
            try:
                cursor.execute("""
                    ALTER TABLE `users`
                    MODIFY COLUMN `role` ENUM('super_admin', 'admin', 'dokter') NOT NULL
                """)
            except Exception:
                pass  # Sudah terbaru

            # Tabel patients
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `patients` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `nama` VARCHAR(255) NOT NULL,
                    `nik` VARCHAR(50),
                    `tanggal_lahir` DATE,
                    `jenis_kelamin` ENUM('Laki-laki', 'Perempuan') DEFAULT 'Laki-laki',
                    `alamat` TEXT,
                    `telepon` VARCHAR(20),
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Tabel analyses (ringkasan per analisis)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `analyses` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `patient_id` INT,
                    `created_by` INT,
                    `filename` VARCHAR(255) NOT NULL,
                    `image_path` VARCHAR(500),
                    `annotated_image_path` VARCHAR(500),
                    `total_detections` INT DEFAULT 0,
                    `avg_conf_yolo` FLOAT DEFAULT 0,
                    `avg_conf_xgb` FLOAT DEFAULT 0,
                    `agreement_rate` FLOAT DEFAULT 0,
                    `processing_time` FLOAT DEFAULT 0,
                    `conf_threshold` FLOAT DEFAULT 0.25,
                    `dominant_class` VARCHAR(100),
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (`patient_id`) REFERENCES `patients`(`id`)
                        ON DELETE SET NULL,
                    FOREIGN KEY (`created_by`) REFERENCES `users`(`id`)
                        ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Tabel detections (detail per objek terdeteksi)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `detections` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `analysis_id` INT NOT NULL,
                    `yolo_class` VARCHAR(100) NOT NULL,
                    `yolo_conf` FLOAT DEFAULT 0,
                    `xgb_class` VARCHAR(100) NOT NULL,
                    `xgb_conf` FLOAT DEFAULT 0,
                    `bbox_x1` INT DEFAULT 0,
                    `bbox_y1` INT DEFAULT 0,
                    `bbox_x2` INT DEFAULT 0,
                    `bbox_y2` INT DEFAULT 0,
                    `crop_image_path` VARCHAR(500),
                    FOREIGN KEY (`analysis_id`) REFERENCES `analyses`(`id`)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Tabel doctor_diagnoses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS `doctor_diagnoses` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `analysis_id` INT NOT NULL UNIQUE,
                    `doctor_id` INT NOT NULL,
                    `diagnosa` TEXT NOT NULL,
                    `tindakan` VARCHAR(255) NOT NULL,
                    `catatan` TEXT,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (`analysis_id`) REFERENCES `analyses`(`id`)
                        ON DELETE CASCADE,
                    FOREIGN KEY (`doctor_id`) REFERENCES `users`(`id`)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # Tambah kolom patient_id dan created_by ke analyses jika belum ada
            # (untuk migrasi dari versi lama)
            try:
                cursor.execute("ALTER TABLE `analyses` ADD COLUMN `patient_id` INT DEFAULT NULL")
            except Exception:
                pass  # Kolom sudah ada
            try:
                cursor.execute("ALTER TABLE `analyses` ADD COLUMN `created_by` INT DEFAULT NULL")
            except Exception:
                pass  # Kolom sudah ada

        conn.commit()
    finally:
        conn.close()

    # Seed default users
    seed_default_users()


# ============================================================
#  USER FUNCTIONS
# ============================================================
def seed_default_users():
    """Buat user super_admin, admin, dan dokter default jika belum ada."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Cek apakah sudah ada user
            cursor.execute("SELECT COUNT(*) as total FROM `users`")
            result = cursor.fetchone()
            if result["total"] > 0:
                # Pastikan super_admin ada (migrasi dari versi lama)
                cursor.execute("SELECT COUNT(*) as total FROM `users` WHERE `role` = 'super_admin'")
                sa_result = cursor.fetchone()
                if sa_result["total"] == 0:
                    cursor.execute("""
                        INSERT INTO `users` (`username`, `password_hash`, `role`, `nama_lengkap`)
                        VALUES (%s, %s, %s, %s)
                    """, ("superadmin", generate_password_hash("superadmin123"), "super_admin", "Super Administrator"))
                    conn.commit()
                    print("[OK] Super admin created: superadmin/superadmin123")
                return

            # Buat super admin default
            cursor.execute("""
                INSERT INTO `users` (`username`, `password_hash`, `role`, `nama_lengkap`)
                VALUES (%s, %s, %s, %s)
            """, ("superadmin", generate_password_hash("superadmin123"), "super_admin", "Super Administrator"))

            # Buat admin default
            cursor.execute("""
                INSERT INTO `users` (`username`, `password_hash`, `role`, `nama_lengkap`)
                VALUES (%s, %s, %s, %s)
            """, ("admin", generate_password_hash("admin123"), "admin", "Administrator"))

            # Buat dokter default
            cursor.execute("""
                INSERT INTO `users` (`username`, `password_hash`, `role`, `nama_lengkap`)
                VALUES (%s, %s, %s, %s)
            """, ("dokter", generate_password_hash("dokter123"), "dokter", "Dr. Spesialis Patologi"))

        conn.commit()
        print("[OK] Default users created: superadmin/superadmin123, admin/admin123, dokter/dokter123")
    finally:
        conn.close()


def get_user_by_username(username):
    """Ambil user berdasarkan username."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM `users` WHERE `username` = %s", (username,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Ambil user berdasarkan ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT `id`, `username`, `role`, `nama_lengkap`, `created_at` FROM `users` WHERE `id` = %s", (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def verify_password(stored_hash, password):
    """Verifikasi password."""
    return check_password_hash(stored_hash, password)


# ============================================================
#  USER MANAGEMENT FUNCTIONS (Super Admin)
# ============================================================
def get_all_users():
    """Ambil semua user (tanpa password hash)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT `id`, `username`, `role`, `nama_lengkap`, `created_at`
                FROM `users`
                ORDER BY FIELD(`role`, 'super_admin', 'admin', 'dokter'), `created_at` DESC
            """)
            return cursor.fetchall()
    finally:
        conn.close()


def get_user_detail(user_id):
    """Ambil detail user berdasarkan ID (tanpa password hash)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT `id`, `username`, `role`, `nama_lengkap`, `created_at`
                FROM `users` WHERE `id` = %s
            """, (user_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def create_user(username, password, role, nama_lengkap):
    """Buat user baru. Returns user ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO `users` (`username`, `password_hash`, `role`, `nama_lengkap`)
                VALUES (%s, %s, %s, %s)
            """, (username, generate_password_hash(password), role, nama_lengkap))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_user(user_id, username, role, nama_lengkap, password=None):
    """Update data user. Password opsional (jika None, tidak diubah)."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if password:
                cursor.execute("""
                    UPDATE `users`
                    SET `username` = %s, `role` = %s, `nama_lengkap` = %s,
                        `password_hash` = %s
                    WHERE `id` = %s
                """, (username, role, nama_lengkap, generate_password_hash(password), user_id))
            else:
                cursor.execute("""
                    UPDATE `users`
                    SET `username` = %s, `role` = %s, `nama_lengkap` = %s
                    WHERE `id` = %s
                """, (username, role, nama_lengkap, user_id))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_user(user_id):
    """Hapus user berdasarkan ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM `users` WHERE `id` = %s", (user_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def is_username_taken(username, exclude_id=None):
    """Cek apakah username sudah dipakai."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if exclude_id:
                cursor.execute(
                    "SELECT COUNT(*) as total FROM `users` WHERE `username` = %s AND `id` != %s",
                    (username, exclude_id)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as total FROM `users` WHERE `username` = %s",
                    (username,)
                )
            result = cursor.fetchone()
            return result["total"] > 0
    finally:
        conn.close()


# ============================================================
#  PATIENT FUNCTIONS (CRUD)
# ============================================================
def create_patient(nama, nik=None, tanggal_lahir=None, jenis_kelamin="Laki-laki",
                   alamat=None, telepon=None):
    """Tambah data pasien baru."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO `patients` (`nama`, `nik`, `tanggal_lahir`, `jenis_kelamin`, `alamat`, `telepon`)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (nama, nik, tanggal_lahir, jenis_kelamin, alamat, telepon))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_patients():
    """Ambil semua data pasien."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM `patients` ORDER BY `created_at` DESC")
            return cursor.fetchall()
    finally:
        conn.close()


def get_patient(patient_id):
    """Ambil data pasien berdasarkan ID."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM `patients` WHERE `id` = %s", (patient_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def update_patient(patient_id, nama, nik=None, tanggal_lahir=None,
                   jenis_kelamin="Laki-laki", alamat=None, telepon=None):
    """Update data pasien."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE `patients`
                SET `nama` = %s, `nik` = %s, `tanggal_lahir` = %s,
                    `jenis_kelamin` = %s, `alamat` = %s, `telepon` = %s
                WHERE `id` = %s
            """, (nama, nik, tanggal_lahir, jenis_kelamin, alamat, telepon, patient_id))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_patient(patient_id):
    """Hapus data pasien."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM `patients` WHERE `id` = %s", (patient_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ============================================================
#  ANALYSIS FUNCTIONS
# ============================================================
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


# ============================================================
#  DIAGNOSIS FUNCTIONS
# ============================================================
def save_diagnosis(analysis_id, doctor_id, diagnosa, tindakan, catatan=None):
    """Simpan diagnosa dokter untuk suatu analisis."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Cek apakah sudah ada diagnosis untuk analysis ini
            cursor.execute("SELECT `id` FROM `doctor_diagnoses` WHERE `analysis_id` = %s", (analysis_id,))
            existing = cursor.fetchone()

            if existing:
                # Update existing
                cursor.execute("""
                    UPDATE `doctor_diagnoses`
                    SET `doctor_id` = %s, `diagnosa` = %s, `tindakan` = %s, `catatan` = %s
                    WHERE `analysis_id` = %s
                """, (doctor_id, diagnosa, tindakan, catatan, analysis_id))
                diagnosis_id = existing["id"]
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO `doctor_diagnoses` (`analysis_id`, `doctor_id`, `diagnosa`, `tindakan`, `catatan`)
                    VALUES (%s, %s, %s, %s, %s)
                """, (analysis_id, doctor_id, diagnosa, tindakan, catatan))
                diagnosis_id = cursor.lastrowid

        conn.commit()
        return diagnosis_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_diagnosis(analysis_id):
    """Ambil diagnosa untuk suatu analisis."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT dd.*, u.nama_lengkap as doctor_name
                FROM `doctor_diagnoses` dd
                LEFT JOIN `users` u ON dd.doctor_id = u.id
                WHERE dd.`analysis_id` = %s
            """, (analysis_id,))
            return cursor.fetchone()
    finally:
        conn.close()
