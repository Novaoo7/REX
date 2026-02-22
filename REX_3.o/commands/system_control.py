# ============================================
# FILE: commands/system_control.py - FIXED VERSION
# REX 3.0 - Universal System Control
# ============================================

import os
import subprocess
import winreg
from pathlib import Path
from typing import List, Dict, Optional


class SystemController:
    """Universal system controller - finds ANY app/file"""
    
    def __init__(self):
        # Smart search paths
        self.common_paths = [
            Path("C:/Program Files"),
            Path("C:/Program Files (x86)"),
            Path("C:/Windows/System32"),
            Path.home() / "AppData/Local/Programs",
            Path.home() / "Desktop",
            Path.home() / "Documents"
        ]
    
    def search_and_open(self, query: str) -> Dict:
        """
        UNIVERSAL SEARCH - Finds ANY application or file
        """
        print(f"[SEARCH] Looking for: {query}")
        
        # Method 1: Try Windows registry (fastest for installed apps)
        app = self._search_registry(query)
        if app:
            print(f"[FOUND] Via Registry: {app}")
            return self._open_item(app)
        
        # Method 2: Try common executable names
        exe_result = self._try_common_executables(query)
        if exe_result["success"]:
            return exe_result
        
        # Method 3: File system search
        results = self._search_filesystem(query)
        if results:
            print(f"[FOUND] Via Filesystem: {results[0]}")
            return self._open_item(results[0])
        
        return {"success": False, "message": f"Could not find {query}"}
    
    def _search_registry(self, query: str) -> Optional[str]:
        """Search Windows Registry for installed applications"""
        registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        ]
        
        # Try direct app name
        for base_key in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
            for reg_path in registry_paths:
                try:
                    # Try with .exe
                    key_path = f"{reg_path}\\{query}.exe"
                    key = winreg.OpenKey(base_key, key_path)
                    path = winreg.QueryValue(key, None)
                    winreg.CloseKey(key)
                    if path and os.path.exists(path):
                        return path
                except:
                    pass
        
        return None
    
    def _try_common_executables(self, query: str) -> Dict:
        """Try common executable names"""
        # Common app mappings
        common_apps = {
            "chrome": "chrome.exe",
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "paint": "mspaint.exe",
            "explorer": "explorer.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "outlook": "outlook.exe",
            "vscode": "code.exe",
            "code": "code.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe"
        }
        
        query_lower = query.lower()
        
        # Try exact match
        if query_lower in common_apps:
            try:
                subprocess.Popen(common_apps[query_lower])
                return {"success": True, "message": f"Opened {query}"}
            except:
                pass
        
        # Try partial match
        for name, exe in common_apps.items():
            if name in query_lower or query_lower in name:
                try:
                    subprocess.Popen(exe)
                    return {"success": True, "message": f"Opened {name}"}
                except:
                    pass
        
        return {"success": False}
    
    def _search_filesystem(self, query: str, max_depth: int = 2) -> List[Path]:
        """Search filesystem for apps/files"""
        results = []
        
        for base_path in self.common_paths:
            if not base_path.exists():
                continue
            
            try:
                self._search_recursive(base_path, query, results, 0, max_depth)
                
                if results:
                    break  # Found something, stop searching
            except:
                continue
        
        return results
    
    def _search_recursive(self, path: Path, query: str, results: List, 
                         depth: int, max_depth: int):
        """Recursive file search"""
        if depth > max_depth or len(results) >= 5:
            return
        
        try:
            for item in path.iterdir():
                if len(results) >= 5:
                    return
                
                # Check if name matches
                if query.lower() in item.name.lower():
                    # Prioritize executables
                    if item.suffix in ['.exe', '.lnk']:
                        results.insert(0, item)
                    else:
                        results.append(item)
                
                # Recurse into directories
                if item.is_dir() and not item.name.startswith('.'):
                    self._search_recursive(item, query, results, depth + 1, max_depth)
        
        except (PermissionError, OSError):
            pass
    
    def _open_item(self, path) -> Dict:
        """Open file/app at path"""
        try:
            path_str = str(path)
            
            # Use os.startfile for Windows
            os.startfile(path_str)
            
            return {
                "success": True,
                "message": f"Opened {Path(path_str).name}",
                "target": path_str
            }
        except Exception as e:
            print(f"[ERROR] Failed to open {path}: {e}")
            return {
                "success": False,
                "message": f"Could not open {path}"
            }