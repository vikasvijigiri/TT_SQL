"""
PATH STRUCTURE MIGRATION & DEPLOYMENT GUIDE
============================================

This guide explains how to safely change your application's folder structure
in production without breaking anything.

INDUSTRY-STANDARD APPROACH:
===========================
Our application uses centralized path management through PathStructure class.
To change folder layout, you only need to:

1. Change environment variables in your deployment configuration
2. Application automatically routes all paths through this configuration
3. No code changes required
4. Fully backward compatible

ENVIRONMENT VARIABLES
====================

Set these in your deployment environment (.env file, Docker, K8s, etc.):

- RESULTS_DIR: Override location for results/ folder
  Example: RESULTS_DIR=/data/results
  Default: app/repositories/data/results

- DATA_DIR: Override location for data/ folder  
  Example: DATA_DIR=/var/lib/app/data
  Default: app/repositories/data

- SQLITE_DB_PATH: Override location for SQLite databases
  Example: SQLITE_DB_PATH=/var/lib/databases
  Default: app/repositories/data/sqlite

EXAMPLES
========

Example 1: Move results to external disk
------------------------------------------
Before:
  PROJECT_ROOT/app/repositories/data/results/ (10GB)

After:
  /mnt/data/results/ (10GB)

Action:
  RESULTS_DIR=/mnt/data/results

Example 2: Use Docker volumes
------------------------------
Docker Compose:
  volumes:
    - /host/data:/app/data
  
.env:
  RESULTS_DIR=/app/data/results
  DATA_DIR=/app/data

Example 3: Kubernetes PersistentVolumes
----------------------------------------
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    env:
    - name: RESULTS_DIR
      value: /mnt/pvc/results
    - name: DATA_DIR
      value: /mnt/pvc/data
    volumeMounts:
    - name: data
      mountPath: /mnt/pvc
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: app-data-pvc

MIGRATION STEPS (Live System)
=============================

To migrate from one structure to another while running:

1. BACKUP CURRENT DATA
   - Copy entire results/ folder to backup location
   - Copy any other data directories

2. STOP THE APPLICATION
   - Stop uvicorn/FastAPI server
   - Stop any background workers

3. CREATE NEW DIRECTORY STRUCTURE
   - mkdir -p /new/location/results
   - chmod 755 /new/location

4. COPY DATA
   - cp -r /old/location/results/* /new/location/results/
   - Verify all files copied correctly

5. UPDATE ENVIRONMENT VARIABLES
   - Set RESULTS_DIR=/new/location/results in .env or deployment config

6. RUN STARTUP VALIDATION
   - Start application
   - Call GET /api/health/startup endpoint
   - Should return "status": "ok"

7. VERIFY IN UI
   - Open frontend at localhost:5173
   - Check KB (red icon) should show active projects
   - All project files should be accessible

8. MONITOR LOGS
   - Watch application logs for path-related warnings
   - Check /api/health/paths returns correct locations

TROUBLESHOOTING
===============

Issue: KB icon still red after migration
Solution:
  1. Call GET /api/health/startup - shows any path errors
  2. Check RESULTS_DIR env var is set correctly
  3. Verify file permissions on new directory: chmod 755
  4. Check /api/projects endpoint returns projects
  5. Restart application completely (not just reload)

Issue: Projects disappear after migration
Solution:
  1. Verify results/ folder contains user/project subdirectories
  2. Check that project.json files exist:
     /new/location/results/{user}/{project}/registry/project.json
  3. Call GET /api/projects to verify they're found
  4. Check logs for path scanning errors

Issue: Database can't find SQLite files
Solution:
  1. Set SQLITE_DB_PATH env var to new location
  2. Copy .db/.sqlite files to new location
  3. Restart application
  4. Call GET /api/health/paths to verify database path

AUTOMATIC FOLDER CREATION
=========================

On application startup, the PathStructure validates the structure and:
- Creates missing directories automatically
- Logs warnings for any issues
- Never deletes existing directories (safe)
- Returns validation report via /api/health/startup

NO DOWNTIME MIGRATION
====================

For production systems that can't be stopped:

1. Create new directories in parallel
2. Copy data using background process (rsync, etc.)
3. Once copy complete and verified:
   - Update env vars to point to NEW location
   - Restart application containers (rolling restart)
4. Verify projects appear in UI
5. Keep old directory as backup for 30 days
6. Remove backup after verification period

VERIFICATION CHECKLIST
=====================

After any migration:
- [ ] Application starts without errors
- [ ] GET /api/health/startup returns "status": "ok"
- [ ] GET /api/health/paths shows correct locations
- [ ] GET /api/projects lists all projects
- [ ] Frontend shows project icons (not red)
- [ ] Can create new projects
- [ ] Can list projects in UI
- [ ] Can activate a project
- [ ] Can view database schema
- [ ] Can execute queries
- [ ] RAG/KB features work (if enabled)
- [ ] All file permissions correct (755 on dirs, 644 on files)

ROLLBACK
========

If migration fails:
1. Stop application
2. Revert RESULTS_DIR env var to original location
3. Restart application
4. Verify projects appear again

The application is stateless and can be rolled back instantly.

SUPPORT
=======

For path-related issues:
1. Check application logs for "Path" or "Warning" messages
2. Call GET /api/health/startup for diagnostics
3. Call GET /api/health/paths to see active configuration
4. Verify environment variables: echo $RESULTS_DIR

For custom configurations, edit:
- app/repositories/registry/path_config.py (PathStructure class)
- Add new environment variables
- Override get_*_dir() methods as needed
"""

from pathlib import Path
import os
import sys


def validate_path_structure():
    """
    Called on application startup to validate folder structure.
    """
    try:
        from app.repositories.registry.path_config import get_path_structure
        
        print("\n" + "="*60)
        print("PATH STRUCTURE VALIDATION")
        print("="*60)
        
        path_structure = get_path_structure()
        report = path_structure.validate_and_initialize()
        
        print(f"\nStatus: {report['status'].upper()}")
        
        if report.get('paths'):
            print("\nActive Paths:")
            for key, value in report['paths'].items():
                exists = Path(value).exists() if value else False
                status = "✓" if exists else "✗"
                print(f"  {status} {key}: {value}")
        
        if report.get('warnings'):
            print("\nWarnings:")
            for warning in report['warnings']:
                print(f"  ⚠ {warning}")
        
        if report.get('errors'):
            print("\nErrors:")
            for error in report['errors']:
                print(f"  ✗ {error}")
        
        print("="*60 + "\n")
        
        return report['status'] == 'ok'
        
    except Exception as e:
        print(f"\n✗ PATH VALIDATION FAILED: {e}")
        return False


if __name__ == "__main__":
    # Can be run directly to validate paths
    success = validate_path_structure()
    sys.exit(0 if success else 1)
