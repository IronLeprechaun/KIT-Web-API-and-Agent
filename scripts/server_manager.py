#!/usr/bin/env python3
"""
KIT System Server Manager
Handles server health checking and basic management.
"""

import argparse
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ServerManager:
    def __init__(self):
        self.project_root = Path(__file__).parent  # KIT_Web directory
        self.backend_port = 8000
        self.frontend_port = 5173
        
    def health_check(self) -> dict:
        """Check health of all servers"""
        logger.info("Checking server health...")
        
        backend_healthy = self._check_backend_health()
        frontend_healthy = self._check_frontend_health()
        
        health = {
            'backend': backend_healthy,
            'frontend': frontend_healthy,
            'overall': backend_healthy and frontend_healthy
        }
        
        # Print status
        backend_status = "✅" if backend_healthy else "❌"
        frontend_status = "✅" if frontend_healthy else "❌"
        overall_status = "✅" if health['overall'] else "❌"
        
        logger.info(f"Backend ({self.backend_port}): {backend_status}")
        logger.info(f"Frontend ({self.frontend_port}): {frontend_status}")
        logger.info(f"Overall: {overall_status}")
        
        return health
    
    def _check_backend_health(self) -> bool:
        """Check if backend is responding"""
        try:
            import requests
            response = requests.get(f"http://localhost:{self.backend_port}/api/notes/", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _check_frontend_health(self) -> bool:
        """Check if frontend is responding"""
        try:
            import requests
            response = requests.get(f"http://localhost:{self.frontend_port}/", timeout=5)
            return response.status_code == 200
        except:
            return False

def main():
    parser = argparse.ArgumentParser(description="KIT System Server Manager")
    parser.add_argument("--health-check", action='store_true', help="Check server health")
    
    args = parser.parse_args()
    
    manager = ServerManager()
    
    if args.health_check:
        health = manager.health_check()
        sys.exit(0 if health['overall'] else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 