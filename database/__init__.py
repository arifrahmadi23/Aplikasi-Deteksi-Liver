"""
Database Package — LiverScope AI
Re-export semua fungsi publik agar backward compatible.

Penggunaan tetap sama:
    from database import init_db
    from database import get_user_by_username, verify_password
    from database import create_patient, get_all_patients
    dll.
"""

# Schema & Init
from .schema import init_db, seed_default_users

# User functions
from .users import (
    get_user_by_username,
    get_user_by_id,
    verify_password,
    get_all_users,
    get_user_detail,
    create_user,
    update_user,
    delete_user,
    is_username_taken,
)

# Patient functions
from .patients import (
    create_patient,
    get_all_patients,
    get_patient,
    update_patient,
    delete_patient,
)

# Analysis functions
from .analyses import (
    save_analysis,
    get_all_analyses,
    get_analysis_detail,
    delete_analysis,
    get_analysis_count,
)

# Diagnosis functions
from .diagnoses import (
    save_diagnosis,
    get_diagnosis,
)
