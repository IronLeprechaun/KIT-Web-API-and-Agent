#!/usr/bin/env python3
"""
Configuration Manager
Handles environment variables, settings, and deployment configurations.
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List
import subprocess

# Import our secure secrets manager
try:
    from .secrets_manager import SecretsManager
    SECRETS_AVAILABLE = True
except ImportError:
    try:
        from secrets_manager import SecretsManager
        SECRETS_AVAILABLE = True
    except ImportError:
        SECRETS_AVAILABLE = False
        print("⚠️ Secrets manager not available - falling back to environment variables")

class ConfigManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize secrets manager if available
        self.secrets_manager = SecretsManager() if SECRETS_AVAILABLE else None
        
        self.environments = {
            "development": {
                "backend_port": 8000,
                "frontend_port": 3000,
                "database_path": "backend/KITCore/database/kit_agent.db",
                "log_level": "INFO",
                "debug_mode": True
            },
            "production": {
                "backend_port": 8000,
                "frontend_port": 80,
                "database_path": "backend/KITCore/database/kit_agent_prod.db",
                "log_level": "WARNING",
                "debug_mode": False
            },
            "testing": {
                "backend_port": 8001,
                "frontend_port": 3001,
                "database_path": "backend/KITCore/database/kit_agent_test.db",
                "log_level": "DEBUG",
                "debug_mode": True
            }
        }
        
    def _get_secret_value(self, key: str) -> str:
        """Get secret value from secure storage or environment"""
        if self.secrets_manager:
            try:
                # Try to get from encrypted secrets first
                value = self.secrets_manager.get_secret(key, password="")  # Will prompt for password
                if value:
                    return value
            except Exception:
                pass  # Fall back to environment variable
        
        # Fall back to environment variable
        return os.getenv(key, "")
        
    def save_config(self, env_name: str, config: Dict[str, Any]):
        """Save configuration for an environment"""
        config_file = self.config_dir / f"{env_name}.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✅ Configuration saved: {config_file}")
        
    def load_config(self, env_name: str) -> Dict[str, Any]:
        """Load configuration for an environment"""
        config_file = self.config_dir / f"{env_name}.json"
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            # Return default configuration
            return self.environments.get(env_name, self.environments["development"])
    
    def setup_environment(self, env_name: str, use_secrets: bool = True):
        """Set up environment variables for the specified environment"""
        config = self.load_config(env_name)
        
        # Create .env file for backend
        env_file = self.project_root / "backend" / ".env"
        env_content = []
        
        # Add configuration variables
        env_content.append(f"ENVIRONMENT={env_name}")
        env_content.append(f"BACKEND_PORT={config.get('backend_port', 8000)}")
        env_content.append(f"DATABASE_PATH={config.get('database_path', 'kit_agent.db')}")
        env_content.append(f"LOG_LEVEL={config.get('log_level', 'INFO')}")
        env_content.append(f"DEBUG_MODE={str(config.get('debug_mode', False)).lower()}")
        
        # DO NOT add API keys to .env files - they should stay in encrypted secrets manager
        print("🔐 API keys remain in encrypted secrets manager (not exported to .env)")
        env_content.append("# API keys are managed securely via encrypted secrets manager")
        env_content.append("# Use: python scripts/secrets_manager.py --setup to configure")
        
        # Only add non-sensitive environment variables
        env_content.append(f"NODE_ENV={env_name}")
        
        with open(env_file, 'w') as f:
            f.write('\n'.join(env_content))
            
        print(f"✅ Environment configured for {env_name}")
        print(f"📁 Environment file: {env_file}")
        
        # Create frontend environment file
        frontend_env = self.project_root / "frontend" / ".env.local"
        frontend_content = [
            f"REACT_APP_API_URL=http://localhost:{config.get('backend_port', 8000)}/api",
            f"REACT_APP_ENVIRONMENT={env_name}",
            f"PORT={config.get('frontend_port', 3000)}"
        ]
        
        with open(frontend_env, 'w') as f:
            f.write('\n'.join(frontend_content))
            
        print(f"📁 Frontend environment file: {frontend_env}")
    
    def check_environment(self) -> Dict[str, Any]:
        """Check current environment configuration"""
        status = {
            "environment_variables": {},
            "config_files": {},
            "missing_variables": [],
            "issues": [],
            "secure_secrets": {}
        }
        
        # Check secure secrets
        if self.secrets_manager:
            try:
                secrets = self.secrets_manager.load_secrets()
                for key in ["GEMINI_API_KEY", "OPENAI_API_KEY"]:
                    if key in secrets:
                        status["secure_secrets"][key] = "🔐 Encrypted"
                    else:
                        status["secure_secrets"][key] = "❌ Missing"
            except Exception:
                status["secure_secrets"]["status"] = "⚠️ Cannot access - password required"
        else:
            status["secure_secrets"]["status"] = "❌ Secrets manager not available"
        
        # Check important environment variables (only non-sensitive ones)
        important_vars = ["NODE_ENV"]
        for var in important_vars:
            value = os.getenv(var)
            if value:
                status["environment_variables"][var] = "✅ Set"
            else:
                status["environment_variables"][var] = "❌ Missing"
                status["missing_variables"].append(var)
        
        # Note about API keys not being in environment variables
        status["environment_variables"]["API_KEYS"] = "🔐 Stored in encrypted secrets (not env vars)"
        
        # Check configuration files
        backend_env = self.project_root / "backend" / ".env"
        frontend_env = self.project_root / "frontend" / ".env.local"
        
        status["config_files"]["backend_.env"] = "✅ Exists" if backend_env.exists() else "❌ Missing"
        status["config_files"]["frontend_.env.local"] = "✅ Exists" if frontend_env.exists() else "❌ Missing"
        
        # Check configuration directory
        for env in ["development", "production", "testing"]:
            config_file = self.config_dir / f"{env}.json"
            status["config_files"][f"{env}_config"] = "✅ Exists" if config_file.exists() else "⚠️ Using defaults"
        
        # Identify issues
        if status["missing_variables"]:
            status["issues"].append(f"Missing environment variables: {', '.join(status['missing_variables'])}")
            
        if not backend_env.exists():
            status["issues"].append("Backend .env file missing")
            
        return status
    
    def generate_sample_env(self):
        """Generate sample environment files"""
        sample_env = self.project_root / ".env.sample"
        
        content = [
            "# KIT System Environment Variables",
            "# WARNING: This is a sample file showing the format",
            "# DO NOT put real API keys here - use the secure secrets manager instead:",
            "# python scripts/secrets_manager.py --setup",
            "",
            "# Environment",
            "ENVIRONMENT=development",
            "NODE_ENV=development",
            "",
            "# Server Configuration",
            "BACKEND_PORT=8000",
            "FRONTEND_PORT=3000",
            "",
            "# Database",
            "DATABASE_PATH=backend/KITCore/database/kit_agent.db",
            "",
            "# Logging",
            "LOG_LEVEL=INFO",
            "DEBUG_MODE=true",
            "",
            "# API Keys - NEVER put real API keys in environment files!",
            "# API keys are managed securely via encrypted secrets manager:",
            "# Run: python scripts/secrets_manager.py --setup",
            "# GEMINI_API_KEY=NEVER_PUT_REAL_KEYS_HERE",
            "# OPENAI_API_KEY=NEVER_PUT_REAL_KEYS_HERE",
            "",
            "# Security (generate your own)"
        ]
        
        with open(sample_env, 'w') as f:
            f.write('\n'.join(content))
            
        print(f"✅ Sample environment file created: {sample_env}")
        
    def init_configs(self):
        """Initialize all configuration files"""
        print("🔧 Initializing configuration files...")
        
        # Save default configurations
        for env_name, config in self.environments.items():
            self.save_config(env_name, config)
        
        # Generate sample environment
        self.generate_sample_env()
        
        # Set up development environment by default
        self.setup_environment("development", use_secrets=False)  # Don't use secrets on first init
        
        print("✅ Configuration initialization complete!")
        print("\n📋 Next steps:")
        print("1. Set up secure secrets: python scripts/secrets_manager.py --setup")
        print("2. Run: python scripts/config_manager.py --check")
        print("3. Use: python scripts/config_manager.py --env [development|testing|production]")

def main():
    parser = argparse.ArgumentParser(description="Configuration Manager")
    parser.add_argument("--env", choices=["development", "testing", "production"], 
                       help="Set up environment")
    parser.add_argument("--check", action="store_true", help="Check environment status")
    parser.add_argument("--init", action="store_true", help="Initialize configurations")
    parser.add_argument("--sample", action="store_true", help="Generate sample .env file")
    parser.add_argument("--use-env-vars", action="store_true", 
                       help="Use environment variables instead of secure secrets")
    
    args = parser.parse_args()
    
    manager = ConfigManager()
    
    if args.init:
        manager.init_configs()
    elif args.env:
        use_secrets = not args.use_env_vars
        manager.setup_environment(args.env, use_secrets=use_secrets)
    elif args.check:
        print("🔍 Environment Status Check")
        print("=" * 50)
        
        status = manager.check_environment()
        
        if "secure_secrets" in status and status["secure_secrets"]:
            print("\n🔐 Secure Secrets:")
            for key, state in status["secure_secrets"].items():
                print(f"  {key}: {state}")
        
        print("\n🌍 Environment Variables:")
        for var, state in status["environment_variables"].items():
            print(f"  {var}: {state}")
            
        print("\n📁 Configuration Files:")
        for file, state in status["config_files"].items():
            print(f"  {file}: {state}")
            
        if status["issues"]:
            print("\n⚠️ Issues Found:")
            for issue in status["issues"]:
                print(f"  - {issue}")
        else:
            print("\n✅ No issues found!")
            
    elif args.sample:
        manager.generate_sample_env()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 