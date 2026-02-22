# ============================================
# FILE: system_control.py
# ============================================

import os
import subprocess
import psutil
import winreg
import shutil
from pathlib import Path
from logger import log_action
from speech import speak

# ============================================
# SENSITIVE OPERATIONS (Require Password)
# ============================================

SENSITIVE_OPERATIONS = {
    "delete_file": "Delete file",
    "delete_folder": "Delete folder",
    "open_settings": "Open system settings",
    "open_camera": "Access camera",
    "open_mic": "Access microphone",
    "open_private_apps": "Open private messaging apps",
    "modify_system": "Modify system files"
}

PRIVATE_APPS = [
    "whatsapp", "telegram", "signal", "discord",
    "messenger", "skype", "teams"
]

SYSTEM_APPS = [
    "settings", "control panel", "task manager",
    "registry editor", "device manager"
]

# ============================================
# PASSWORD VERIFICATION
# ============================================

def verify_password(operation_type, listen_func):
    """
    Request password for sensitive operations
    """
    speak(f"This operation requires authentication: {SENSITIVE_OPERATIONS.get(operation_type, 'Unknown operation')}")
    speak("Please say your password")
    
    result = listen_func()
    if not result:
        speak("No password provided. Operation cancelled")
        log_action("SECURITY", f"Password verification failed for: {operation_type}")
        return False
    
    password, _ = result
    
    # ⚠️ CHANGE THIS PASSWORD!
    # your custom password
    if password == "authorize" or "authorize" in password:
        speak("Password accepted")
        log_action("SECURITY", f"Password verified for: {operation_type}")
        return True
    else:
        speak("Incorrect password. Operation cancelled")
        log_action("SECURITY", f"Incorrect password attempt for: {operation_type}")
        return False

# ============================================
# SEARCH FOR FILES AND APPLICATIONS
# ============================================

def search_file_system(query, search_type="all"):
    """
    Search for files, folders, or applications in the system
    
    Args:
        query: What to search for
        search_type: "file", "folder", "app", or "all"
    
    Returns:
        List of matching paths
    """
    results = []
    
    # Common search locations
    search_paths = [
        Path.home(),  # User home directory
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Downloads",
    ]
    
    speak(f"Searching for {query}")
    log_action("SYSTEM", f"File search initiated: {query}")
    
    for base_path in search_paths:
        if not base_path.exists():
            continue
        
        try:
            # Search with depth limit to avoid taking too long
            for item in base_path.rglob(f"*{query}*"):
                if len(results) >= 10:  # Limit to 10 results
                    break
                
                if search_type == "file" and item.is_file():
                    results.append(str(item))
                elif search_type == "folder" and item.is_dir():
                    results.append(str(item))
                elif search_type == "all":
                    results.append(str(item))
                    
        except (PermissionError, OSError):
            continue
    
    return results

def search_installed_applications(app_name):
    """
    Search for installed applications in Windows Registry
    """
    results = []
    
    # Registry paths to check
    registry_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    
    for reg_path in registry_paths:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if app_name.lower() in display_name.lower():
                            try:
                                install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                if install_location:
                                    results.append({
                                        "name": display_name,
                                        "path": install_location
                                    })
                            except:
                                # Try to get executable path
                                try:
                                    display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                                    if display_icon:
                                        results.append({
                                            "name": display_name,
                                            "path": display_icon.split(',')[0]
                                        })
                                except:
                                    pass
                    except:
                        pass
                    
                    winreg.CloseKey(subkey)
                except:
                    continue
            
            winreg.CloseKey(key)
        except:
            continue
    
    return results

# ============================================
# OPEN FILE/FOLDER/APPLICATION
# ============================================

def open_item(query, listen_func):
    """
    Open a file, folder, or application
    """
    # Check if it's a sensitive/private app
    is_private = any(app in query.lower() for app in PRIVATE_APPS)
    is_system = any(app in query.lower() for app in SYSTEM_APPS)
    
    if is_private or is_system:
        if not verify_password("open_private_apps" if is_private else "open_settings", listen_func):
            return False
    
    # Search for the item
    results = search_file_system(query)
    
    if not results:
        # Try searching for installed apps
        app_results = search_installed_applications(query)
        
        if app_results:
            speak(f"Found {len(app_results)} applications")
            
            if len(app_results) == 1:
                app = app_results[0]
                speak(f"Opening {app['name']}")
                try:
                    os.startfile(app['path'])
                    log_action("SYSTEM", f"Opened application: {app['name']}")
                    return True
                except:
                    speak(f"Could not open {app['name']}")
                    return False
            else:
                speak(f"Found multiple matches. Opening first: {app_results[0]['name']}")
                try:
                    os.startfile(app_results[0]['path'])
                    log_action("SYSTEM", f"Opened application: {app_results[0]['name']}")
                    return True
                except:
                    speak(f"Could not open {app_results[0]['name']}")
                    return False
        
        speak(f"Could not find {query}")
        log_action("SYSTEM", f"Search failed: {query}")
        return False
    
    # Present results
    if len(results) == 1:
        speak(f"Found {query}. Opening it")
        try:
            os.startfile(results[0])
            log_action("SYSTEM", f"Opened: {results[0]}")
            return True
        except Exception as e:
            speak("Could not open the file")
            log_action("ERROR", f"Failed to open: {results[0]} - {e}")
            return False
    else:
        speak(f"Found {len(results)} matches. Opening the first one")
        try:
            os.startfile(results[0])
            log_action("SYSTEM", f"Opened: {results[0]}")
            return True
        except Exception as e:
            speak("Could not open the file")
            log_action("ERROR", f"Failed to open: {results[0]} - {e}")
            return False

