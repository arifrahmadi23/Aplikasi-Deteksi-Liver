"""
Routes Package — LiverScope AI
Mendaftarkan semua Blueprints ke Flask app.
"""

from .auth import auth_bp
from .admin import admin_bp
from .detection import detection_bp
from .doctor import doctor_bp
from .superadmin import superadmin_bp


def register_blueprints(app):
    """Register semua blueprint ke Flask app."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(detection_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(superadmin_bp)
