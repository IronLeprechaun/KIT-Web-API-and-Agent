#!/usr/bin/env python3
"""
Development Setup Script
Handles common development tasks and environment setup.
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path

class DevSetup:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        
    def setup_backend(self):
        """Set up backend environment"""
        print("🐍 Setting up backend environment...")
        
        # Check if venv exists
        venv_path = self.backend_dir / ".venv"
        if not venv_path.exists():
            print("Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        
        # Install dependencies
        pip_exe = venv_path / "Scripts" / "pip.exe"
        requirements = self.backend_dir / "api" / "requirements.txt"
        
        if requirements.exists():
            print("Installing Python dependencies...")
            subprocess.run([str(pip_exe), "install", "-r", str(requirements)], check=True)
        
        print("✅ Backend setup complete")
        
    def setup_frontend(self):
        """Set up frontend environment"""
        print("⚛️ Setting up frontend environment...")
        
        if not (self.frontend_dir / "node_modules").exists():
            print("Installing npm dependencies...")
            subprocess.run(["npm", "install"], cwd=self.frontend_dir, check=True)
        
        print("✅ Frontend setup complete")
        
    def reset_database(self):
        """Reset database to clean state"""
        print("🗄️ Resetting database...")
        
        db_path = self.backend_dir / "KITCore" / "database" / "kit_agent.db"
        if db_path.exists():
            db_path.unlink()
            print(f"Removed existing database: {db_path}")
        
        # Initialize new database
        os.chdir(self.backend_dir)
        venv_python = self.backend_dir / ".venv" / "Scripts" / "python.exe"
        
        result = subprocess.run([
            str(venv_python), "-c",
            "from KITCore.database_manager import get_db_connection; get_db_connection()"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print("✅ Database reset complete")
        else:
            print(f"❌ Database reset failed: {result.stderr}")
            
    def run_tests(self):
        """Run all tests"""
        print("🧪 Running tests...")
        
        os.chdir(self.project_root)
        venv_python = self.backend_dir / ".venv" / "Scripts" / "python.exe"
        
        result = subprocess.run([
            str(venv_python), "scripts/enhanced_tester.py", "--backend"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
            
        return result.returncode == 0
        
    def check_environment(self):
        """Check development environment health"""
        print("🔍 Checking development environment...")
        
        issues = []
        
        # Check Python version
        if sys.version_info < (3, 11):
            issues.append("Python 3.11+ required")
            
        # Check Node.js
        try:
            result = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                issues.append("Node.js not found")
        except FileNotFoundError:
            issues.append("Node.js not installed")
            
        # Check environment variables
        if not os.getenv("GEMINI_API_KEY"):
            issues.append("GEMINI_API_KEY not set")
            
        # Check virtual environment
        if not (self.backend_dir / ".venv").exists():
            issues.append("Backend virtual environment not found")
            
        # Check dependencies
        if not (self.frontend_dir / "node_modules").exists():
            issues.append("Frontend dependencies not installed")
            
        if issues:
            print("❌ Issues found:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        else:
            print("✅ Environment looks good!")
            return True

def main():
    parser = argparse.ArgumentParser(description="Development Setup Script")
    parser.add_argument("--setup-backend", action="store_true", help="Set up backend environment")
    parser.add_argument("--setup-frontend", action="store_true", help="Set up frontend environment")
    parser.add_argument("--reset-db", action="store_true", help="Reset database")
    parser.add_argument("--run-tests", action="store_true", help="Run tests")
    parser.add_argument("--check-env", action="store_true", help="Check environment")
    parser.add_argument("--setup-all", action="store_true", help="Set up everything")
    
    args = parser.parse_args()
    
    setup = DevSetup()
    
    if args.setup_all:
        setup.check_environment()
        setup.setup_backend()
        setup.setup_frontend()
        setup.reset_database()
        setup.run_tests()
    elif args.setup_backend:
        setup.setup_backend()
    elif args.setup_frontend:
        setup.setup_frontend()
    elif args.reset_db:
        setup.reset_database()
    elif args.run_tests:
        setup.run_tests()
    elif args.check_env:
        setup.check_environment()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 