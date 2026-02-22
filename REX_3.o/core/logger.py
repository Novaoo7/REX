# ============================================
# FILE: core/logger.py
# REX 3.0 - Advanced Logging System
# ============================================

import os
import datetime
import logging
from pathlib import Path
from typing import Optional, List
from logging.handlers import RotatingFileHandler


class Logger:
    """Advanced logging system with rotation and search"""
    
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup Python logging
        self._setup_python_logger()
    
    def _setup_python_logger(self):
        """Setup Python's logging module"""
        log_file = self.log_dir / "rex_system.log"
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create rotating file handler (max 10MB, keep 5 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)
        
        # Configure root logger
        logger = logging.getLogger('REX')
        logger.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        self.python_logger = logger
    
    def log_action(self, source: str, message: str, level: str = "INFO"):
        """Log action to daily file and Python logger"""
        # Log to daily file
        today = datetime.date.today().isoformat()
        now = datetime.datetime.now().strftime("%H:%M:%S")
        file_path = self.log_dir / f"{today}.txt"
        
        try:
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"[{now}] {source}: {message}\n")
        except Exception as e:
            print(f"Logging error: {e}")
        
        # Log to Python logger
        log_message = f"{source}: {message}"
        if level == "DEBUG":
            self.python_logger.debug(log_message)
        elif level == "INFO":
            self.python_logger.info(log_message)
        elif level == "WARNING":
            self.python_logger.warning(log_message)
        elif level == "ERROR":
            self.python_logger.error(log_message)
        elif level == "CRITICAL":
            self.python_logger.critical(log_message)
    
    def open_logs(self, date_str: str) -> bool:
        """Open log file in default text editor"""
        file_path = self.log_dir / f"{date_str}.txt"
        abs_path = file_path.absolute()
        
        if abs_path.exists():
            try:
                os.system(f'notepad "{abs_path}"')
                return True
            except Exception as e:
                self.log_action("ERROR", f"Failed to open log: {e}", "ERROR")
                return False
        return False
    
    def list_all_log_files(self) -> List[str]:
        """Get list of all available log dates"""
        if not self.log_dir.exists():
            return []
        
        log_files = [
            f.stem for f in self.log_dir.glob("*.txt")
            if f.stem != "rex_system"
        ]
        return sorted(log_files, reverse=True)
    
    def search_logs(self, keyword: str) -> List[str]:
        """Search for keyword in all log files"""
        results = []
        
        for log_file in self.list_all_log_files():
            file_path = self.log_dir / f"{log_file}.txt"
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if keyword.lower() in content.lower():
                        results.append(log_file)
            except Exception as e:
                self.log_action("ERROR", f"Search error in {log_file}: {e}", "ERROR")
        
        return results
    
    def get_recent_logs(self, lines: int = 50) -> List[str]:
        """Get recent log entries"""
        today = datetime.date.today().isoformat()
        file_path = self.log_dir / f"{today}.txt"
        
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                return all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            self.log_action("ERROR", f"Failed to read logs: {e}", "ERROR")
            return []
    
    def get_stats(self) -> dict:
        """Get logging statistics"""
        stats = {
            "total_log_files": len(self.list_all_log_files()),
            "total_size_mb": 0,
            "oldest_log": None,
            "newest_log": None
        }
        
        log_files = self.list_all_log_files()
        if log_files:
            stats["oldest_log"] = log_files[-1]
            stats["newest_log"] = log_files[0]
        
        # Calculate total size
        total_size = sum(
            f.stat().st_size for f in self.log_dir.glob("*.txt")
        )
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        return stats
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Delete logs older than specified days"""
        cutoff_date = datetime.date.today() - datetime.timedelta(days=days_to_keep)
        deleted_count = 0
        
        for log_file in self.list_all_log_files():
            try:
                log_date = datetime.date.fromisoformat(log_file)
                if log_date < cutoff_date:
                    file_path = self.log_dir / f"{log_file}.txt"
                    file_path.unlink()
                    deleted_count += 1
            except ValueError:
                continue
        
        self.log_action("SYSTEM", f"Cleaned up {deleted_count} old log files", "INFO")
        return deleted_count


# Global logger instance
_global_logger: Optional[Logger] = None


def init_logger(log_dir: Path = Path("logs")) -> Logger:
    """Initialize global logger"""
    global _global_logger
    _global_logger = Logger(log_dir)
    return _global_logger


def log_action(source: str, message: str, level: str = "INFO"):
    """Convenience function to log action"""
    global _global_logger
    
    if _global_logger is None:
        _global_logger = Logger()
    
    _global_logger.log_action(source, message, level)


def get_logger() -> Logger:
    """Get global logger instance"""
    global _global_logger
    
    if _global_logger is None:
        _global_logger = Logger()
    
    return _global_logger