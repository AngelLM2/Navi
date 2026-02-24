import subprocess
import os
import shutil



class WindowsCompatibility:
    
    
    @staticmethod
    def find_ollama():
        
        ollama_paths = [
            os.path.expanduser("~\\AppData\\Local\\Programs\\Ollama\\ollama.exe"),
            "C:\\Program Files\\Ollama\\ollama.exe",
            "ollama.exe",
            "ollama"
        ]
        
        for path in ollama_paths:
            if os.path.exists(path):
                return path
            try:
                result = shutil.which(path)
                if result:
                    return result
            except:
                continue
        return None
    
    @staticmethod
    def get_windows_apps():
        
        local_app_data = os.getenv("LOCALAPPDATA", "")
        return {
            'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            'firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
            'brave': 'brave',
            'opera': 'opera',
            'vscode': 'code',
            'obsidian': os.path.join(local_app_data, 'Obsidian', 'Obsidian.exe') if local_app_data else 'obsidian',
            'notepad': 'notepad',
            'calculator': 'calc',
            'paint': 'mspaint',
            'word': 'winword',
            'excel': 'excel',
            'powerpoint': 'powerpnt',
            'outlook': 'outlook',
            'explorer': 'explorer',
            'cmd': 'cmd',
            'powershell': 'powershell',
            'terminal': 'wt',
            'spotify': 'spotify',
            'discord': 'discord',
            'whatsapp': 'whatsapp',
            'telegram': 'telegram',
            'steam': 'steam',
            'epic': 'EpicGamesLauncher',
            'minecraft': 'minecraft',
            'zoom': 'zoom',
            'teams': 'teams',
            'skype': 'skype',
            'photoshop': 'photoshop',
            'premiere': 'premiere',
            'aftereffects': 'afterfx',
            'illustrator': 'illustrator',
            'obs': 'obs',
            'vlc': 'vlc',
            'winrar': 'winrar',
            '7zip': '7zfm',
        }
    
    @staticmethod
    def open_app_windows(app_name, custom_response=None):
        
        apps = WindowsCompatibility.get_windows_apps()
        
        app_key = app_name.lower()
        
        def _try_open(target):
            target = str(target or "").strip()
            if not target:
                return False

            
            if os.path.isfile(target):
                try:
                    os.startfile(target)
                    return True
                except Exception:
                    pass

            
            which_cmd = shutil.which(target)
            if which_cmd:
                try:
                    subprocess.Popen([which_cmd], shell=False)
                    return True
                except Exception:
                    pass

            
            if target.lower() in {'notepad', 'calc', 'mspaint', 'cmd', 'powershell', 'explorer', 'wt'}:
                try:
                    subprocess.Popen(f'start "" {target}', shell=True)
                    return True
                except Exception:
                    pass

            
            try:
                os.startfile(target)
                return True
            except Exception:
                return False

        if app_key in apps:
            cmd = apps[app_key]
            if _try_open(cmd):
                return f"{app_name} opened"
            
            if _try_open(app_name):
                return f"{app_name} opened"
            return f"Could not open {app_name}"

        if _try_open(app_name):
            return f"{app_name} opened"
        return f"App {app_name} not found"


class TextPreprocessor:
    
    
    @staticmethod
    def normalize(text):
        
        if not text:
            return ""
        
        text = text.lower().strip()
        
        for char in ".,!?;:\"'()[]{}":
            text = text.replace(char, "")
        
        stop_words = {
            "the", "a", "an", "to", "of", "in", "for", "on", "with", "at",
            "by", "from", "up", "about", "into", "over", "after", "and",
            "or", "but", "so", "yet", "not"
        }
        
        words = text.split()
        filtered_words = [w for w in words if w not in stop_words and len(w) > 1]
        
        return " ".join(filtered_words)
    
    @staticmethod
    def extract_command(text, keyword):
        
        text_lower = text.lower()
        
        patterns = [
            f"{keyword} ",
            f"hey {keyword} ",
            f"hi {keyword} ",
            keyword,
        ]
        
        for pattern in patterns:
            if text_lower.startswith(pattern):
                text = text[len(pattern):].strip()
                break
        
        if text_lower.endswith(f" {keyword}"):
            text = text[:-len(keyword)-1].strip()
        
        return text.strip()
