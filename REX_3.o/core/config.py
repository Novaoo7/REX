# ============================================
# FILE: core/config.py
# REX 3.0 - Configuration Management
# ============================================

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any


@dataclass
class SystemConfig:
    """Centralized system configuration"""
    
    # === Audio Settings ===
    sample_rate: int = 16000
    block_size: int = 8000
    speech_rate: int = 170
    speech_volume: float = 1.0
    
    # === Voice Recognition ===
    vosk_model_path: str = "model"
    confidence_threshold: float = 0.7
    noise_filter_enabled: bool = True
    
    # === Security ===
    max_login_attempts: int = 3
    session_timeout: int = 3600
    require_password_for_sensitive: bool = True
    password_min_length: int = 6
    
    # === Performance ===
    max_search_depth: int = 3
    max_search_results: int = 10
    command_history_size: int = 50
    cache_timeout: int = 300
    enable_performance_monitoring: bool = True
    
    # === Paths ===
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    memory_dir: Path = field(default_factory=lambda: Path("memory"))
    cache_dir: Path = field(default_factory=lambda: Path("cache"))
    config_file: Path = field(default_factory=lambda: Path("config.json"))
    users_file: Path = field(default_factory=lambda: Path("users_secure.json"))
    
    # === Features ===
    enable_proactive_suggestions: bool = True
    enable_context_memory: bool = True
    enable_routines: bool = True
    enable_advanced_features: bool = True
    
    # === UI ===
    verbosity: str = "normal"  # minimal, normal, verbose
    show_confidence: bool = True
    show_intent: bool = True
    
    # === Wake Words ===
    wake_words: list = field(default_factory=lambda: ["rex", "wake up", "hey rex"])
    sleep_words: list = field(default_factory=lambda: ["sleep", "go to sleep", "rest"])
    
    def __post_init__(self):
        """Ensure paths are Path objects"""
        if not isinstance(self.logs_dir, Path):
            self.logs_dir = Path(self.logs_dir)
        if not isinstance(self.memory_dir, Path):
            self.memory_dir = Path(self.memory_dir)
        if not isinstance(self.cache_dir, Path):
            self.cache_dir = Path(self.cache_dir)
        if not isinstance(self.config_file, Path):
            self.config_file = Path(self.config_file)
        if not isinstance(self.users_file, Path):
            self.users_file = Path(self.users_file)
        
        # Create directories if they don't exist
        self.logs_dir.mkdir(exist_ok=True)
        self.memory_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)
    
    def save(self):
        """Save configuration to file"""
        config_dict = asdict(self)
        
        # Convert Path objects to strings for JSON serialization
        config_dict['logs_dir'] = str(self.logs_dir)
        config_dict['memory_dir'] = str(self.memory_dir)
        config_dict['cache_dir'] = str(self.cache_dir)
        config_dict['config_file'] = str(self.config_file)
        config_dict['users_file'] = str(self.users_file)
        
        with open(self.config_file, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        print(f"✓ Configuration saved to {self.config_file}")
    
    @classmethod
    def load(cls) -> 'SystemConfig':
        """Load configuration from file or create default"""
        config_file = Path("config.json")
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                # Convert string paths back to Path objects
                data['logs_dir'] = Path(data['logs_dir'])
                data['memory_dir'] = Path(data['memory_dir'])
                data['cache_dir'] = Path(data['cache_dir'])
                data['config_file'] = Path(data['config_file'])
                data['users_file'] = Path(data['users_file'])
                
                print(f"✓ Configuration loaded from {config_file}")
                return cls(**data)
            
            except Exception as e:
                print(f"⚠️  Failed to load config: {e}")
                print("Creating default configuration...")
        
        # Create and save default configuration
        config = cls()
        config.save()
        return config
    
    def update(self, **kwargs):
        """Update configuration values"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        default_config = SystemConfig()
        for key, value in asdict(default_config).items():
            setattr(self, key, value)
        self.save()
        print("✓ Configuration reset to defaults")
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return getattr(self, key, default)
    
    def display(self):
        """Display current configuration"""
        print("\n" + "=" * 60)
        print("CURRENT CONFIGURATION")
        print("=" * 60)
        
        for key, value in asdict(self).items():
            print(f"{key:30} : {value}")
        
        print("=" * 60 + "\n")