# ============================================
# CREATE FOLDER
# ============================================

def create_folder(folder_name, location=None):
    """
    Create a new folder
    """
    if location is None:
        location = Path.home() / "Documents"
    
    folder_path = Path(location) / folder_name
    
    try:
        folder_path.mkdir(parents=True, exist_ok=False)
        speak(f"Folder {folder_name} created successfully")
        log_action("SYSTEM", f"Created folder: {folder_path}")
        return True
    except FileExistsError:
        speak(f"Folder {folder_name} already exists")
        log_action("SYSTEM", f"Folder creation failed - already exists: {folder_path}")
        return False
    except Exception as e:
        speak(f"Could not create folder. Error occurred")
        log_action("ERROR", f"Folder creation failed: {e}")
        return False

# ============================================
# DELETE FILE/FOLDER
# ============================================

def delete_item(query, listen_func):
    """
    Delete a file or folder (requires password)
    """
    # Search for the item
    results = search_file_system(query)
    
    if not results:
        speak(f"Could not find {query}")
        return False
    
    item_path = Path(results[0])
    item_type = "folder" if item_path.is_dir() else "file"
    
    # Require password
    if not verify_password(f"delete_{item_type}", listen_func):
        return False
    
    # Ask for confirmation
    speak(f"Are you sure you want to delete this {item_type}: {item_path.name}? Say yes to confirm")
    
    result = listen_func()
    if not result:
        speak("Deletion cancelled")
        return False
    
    confirmation, _ = result
    
    if "yes" not in confirmation and "confirm" not in confirmation:
        speak("Deletion cancelled")
        log_action("SYSTEM", f"Deletion cancelled by user: {item_path}")
        return False
    
    # Delete the item
    try:
        if item_path.is_dir():
            shutil.rmtree(item_path)
        else:
            item_path.unlink()
        
        speak(f"{item_type.capitalize()} deleted successfully")
        log_action("SYSTEM", f"Deleted {item_type}: {item_path}")
        return True
    except Exception as e:
        speak(f"Could not delete {item_type}. Error occurred")
        log_action("ERROR", f"Deletion failed: {e}")
        return False

# ============================================
# CAMERA CONTROL
# ============================================

def open_camera(listen_func):
    """
    Open the camera app (requires password)
    """
    if not verify_password("open_camera", listen_func):
        return False
    
    try:
        os.system("start microsoft.windows.camera:")
        speak("Opening camera")
        log_action("SYSTEM", "Camera accessed")
        return True
    except Exception as e:
        speak("Could not open camera")
        log_action("ERROR", f"Camera access failed: {e}")
        return False

# ============================================
# MICROPHONE CONTROL
# ============================================

def test_microphone():
    """
    Test microphone (already in use by REX)
    """
    speak("Your microphone is currently active and being used by REX")
    log_action("SYSTEM", "Microphone test performed")
    return True

# ============================================
# SYSTEM SETTINGS
# ============================================

def open_settings(setting_type, listen_func):
    """
    Open various system settings
    """
    if not verify_password("open_settings", listen_func):
        return False
    
    settings_commands = {
        "settings": "start ms-settings:",
        "control panel": "control",
        "task manager": "taskmgr",
        "device manager": "devmgmt.msc",
        "network settings": "start ms-settings:network",
        "sound settings": "start ms-settings:sound",
        "display settings": "start ms-settings:display",
        "bluetooth settings": "start ms-settings:bluetooth",
    }
    
    command = settings_commands.get(setting_type.lower())
    
    if command:
        try:
            os.system(command)
            speak(f"Opening {setting_type}")
            log_action("SYSTEM", f"Opened settings: {setting_type}")
            return True
        except Exception as e:
            speak(f"Could not open {setting_type}")
            log_action("ERROR", f"Settings access failed: {e}")
            return False
    else:
        speak(f"Unknown setting type: {setting_type}")
        return False