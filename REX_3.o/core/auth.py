# ============================================
# FILE: core/auth.py
# REX 3.0 - Secure Authentication System
# ============================================

import json
import hashlib
import secrets
import time
from pathlib import Path
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class UserAccount:
    """User account information"""
    username: str
    password_hash: str
    salt: str
    role: str  # admin, user, guest
    created_at: str
    last_login: Optional[str] = None
    login_count: int = 0
    failed_attempts: int = 0


class AuthenticationManager:
    """Secure authentication with password hashing and session management"""
    
    ROLES = {
        "admin": {
            "description": "Full system access",
            "permissions": ["all"]
        },
        "user": {
            "description": "Standard access (no system modifications)",
            "permissions": ["open", "search", "time", "date", "logs_view"]
        },
        "guest": {
            "description": "Read-only access",
            "permissions": ["time", "date", "logs_view"]
        }
    }
    
    def __init__(self, users_file: Path = Path("users_secure.json")):
        self.users_file = users_file
        self.users: Dict[str, UserAccount] = {}
        self.sessions: Dict[str, dict] = {}
        self.max_failed_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        self.locked_accounts = {}
        
        self._load_users()
    
    def _load_users(self):
        """Load users from secure file"""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    
                for username, user_data in data.items():
                    self.users[username] = UserAccount(**user_data)
                
                print(f"✓ Loaded {len(self.users)} user accounts")
            except Exception as e:
                print(f"⚠️  Failed to load users: {e}")
                self._create_default_admin()
        else:
            self._create_default_admin()
    
    def _create_default_admin(self):
        """Create default admin account"""
        salt = secrets.token_hex(16)
        password_hash = self._hash_password("admin123", salt)
        
        admin = UserAccount(
            username="admin",
            password_hash=password_hash,
            salt=salt,
            role="admin",
            created_at=datetime.now().isoformat()
        )
        
        self.users["admin"] = admin
        self._save_users()
        
        print("=" * 60)
        print("⚠️  DEFAULT ADMIN ACCOUNT CREATED")
        print("Username: admin")
        print("Password: admin123")
        print("PLEASE CHANGE THIS PASSWORD IMMEDIATELY!")
        print("=" * 60)
    
    def _save_users(self):
        """Save users to secure file"""
        data = {}
        for username, user in self.users.items():
            data[username] = {
                "username": user.username,
                "password_hash": user.password_hash,
                "salt": user.salt,
                "role": user.role,
                "created_at": user.created_at,
                "last_login": user.last_login,
                "login_count": user.login_count,
                "failed_attempts": user.failed_attempts
            }
        
        self.users_file.parent.mkdir(exist_ok=True)
        with open(self.users_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _hash_password(self, password: str, salt: str) -> str:
        """Hash password with salt using PBKDF2"""
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000
        ).hex()
    
    def _is_account_locked(self, username: str) -> bool:
        """Check if account is temporarily locked"""
        if username in self.locked_accounts:
            lock_time = self.locked_accounts[username]
            if time.time() - lock_time < self.lockout_duration:
                return True
            else:
                del self.locked_accounts[username]
        return False
    
    def authenticate(self, username: str, password: str) -> Tuple[bool, Optional[str]]:
        """
        Authenticate user credentials
        
        Returns:
            (success, role) - role is None if authentication fails
        """
        username = username.lower().strip()
        
        # Check if account is locked
        if self._is_account_locked(username):
            remaining = int(self.lockout_duration - (time.time() - self.locked_accounts[username]))
            print(f"⚠️  Account locked. Try again in {remaining} seconds")
            return False, None
        
        # Check if user exists
        if username not in self.users:
            time.sleep(1)  # Prevent timing attacks
            return False, None
        
        user = self.users[username]
        
        # Verify password
        password_hash = self._hash_password(password, user.salt)
        
        if password_hash == user.password_hash:
            # Successful login
            user.failed_attempts = 0
            user.last_login = datetime.now().isoformat()
            user.login_count += 1
            self._save_users()
            
            return True, user.role
        else:
            # Failed login
            user.failed_attempts += 1
            
            if user.failed_attempts >= self.max_failed_attempts:
                self.locked_accounts[username] = time.time()
                print(f"⚠️  Account locked due to too many failed attempts")
            
            self._save_users()
            time.sleep(1)  # Prevent brute force
            
            return False, None
    
    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        """Create new user account"""
        username = username.lower().strip()
        
        # Validate username
        if username in self.users:
            print(f"✗ User '{username}' already exists")
            return False
        
        if len(username) < 3:
            print("✗ Username must be at least 3 characters")
            return False
        
        # Validate password
        if len(password) < 6:
            print("✗ Password must be at least 6 characters")
            return False
        
        # Validate role
        if role not in self.ROLES:
            print(f"✗ Invalid role. Must be: {', '.join(self.ROLES.keys())}")
            return False
        
        # Create user
        salt = secrets.token_hex(16)
        password_hash = self._hash_password(password, salt)
        
        user = UserAccount(
            username=username,
            password_hash=password_hash,
            salt=salt,
            role=role,
            created_at=datetime.now().isoformat()
        )
        
        self.users[username] = user
        self._save_users()
        
        print(f"✓ User '{username}' created successfully")
        return True
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        # Verify old password
        success, role = self.authenticate(username, old_password)
        
        if not success:
            print("✗ Current password incorrect")
            return False
        
        # Validate new password
        if len(new_password) < 6:
            print("✗ New password must be at least 6 characters")
            return False
        
        if new_password == old_password:
            print("✗ New password must be different from old password")
            return False
        
        # Update password
        user = self.users[username.lower()]
        salt = secrets.token_hex(16)
        user.password_hash = self._hash_password(new_password, salt)
        user.salt = salt
        
        self._save_users()
        print(f"✓ Password changed successfully for '{username}'")
        return True
    
    def delete_user(self, username: str) -> bool:
        """Delete user account (admin only)"""
        username = username.lower()
        
        if username not in self.users:
            print(f"✗ User '{username}' not found")
            return False
        
        if username == "admin":
            print("✗ Cannot delete admin account")
            return False
        
        del self.users[username]
        self._save_users()
        
        print(f"✓ User '{username}' deleted")
        return True
    
    def has_permission(self, role: str, command: str) -> bool:
        """Check if role has permission for command"""
        if role == "admin":
            return True
        
        # Restricted commands (admin only)
        restricted_keywords = [
            "close", "shutdown", "exit", "quit",
            "delete", "remove", "create folder",
            "open camera", "open settings"
        ]
        
        # User permissions
        if role == "user":
            return not any(word in command.lower() for word in restricted_keywords)
        
        # Guest permissions (very limited)
        if role == "guest":
            allowed = ["hello", "hi", "time", "date", "logs"]
            return any(word in command.lower() for word in allowed)
        
        return False
    
    def list_users(self) -> list:
        """List all users"""
        return [
            {
                "username": user.username,
                "role": user.role,
                "created": user.created_at,
                "last_login": user.last_login,
                "login_count": user.login_count
            }
            for user in self.users.values()
        ]
    
    def get_user_info(self, username: str) -> Optional[dict]:
        """Get user information"""
        user = self.users.get(username.lower())
        if user:
            return {
                "username": user.username,
                "role": user.role,
                "created": user.created_at,
                "last_login": user.last_login,
                "login_count": user.login_count,
                "failed_attempts": user.failed_attempts
            }
        return None