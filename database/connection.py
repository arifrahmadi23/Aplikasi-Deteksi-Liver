"""
Database Connection & Configuration
Konfigurasi koneksi MySQL dan path penyimpanan file.
"""

import os
import pymysql


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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
