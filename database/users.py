"""
Database — User Functions
CRUD operasi untuk tabel users dan autentikasi.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from .connection import get_connection


# ============================================================
#  AUTH FUNCTIONS
# ============================================================
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
