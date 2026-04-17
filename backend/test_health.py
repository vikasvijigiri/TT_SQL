import os
import sys

# Add backend to path
sys.path.append(os.getcwd())

try:
    from app.repositories.config import settings
    from app.services.utils.health_service import HealthService
    
    print(f"Active Project ID: {settings.ACTIVE_PROJECT_ID}")
    print(f"DB Type: {settings.DB_TYPE}")
    
    is_ok = HealthService.check_db_connection()
    print(f"Health Check result: {is_ok}")
except Exception as e:
    import traceback
    traceback.print_exc()
