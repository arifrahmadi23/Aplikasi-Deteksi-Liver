"""
Database — Diagnosis Functions
Menyimpan dan mengambil diagnosa dokter.
"""

from .connection import get_connection


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
