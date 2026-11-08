"""
Database Schema & Initialization
Membuat database, tabel, dan seed default users.
"""

from werkzeug.security import generate_password_hash
from .connection import get_connection, _ensure_dirs, DB_NAME


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
