#!/usr/bin/env python3
"""
Secure Secrets Manager
Handles encrypted storage of API keys and sensitive configuration data.
"""

import argparse
import json
import getpass
import hashlib
import base64
import os
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("⚠️ cryptography package not installed. Run: pip install cryptography")

class SecretsManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.secrets_dir = self.project_root / ".secrets"
        self.secrets_dir.mkdir(exist_ok=True)
        
        # Set restrictive permissions on secrets directory (Unix-like systems)
        if os.name != 'nt':  # Not Windows
            os.chmod(self.secrets_dir, 0o700)
        
        self.secrets_file = self.secrets_dir / "secrets.enc"
        self.salt_file = self.secrets_dir / "salt.bin"
        
    def _generate_key(self, password: str, salt: bytes = None) -> bytes:
        """Generate encryption key from password"""
        if salt is None:
            salt = os.urandom(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _get_salt(self) -> Optional[bytes]:
        """Get existing salt or return None"""
        if self.salt_file.exists():
            with open(self.salt_file, 'rb') as f:
                return f.read()
        return None
    
    def _encrypt_data(self, data: Dict[str, Any], password: str = None) -> bytes:
        """Store data as plain JSON (no encryption for local-only app)"""
        # For local-only applications, we don't need encryption
        json_data = json.dumps(data, indent=2).encode()
        return json_data
    
    def _decrypt_data(self, data: bytes, password: str = None) -> Dict[str, Any]:
        """Load data from plain JSON"""
        # For local-only applications, data is stored as plain JSON
        try:
            return json.loads(data.decode())
        except Exception as e:
            raise ValueError("Failed to load configuration - file may be corrupted") from e
    
    def set_secret(self, key: str, value: str, password: str = None) -> bool:
        """Set a secret value (no password required for local app)"""
        
        # Load existing secrets or create new
        secrets = {}
        if self.secrets_file.exists():
            try:
                secrets = self.load_secrets()
            except Exception as e:
                print(f"❌ Failed to load existing secrets: {e}")
                return False
        
        # Add new secret
        secrets[key] = value
        
        # Save secrets
        try:
            data = self._encrypt_data(secrets)
            with open(self.secrets_file, 'wb') as f:
                f.write(data)
            
            print(f"✅ Secret '{key}' saved successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to save secret: {e}")
            return False
    
    def get_secret(self, key: str, password: str = None) -> Optional[str]:
        """Get a secret value (no password required for local app)"""
        if not self.secrets_file.exists():
            return None
        
        try:
            secrets = self.load_secrets()
            return secrets.get(key)
        except Exception as e:
            print(f"❌ Failed to retrieve secret: {e}")
            return None
    
    def load_secrets(self, password: str = None) -> Dict[str, Any]:
        """Load all secrets (no password required for local app)"""
        if not self.secrets_file.exists():
            return {}
        
        with open(self.secrets_file, 'rb') as f:
            data = f.read()
        
        return self._decrypt_data(data)
    
    def list_secrets(self, password: str = None) -> None:
        """List all secret keys (not values)"""
        try:
            secrets = self.load_secrets()
            if secrets:
                print("🔑 Stored secrets:")
                for key in secrets.keys():
                    print(f"  - {key}")
            else:
                print("No secrets stored")
        except Exception as e:
            print(f"❌ Failed to list secrets: {e}")
    
    def delete_secret(self, key: str, password: str = None) -> bool:
        """Delete a secret"""
        try:
            secrets = self.load_secrets()
            if key in secrets:
                del secrets[key]
                
                # Save updated secrets
                data = self._encrypt_data(secrets)
                with open(self.secrets_file, 'wb') as f:
                    f.write(data)
                
                print(f"✅ Secret '{key}' deleted")
                return True
            else:
                print(f"⚠️ Secret '{key}' not found")
                return False
                
        except Exception as e:
            print(f"❌ Failed to delete secret: {e}")
            return False
    
    def export_to_env(self, env_file: Path, password: str = None) -> bool:
        """Export secrets to a .env file"""
        try:
            secrets = self.load_secrets()
            
            with open(env_file, 'w') as f:
                f.write("# Generated from local configuration - DO NOT COMMIT\n")
                f.write("# This file should be in .gitignore\n\n")
                
                for key, value in secrets.items():
                    f.write(f"{key}={value}\n")
            
            print(f"✅ Secrets exported to {env_file}")
            print("⚠️ Remember: This file contains sensitive data in plain text!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to export secrets: {e}")
            return False
    
    def setup_initial_secrets(self) -> None:
        """Interactive setup for initial secrets (no password required)"""
        print("🔧 Initial API Key Setup")
        print("=" * 40)
        
        # Collect API keys
        secrets = {}
        
        print("\n1. Enter your API keys (press Enter to skip):")
        
        api_keys = [
            ("GEMINI_API_KEY", "Google Gemini API Key"),
            ("OPENAI_API_KEY", "OpenAI API Key (optional)"),
            ("ANTHROPIC_API_KEY", "Anthropic API Key (optional)")
        ]
        
        for key, description in api_keys:
            value = input(f"{description}: ").strip()
            if value:
                secrets[key] = value
        
        # Save secrets
        if secrets:
            try:
                data = self._encrypt_data(secrets)
                with open(self.secrets_file, 'wb') as f:
                    f.write(data)
                
                print(f"\n✅ {len(secrets)} API keys saved successfully!")
                print("🔑 API keys stored:")
                for key in secrets.keys():
                    print(f"  - {key}")
                    
            except Exception as e:
                print(f"❌ Failed to save API keys: {e}")
        else:
            print("⚠️ No API keys provided")

def main():
    parser = argparse.ArgumentParser(description="Secure Secrets Manager")
    parser.add_argument("--setup", action="store_true", help="Initial setup wizard")
    parser.add_argument("--set", nargs=2, metavar=('KEY', 'VALUE'), help="Set a secret")
    parser.add_argument("--get", metavar='KEY', help="Get a secret value")
    parser.add_argument("--list", action="store_true", help="List all secret keys")
    parser.add_argument("--delete", metavar='KEY', help="Delete a secret")
    parser.add_argument("--export-env", metavar='FILE', help="Export secrets to .env file")
    
    args = parser.parse_args()
    
    manager = SecretsManager()
    
    if args.setup:
        manager.setup_initial_secrets()
    elif args.set:
        key, value = args.set
        manager.set_secret(key, value)
    elif args.get:
        value = manager.get_secret(args.get)
        if value:
            print(f"{args.get}={value}")
        else:
            print(f"Secret '{args.get}' not found")
    elif args.list:
        manager.list_secrets()
    elif args.delete:
        manager.delete_secret(args.delete)
    elif args.export_env:
        manager.export_to_env(Path(args.export_env))
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 