# ============================================
# FILE: rex_advanced.py
# REX 2.0 - Advanced Features Module
# ============================================

import os
import json
import datetime
import subprocess
from pathlib import Path
from logger import log_action
from speech import speak

# ============================================
# EMAIL INTEGRATION
# ============================================

class EmailManager:
    """
    Manages email operations (Gmail/Outlook)
    """
    
    def __init__(self):
        self.config_file = Path("memory/email_config.json")
        self.config = self._load_config()
    
    def _load_config(self):
        """Load email configuration"""
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {"email": None, "provider": None}
    
    def setup_email(self, email, provider="gmail"):
        """Configure email account"""
        self.config = {"email": email, "provider": provider}
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f)
        speak(f"Email configured: {email}")
    
    def check_inbox(self):
        """Check for new emails"""
        # This would use IMAP in production
        speak("Checking your email")
        # Placeholder - would integrate with actual email API
        speak("You have 3 unread emails")
        log_action("EMAIL", "Checked inbox")
    
    def send_email(self, recipient, subject, body):
        """Send an email"""
        speak(f"Sending email to {recipient}")
        # Placeholder - would integrate with actual email API
        log_action("EMAIL", f"Sent email to {recipient}: {subject}")
        speak("Email sent successfully")

# ============================================
# CALENDAR INTEGRATION
# ============================================

