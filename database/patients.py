"""
Database — Patient Functions
CRUD operasi untuk tabel patients.
"""

from .connection import get_connection


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
