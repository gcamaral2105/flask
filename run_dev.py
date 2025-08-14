"""
Development Server Script
========================

Script for running the ERP Bauxita application in development mode.
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db

def create_dev_app():
    """Create Flask app for development."""
    app = create_app('config.DevelopmentConfig')
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        # Print startup information
        print("=" * 60)
        print("🚀 ERP Bauxita Development Server")
        print("=" * 60)
        print(f"📍 Server: http://localhost:{app.config.get('PORT', 5000)}")
        print(f"🔧 Debug Mode: {app.config.get('DEBUG', False)}")
        print(f"💾 Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///app.db')}")
        print()
        print("📚 API Documentation:")
        print("   • Authentication: /api/v1/auth/")
        print("   • Productions:    /api/v1/productions/")
        print("   • Vessels:        /api/v1/vessels/")
        print("   • Partners:       /api/v1/partners/")
        print()
        print("👥 Default Users:")
        print("   • admin/admin123     (Admin)")
        print("   • operator/operator123 (Operator)")
        print("   • viewer/viewer123   (Viewer)")
        print()
        print("📖 Full documentation: README.md")
        print("=" * 60)
    
    return app

if __name__ == '__main__':
    # Configuration
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Create and run app
    app = create_dev_app()
    app.run(host=host, port=port, debug=debug)