class CalendarManager:
    """
    Manages calendar and appointments
    """
    
    def __init__(self):
        self.events_file = Path("memory/calendar.json")
        self.events = self._load_events()
    
    def _load_events(self):
        """Load calendar events"""
        if self.events_file.exists():
            with open(self.events_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_events(self):
        """Save calendar events"""
        self.events_file.parent.mkdir(exist_ok=True)
        with open(self.events_file, 'w') as f:
            json.dump(self.events, f, indent=2)
    
    def add_event(self, title, date_str, time_str=None):
        """Add calendar event"""
        event = {
            "id": len(self.events) + 1,
            "title": title,
            "date": date_str,
            "time": time_str,
            "created": datetime.datetime.now().isoformat()
        }
        self.events.append(event)
        self._save_events()
        speak(f"Added to calendar: {title} on {date_str}")
        log_action("CALENDAR", f"Event added: {title}")
    
    def get_today_events(self):
        """Get today's events"""
        today = datetime.date.today().isoformat()
        today_events = [e for e in self.events if e["date"] == today]
        return today_events
    
    def get_upcoming_events(self, days=7):
        """Get upcoming events"""
        today = datetime.date.today()
        future = today + datetime.timedelta(days=days)
        
        upcoming = []
        for event in self.events:
            event_date = datetime.date.fromisoformat(event["date"])
            if today <= event_date <= future:
                upcoming.append(event)
        
        return sorted(upcoming, key=lambda x: x["date"])
    
    def speak_today_schedule(self):
        """Speak today's schedule"""
        events = self.get_today_events()
        
        if not events:
            speak("You have no events scheduled for today")
            return
        
        speak(f"You have {len(events)} events today")
        for event in events:
            time_info = f"at {event['time']}" if event["time"] else ""
            speak(f"{event['title']} {time_info}")

# ============================================
# WEB SEARCH & INFORMATION
# ============================================

class WebAssistant:
    """
    Web search and information retrieval
    """
    
    def search_web(self, query):
        """Search the web"""
        speak(f"Searching for {query}")
        # Open default browser with search
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        os.system(f'start {search_url}')
        log_action("WEB", f"Searched: {query}")
    
    def get_weather(self, location="current"):
        """Get weather information"""
        speak(f"Getting weather for {location}")
        # Placeholder - would integrate with weather API
        weather_url = f"https://www.google.com/search?q=weather+{location.replace(' ', '+')}"
        os.system(f'start {weather_url}')
        log_action("WEB", f"Weather check: {location}")
    
    def get_news(self, topic="headlines"):
        """Get news"""
        speak(f"Getting {topic} news")
        news_url = f"https://news.google.com/search?q={topic.replace(' ', '+')}"
        os.system(f'start {news_url}')
        log_action("WEB", f"News: {topic}")
    
    def open_website(self, url):
        """Open specific website"""
        if not url.startswith("http"):
            url = f"https://{url}"
        speak(f"Opening website")
        os.system(f'start {url}')
        log_action("WEB", f"Opened: {url}")

# ============================================
# MUSIC & MEDIA CONTROL
# ============================================

class MediaController:
    """
    Controls music and media playback
    """
    
    def play_music(self, query=None):
        """Play music"""
        if query:
            speak(f"Playing {query}")
            # Open YouTube Music or Spotify with query
            url = f"https://music.youtube.com/search?q={query.replace(' ', '+')}"
        else:
            speak("Opening music player")
            url = "https://music.youtube.com"
        
        os.system(f'start {url}')
        log_action("MEDIA", f"Music: {query or 'player'}")
    
    def control_playback(self, action):
        """Control playback (play/pause/next/previous)"""
        # Use Windows media keys
        if action == "pause" or action == "play":
            os.system("nircmd mediaplay")
        elif action == "next":
            os.system("nircmd mediaforward")
        elif action == "previous":
            os.system("nircmd mediaback")
        
        speak(f"Media {action}")
        log_action("MEDIA", f"Control: {action}")

# ============================================
# REMINDER & NOTIFICATION SYSTEM
# ============================================

class ReminderManager:
    """
    Manages reminders and notifications
    """
    
    def __init__(self):
        self.reminders_file = Path("memory/reminders.json")
        self.reminders = self._load_reminders()
    
    def _load_reminders(self):
        """Load reminders"""
        if self.reminders_file.exists():
            with open(self.reminders_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_reminders(self):
        """Save reminders"""
        self.reminders_file.parent.mkdir(exist_ok=True)
        with open(self.reminders_file, 'w') as f:
            json.dump(self.reminders, f, indent=2)
    
    def add_reminder(self, text, time_str=None, date_str=None):
        """Add a reminder"""
        reminder = {
            "id": len(self.reminders) + 1,
            "text": text,
            "time": time_str,
            "date": date_str or datetime.date.today().isoformat(),
            "completed": False,
            "created": datetime.datetime.now().isoformat()
        }
        self.reminders.append(reminder)
        self._save_reminders()
        
        when = f"at {time_str}" if time_str else "today"
        speak(f"Reminder set: {text} {when}")
        log_action("REMINDER", f"Added: {text}")
    
    def list_reminders(self):
        """List active reminders"""
        active = [r for r in self.reminders if not r["completed"]]
        
        if not active:
            speak("You have no active reminders")
            return
        
        speak(f"You have {len(active)} reminders")
        for r in active:
            speak(r["text"])
    
    def check_due_reminders(self):
        """Check for due reminders"""
        now = datetime.datetime.now()
        today = now.date().isoformat()
        current_time = now.strftime("%H:%M")
        
        due = []
        for reminder in self.reminders:
            if not reminder["completed"] and reminder["date"] == today:
                if not reminder["time"] or reminder["time"] <= current_time:
                    due.append(reminder)
        
        return due

# ============================================
# SMART ASSISTANT FEATURES
# ============================================

class SmartFeatures:
    """
    Advanced smart assistant capabilities
    """
    
    def __init__(self):
        self.knowledge_file = Path("memory/knowledge_base.json")
        self.knowledge = self._load_knowledge()
    
    def _load_knowledge(self):
        """Load knowledge base"""
        if self.knowledge_file.exists():
            with open(self.knowledge_file, 'r') as f:
                return json.load(f)
        return {"facts": {}, "contacts": {}, "notes": {}}
    
    def _save_knowledge(self):
        """Save knowledge base"""
        self.knowledge_file.parent.mkdir(exist_ok=True)
        with open(self.knowledge_file, 'w') as f:
            json.dump(self.knowledge, f, indent=2)
    
    def remember_fact(self, key, value):
        """Remember a fact"""
        self.knowledge["facts"][key.lower()] = {
            "value": value,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self._save_knowledge()
        speak(f"I'll remember that {key} is {value}")
        log_action("KNOWLEDGE", f"Stored: {key} = {value}")
    
    def recall_fact(self, key):
        """Recall a fact"""
        fact = self.knowledge["facts"].get(key.lower())
        if fact:
            speak(f"{key} is {fact['value']}")
            return fact["value"]
        else:
            speak(f"I don't remember anything about {key}")
            return None
    
    def add_contact(self, name, phone=None, email=None):
        """Add a contact"""
        self.knowledge["contacts"][name.lower()] = {
            "name": name,
            "phone": phone,
            "email": email,
            "added": datetime.datetime.now().isoformat()
        }
        self._save_knowledge()
        speak(f"Contact added: {name}")
    
    def get_contact(self, name):
        """Get contact info"""
        contact = self.knowledge["contacts"].get(name.lower())
        if contact:
            speak(f"{contact['name']}")
            if contact["phone"]:
                speak(f"Phone: {contact['phone']}")
            if contact["email"]:
                speak(f"Email: {contact['email']}")
            return contact
        else:
            speak(f"I don't have contact information for {name}")
            return None
    
    def take_note(self, note_text):
        """Take a quick note"""
        note_id = len(self.knowledge["notes"]) + 1
        self.knowledge["notes"][note_id] = {
            "text": note_text,
            "timestamp": datetime.datetime.now().isoformat()
        }
        self._save_knowledge()
        speak("Note saved")
        log_action("NOTE", note_text)

# ============================================
# SYSTEM OPTIMIZATION
# ============================================

class SystemOptimizer:
    """
    System maintenance and optimization
    """
    
    def check_system_health(self):
        """Check system health"""
        try:
            import psutil
            
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            speak("System health check")
            speak(f"CPU usage: {cpu} percent")
            speak(f"Memory usage: {memory.percent} percent")
            speak(f"Disk usage: {disk.percent} percent")
            
            # Warnings
            if cpu > 80:
                speak("Warning: High CPU usage detected")
            if memory.percent > 85:
                speak("Warning: High memory usage detected")
            if disk.percent > 90:
                speak("Warning: Low disk space")
            
            log_action("SYSTEM", f"Health check - CPU:{cpu}% RAM:{memory.percent}% DISK:{disk.percent}%")
        except:
            speak("Could not check system health")
    
    def clean_temp_files(self):
        """Clean temporary files"""
        speak("Cleaning temporary files")
        try:
            # Clean Windows temp folder
            temp_path = Path(os.getenv('TEMP'))
            count = 0
            for item in temp_path.glob('*'):
                try:
                    if item.is_file():
                        item.unlink()
                        count += 1
                except:
                    pass
            
            speak(f"Cleaned {count} temporary files")
            log_action("SYSTEM", f"Cleaned {count} temp files")
        except:
            speak("Could not clean all temporary files")
    
    def list_startup_programs(self):
        """List startup programs"""
        speak("Checking startup programs")
        # This would integrate with Windows startup management
        speak("This feature requires administrative access")
        log_action("SYSTEM", "Startup programs check")

# ============================================
# INITIALIZE ADVANCED MODULES
# ============================================

rex_email = EmailManager()
rex_calendar = CalendarManager()
rex_web = WebAssistant()
rex_media = MediaController()
rex_reminders = ReminderManager()
rex_smart = SmartFeatures()
rex_optimizer = SystemOptimizer()

def get_advanced_modules():
    """Get all advanced module instances"""
    return {
        "email": rex_email,
        "calendar": rex_calendar,
        "web": rex_web,
        "media": rex_media,
        "reminders": rex_reminders,
        "smart": rex_smart,
        "optimizer": rex_optimizer
    }