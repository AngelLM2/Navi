import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import platform
import sys
from pathlib import Path
import psutil
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from variaveis import mirror_legacy_file, pcscan

if platform.system() == "Windows":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass



IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_MAC = platform.system() == "Darwin"

if __name__ == "__main__":
    print(f"Sistema detectado: {platform.system()}")










class IntelligentPcScanner:
    def __init__(self):
        self.system = platform.system()
        self.user_home = Path.home()
        self.cache = self._load_json(pcscan.SCAN_CACHE_FILE, {})
        self.cache_fast = self._load_json(pcscan.FAST_SCAN_CACHE_FILE, {})
        self.cache_deep = self._load_json(pcscan.DEEP_SCAN_CACHE_FILE, {})
        self.app_cache = self._load_json(pcscan.APP_CACHE_FILE, {})
        self.history = self._load_json(pcscan.SCAN_HISTORY_FILE, [])
        self.patterns = self._load_json(pcscan.LEARNED_PATTERNS_FILE, {})
        self.base_path = Path("C:")
        
        
        self.cache_config = pcscan.CACHE_CONFIG

        
        self.priority_paths = self._get_priority_paths()
        
        
        self.stats = {
            "last_scan": self.cache.get("last_scan"),
            "total_items": 0,
            "apps_found": 0,
            "documents_found": 0,
            "media_found": 0
        }
        
        
        self.apps_cache = set()
        self._load_apps_cache()
        
        
        self.scan_modes = {
            "fast": {
                "max_depth": 2,
                "max_files_per_dir": 200,
                "extensions": ['.exe', '.msi', '.lnk', '.app', '.desktop', '.bat', '.cmd', '.sh', '.dmg', '.pkg'],
                "target_paths": self._get_fast_scan_paths(),
                "cache_time": pcscan.CACHE_CONFIG["fast"]
            },
            "quick": {
                "max_depth": 5,  
                "max_files_per_dir": 500,  
                "extensions": [],
                "target_paths": list(self.priority_paths.values()),
                "cache_time": pcscan.CACHE_CONFIG["quick"]
            },
            "deep": {
                "max_depth": 10,
                "max_files_per_dir": 1000,
                "extensions": [],
                "target_paths": self._get_all_disk_paths(),
                "cache_time": pcscan.CACHE_CONFIG["deep"]
            }
        }
        
        print(f"PC Scanner inicializado para {self.system} com 3 modos")
        print(f"   DiretA3rios monitorados: {len(self.priority_paths)}")
        print(f"   as Fast Scan: {len(self.scan_modes['fast']['target_paths'])} locais")
        print(f"   Quick Scan: {len(self.scan_modes['quick']['target_paths'])} locais")
        print(f"   Deep Scan: {len(self.scan_modes['deep']['target_paths'])} locais")
    
    def _load_json(self, filename, default):
        
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"WARNING: Error loading {filename}: {e}")
        return default
    
    def _save_json(self, filename, data):
        
        try:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            legacy_map = {
                pcscan.SCAN_CACHE_FILE: getattr(pcscan, "LEGACY_SCAN_CACHE_FILE", ""),
                pcscan.FAST_SCAN_CACHE_FILE: getattr(pcscan, "LEGACY_FAST_SCAN_CACHE_FILE", ""),
                pcscan.DEEP_SCAN_CACHE_FILE: getattr(pcscan, "LEGACY_DEEP_SCAN_CACHE_FILE", ""),
                pcscan.SCAN_HISTORY_FILE: getattr(pcscan, "LEGACY_SCAN_HISTORY_FILE", ""),
                pcscan.LEARNED_PATTERNS_FILE: getattr(pcscan, "LEGACY_LEARNED_PATTERNS_FILE", ""),
                pcscan.APP_CACHE_FILE: getattr(pcscan, "LEGACY_APP_CACHE_FILE", ""),
            }
            mirror_legacy_file(filename, legacy_map.get(filename, ""))
            return True
        except Exception as e:
            print(f"WARNING: Error saving {filename}: {e}")
            return False
    
    def _load_apps_cache(self):
        
        if self.cache.get("scan_summary"):
            apps = self.cache["scan_summary"].get("apps", [])
            self.apps_cache = set(app.lower() for app in apps)
    
    def _get_fast_scan_paths(self):
        
        paths = []
        fast_keys = ["Program Files", "Program Files (x86)", "desktop", "downloads"]
        
        for key in fast_keys:
            if key in self.priority_paths:
                paths.append(self.priority_paths[key])
        
        
        if IS_WINDOWS:
            appdata_path = os.path.join(os.environ.get("APPDATA", ""), "..", "Local")
            if os.path.exists(appdata_path):
                paths.append(appdata_path)
        
        return paths
    
    def _get_all_disk_paths(self):
        
        paths = []
        try:
            for partition in psutil.disk_partitions():
                try:
                    paths.append(partition.mountpoint)
                except:
                    continue
        except:
            
            paths = list(self.priority_paths.values())
            paths.append("C:\\" if IS_WINDOWS else "/")
        
        return paths
    
    def _get_priority_paths(self):
        
        paths = {
            "desktop": str(self.user_home / "Desktop"),
            "downloads": str(self.user_home / "Downloads"),
            "documents": str(self.user_home / "Documents"),
            "pictures": str(self.user_home / "Pictures"),
            "music": str(self.user_home / "Music"),
            "videos": str(self.user_home / "Videos"),
            "Program Files": str(self.base_path / "Program Files"),
            "Program Files (x86)": str(self.base_path / "Program Files (x86)")
        }
        
        if self.system == "Windows":
            possible_paths = [
                "C:\\Program Files",
                "C:\\Program Files (x86)",
                "D:\\Program Files",
                "D:\\Program Files (x86)",
                os.environ.get("PROGRAMFILES", "C:\\Program Files"),
                os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
            ]
            for i, path in enumerate(possible_paths):
                if os.path.exists(path):
                    paths[f"program_files_{i}"] = path
                    
        elif self.system == "Linux":
            paths.update({
                "applications": "/usr/share/applications",
                "local_applications": str(self.user_home / ".local/share/applications"),
                "bin": "/usr/bin",
                "local_bin": str(self.user_home / ".local/bin"),
                "usr_local_bin": "/usr/local/bin"
            })
        elif self.system == "Darwin":  
            paths.update({
                "applications": "/Applications",
                "user_applications": str(self.user_home / "Applications"),
                "library": str(self.user_home / "Library"),
                "system_apps": "/System/Applications",
                "utilities": "/Applications/Utilities"
            })
        
        
        valid_paths = {}
        for key, path in paths.items():
            if os.path.exists(path):
                valid_paths[key] = path
        
        return valid_paths
    
    def _show_progress(self, current, total, prefix=""):
        
        bar_length = 40
        progress = current / total if total > 0 else 0
        filled_length = int(bar_length * progress)
        bar = '#' * filled_length + '-' * (bar_length - filled_length)
        percent = progress * 100
        print(f"\r{prefix} |{bar}| {percent:.1f}% {current}/{total}", end='', flush=True)
        if current == total:
            print()
    
    def _scan_directory_parallel(self, path, results, category, max_depth=10, max_files=400, 
                                current_depth=0, extensions=None):
        
        if current_depth > max_depth:
            return
        
        try:
            entries = list(os.scandir(path))
            file_count = 0
            
            
            for entry in entries:
                if entry.is_file():
                    try:
                        
                        if extensions:
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext not in extensions:
                                continue
                        self._classify_file(entry.path, results, category)
                        file_count += 1
                        if file_count >= max_files:
                            break
                    except (PermissionError, OSError):
                        continue
            
            
            if current_depth < max_depth:
                dirs_to_scan = []
                for entry in entries:
                    if entry.is_dir():
                        try:
                            dir_name = entry.name.lower()
                            
                            
                            if any(term in category.lower() for term in ['program', 'apps', 'program_files', 'progra']):
                                dirs_to_scan.append(entry.path)
                            elif any(keyword in dir_name for keyword in ['app', 'bin', 'program', 'game', 'tool', 'util', 'application']):
                                dirs_to_scan.append(entry.path)
                            elif category.lower() in ['desktop', 'downloads']:
                                dirs_to_scan.append(entry.path)
                        except:
                            continue
                
                
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = []
                    for dir_path in dirs_to_scan:
                        future = executor.submit(
                            self._scan_directory_parallel, 
                            dir_path, results, category, max_depth, 
                            max_files, current_depth + 1, extensions
                        )
                        futures.append(future)
                    
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
                        
        except (PermissionError, OSError) as e:
            pass
    
    def _scan_directory(self, path, results, category, max_depth=10, max_files=400, 
                       current_depth=0, extensions=None, parallel=False):
        
        if parallel and current_depth == 0:
            return self._scan_directory_parallel(path, results, category, max_depth, max_files, current_depth, extensions)
        
        if current_depth > max_depth:
            return
        
        try:
            with os.scandir(path) as entries:
                file_count = 0
                
                for entry in entries:
                    
                    if entry.is_file():
                        try:
                            
                            if extensions:
                                ext = os.path.splitext(entry.name)[1].lower()
                                if ext not in extensions:
                                    continue
                            self._classify_file(entry.path, results, category)
                            file_count += 1
                            if file_count >= max_files:
                                continue
                        except (PermissionError, OSError):
                            continue
                    
                    
                    elif entry.is_dir() and current_depth < max_depth:
                        try:
                            dir_name = entry.name.lower()
                            
                            
                            if any(term in category.lower() for term in ['program', 'apps', 'program_files', 'progra']):
                                self._scan_directory(entry.path, results, category, max_depth, max_files, current_depth + 1, extensions)
                            
                            else:
                                important_subdirs = [
                                    'app', 'bin', 'program', 'game', 'tool', 
                                    'util', 'application', 'software', 'steam',
                                    'epic', 'riot', 'origin', 'uplay', 'gog'
                                ]
                                
                                if any(keyword in dir_name for keyword in important_subdirs):
                                    self._scan_directory(
                                        entry.path, results, category, 
                                        max_depth, max_files, current_depth + 1, extensions
                                    )
                                elif category.lower() in ['desktop', 'downloads']:
                                    self._scan_directory(
                                        entry.path, results, category,
                                        max_depth, max_files, current_depth + 1, extensions
                                    )
                        except (PermissionError, OSError):
                            continue
                            
        except (PermissionError, OSError) as e:
            pass
    
    def _classify_file(self, filepath, results, category):
        
        filename = os.path.basename(filepath).lower()
        ext = os.path.splitext(filename)[1].lower()
        
        
        if ext in ['.exe', '.app', '.lnk', '.desktop', '.msi', '.bat', '.cmd', '.sh', '.dmg', '.pkg']:
            app_name = os.path.splitext(filename)[0]
            if app_name not in results["apps"]:
                results["apps"].append(app_name)
                results["executables"].append({
                    "name": app_name,
                    "path": filepath,
                    "category": category
                })
        
        
        elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.xls', '.xlsx', 
                    '.ppt', '.pptx', '.csv', '.md', '.html', '.htm']:
            if filepath not in results["documents"]:
                results["documents"].append({
                    "path": filepath,
                    "name": filename,
                    "category": category
                })
        
        
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.mp3', '.wav', '.flac',
                    '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
            if filepath not in results["media"]:
                results["media"].append({
                    "path": filepath,
                    "name": filename,
                    "category": category
                })
        
        
        elif ext in ['.zip', '.rar', '.7z', '.tar', '.gz', '.iso']:
            if filepath not in results["documents"]:
                results["documents"].append({
                    "path": filepath,
                    "name": filename,
                    "category": category
                })
    
    def _get_cache_for_mode(self, mode):
        
        if mode == "fast":
            return self.cache_fast
        elif mode == "deep":
            return self.cache_deep
        else:
            return self.cache
    
    def _save_cache_for_mode(self, mode, data):
        
        if mode == "fast":
            self.cache_fast = data
            self._save_json(pcscan.FAST_SCAN_CACHE_FILE, data)
        elif mode == "deep":
            self.cache_deep = data
            self._save_json(pcscan.DEEP_SCAN_CACHE_FILE, data)
            
            self.cache["last_scan_timestamp"] = data.get("last_scan_timestamp")
            self.cache["scan_summary"] = data.get("scan_summary", {})
            self.cache["stats"] = data.get("stats", {})
            self.cache["last_scan_mode"] = "deep"
            self._save_json(pcscan.SCAN_CACHE_FILE, self.cache)
        else:
            self.cache = data
            self._save_json(pcscan.SCAN_CACHE_FILE, data)

    def _append_scan_history(self, mode, scan_results):
        
        summary = {
            "apps": len(scan_results.get("apps", [])),
            "items": len(scan_results.get("documents", [])) + len(scan_results.get("media", [])),
        }
        if mode == "deep":
            summary["system_files"] = len(scan_results.get("system_files", []))

        self.history.append({
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "summary": summary,
        })

        if len(self.history) > 100:
            self.history = self.history[-100:]
        self._save_json(pcscan.SCAN_HISTORY_FILE, self.history)
    
    def fast_scan(self) -> Dict:
        
        print("as Iniciando FAST SCAN (apps apenas)...")
        start_time = time.time()
        
        mode_config = self.scan_modes["fast"]
        cache = self._get_cache_for_mode("fast")
        
        
        last_scan = cache.get("last_scan_timestamp")
        if last_scan:
            try:
                last_time = datetime.fromisoformat(last_scan)
                if datetime.now() - last_time < mode_config["cache_time"]:
                    print("   OK: Usando cache (atA 4 horas)")
                    return cache.get("scan_summary", {})
            except:
                pass
        
        scan_results = {
            "metadata": {
                "scan_time": datetime.now().isoformat(),
                "mode": "fast",
                "system": self.system,
                "target_paths": mode_config["target_paths"]
            },
            "apps": [],
            "executables": [],
            "total_items": 0,
            "scan_duration": 0
        }
        
        
        total_paths = len(mode_config["target_paths"])
        for i, path in enumerate(mode_config["target_paths"], 1):
            self._show_progress(i, total_paths, prefix="Fast Scan")
            if os.path.exists(path):
                self._scan_directory(
                    path, scan_results, "fast", 
                    max_depth=mode_config["max_depth"],
                    max_files=mode_config["max_files_per_dir"],
                    extensions=mode_config["extensions"],
                    parallel=True
                )
        
        scan_results["total_items"] = len(scan_results["apps"])
        scan_results["scan_duration"] = time.time() - start_time
        
        
        cache_data = {
            "last_scan_timestamp": datetime.now().isoformat(),
            "scan_summary": scan_results
        }
        self._save_cache_for_mode("fast", cache_data)
        
        print(f"\nOK: FAST SCAN concluAdo em {scan_results['scan_duration']:.1f}s")
        print(f"   - Apps encontrados: {len(scan_results['apps'])}")
        
        return scan_results
    
    def quick_scan(self, max_depth=5, max_files_per_dir=500):
        
        print("Iniciando QUICK SCAN (padrAo otimizado)...")
        start_time = time.time()
        
        mode_config = self.scan_modes["quick"]
        cache = self._get_cache_for_mode("quick")
        
        
        last_scan = cache.get("last_scan_timestamp")
        if last_scan:
            try:
                last_time = datetime.fromisoformat(last_scan)
                if datetime.now() - last_time < mode_config["cache_time"]:
                    print("   OK: Usando cache (atA 1 hora)")
                    return cache.get("scan_summary", {})
            except:
                pass
        
        scan_results = {
            "metadata": {
                "scan_time": datetime.now().isoformat(),
                "mode": "quick",
                "system": self.system,
                "target_paths": mode_config["target_paths"]
            },
            "apps": [],
            "executables": [],
            "documents": [],
            "media": [],
            "recent_items": [],
            "system_info": self._get_system_info(),
            "scan_duration": 0
        }
        
        
        total_paths = len(mode_config["target_paths"])
        for i, path in enumerate(mode_config["target_paths"], 1):
            self._show_progress(i, total_paths, prefix="Quick Scan")
            if os.path.exists(path):
                self._scan_directory(
                    path, scan_results, "quick", 
                    max_depth=mode_config["max_depth"],
                    max_files=mode_config["max_files_per_dir"],
                    extensions=mode_config["extensions"]
                )
        
        
        scan_results["running_processes"] = self._get_running_processes()
        
        
        scan_results["recent_items"] = self._get_recent_items()
        
        
        scan_results["usage_patterns"] = self._detect_usage_patterns()
        
        scan_results["scan_duration"] = time.time() - start_time
        
        
        cache_data = {
            "last_scan_timestamp": datetime.now().isoformat(),
            "scan_summary": scan_results,
            "stats": {
                "apps_found": len(scan_results["apps"]),
                "executables_found": len(scan_results["executables"]),
                "documents_found": len(scan_results["documents"]),
                "media_found": len(scan_results["media"]),
                "total_items": sum(len(v) for k, v in scan_results.items() 
                                 if isinstance(v, list))
            }
        }
        self._save_cache_for_mode("quick", cache_data)
        
        
        self._load_apps_cache()
        
        
        self._append_scan_history("quick", scan_results)
        
        
        self._learn_from_scan(scan_results)
        
        print(f"\nOK: QUICK SCAN concluAdo em {scan_results['scan_duration']:.1f}s")
        print(f"   - Apps: {len(scan_results['apps'])}")
        print(f"   - Documentos: {len(scan_results['documents'])}")
        print(f"   - MAdia: {len(scan_results['media'])}")
        print(f"   - Processos ativos: {len(scan_results.get('running_processes', []))}")
        
        return scan_results
    
    def deep_scan(self) -> Dict:
        
        print("Iniciando DEEP SCAN (sistema completo)...")
        start_time = time.time()
        
        mode_config = self.scan_modes["deep"]
        cache = self._get_cache_for_mode("deep")
        
        
        last_scan = cache.get("last_scan_timestamp")
        if last_scan:
            try:
                last_time = datetime.fromisoformat(last_scan)
                if datetime.now() - last_time < mode_config["cache_time"]:
                    print("   OK: Usando cache (atA 24 horas)")
                    
                    self._save_cache_for_mode("deep", cache)
                    self._load_apps_cache()
                    return cache.get("scan_summary", {})
            except:
                pass
        
        scan_results = {
            "metadata": {
                "scan_time": datetime.now().isoformat(),
                "mode": "deep",
                "system": self.system,
                "target_paths": mode_config["target_paths"]
            },
            "apps": [],
            "executables": [],
            "documents": [],
            "media": [],
            "system_files": [],
            "logs": [],
            "configs": [],
            "system_info": self._get_system_info(),
            "disk_analysis": self._get_disk_analysis(),
            "duplicate_files": [],
            "scan_duration": 0
        }
        
        
        total_paths = len(mode_config["target_paths"])
        for i, path in enumerate(mode_config["target_paths"], 1):
            self._show_progress(i, total_paths, prefix="Deep Scan")
            if os.path.exists(path):
                try:
                    self._deep_scan_directory(
                        path, scan_results, "deep", 
                        max_depth=mode_config["max_depth"],
                        max_files=mode_config["max_files_per_dir"]
                    )
                except Exception as e:
                    print(f"   WARNING: Erro em {path}: {e}")
        
        
        scan_results["duplicate_files"] = self._find_duplicates(scan_results)
        scan_results["space_analysis"] = self._analyze_disk_space()
        scan_results["cleanup_suggestions"] = self._generate_cleanup_suggestions(scan_results)
        
        scan_results["scan_duration"] = time.time() - start_time
        
        
        cache_data = {
            "last_scan_timestamp": datetime.now().isoformat(),
            "scan_summary": scan_results,
            "stats": {
                "total_items": len(scan_results["apps"]) + len(scan_results["documents"]) + 
                              len(scan_results["media"]) + len(scan_results["system_files"]),
                "apps_found": len(scan_results["apps"]),
                "files_found": len(scan_results["documents"]) + len(scan_results["media"]),
                "system_items": len(scan_results["system_files"])
            }
        }
        self._save_cache_for_mode("deep", cache_data)

        
        self._load_apps_cache()
        self._append_scan_history("deep", scan_results)
        self._learn_from_scan(scan_results)
        
        print(f"\nOK: DEEP SCAN concluAdo em {scan_results['scan_duration']:.1f}s")
        print(f"   - Apps: {len(scan_results['apps'])}")
        print(f"   - Documentos: {len(scan_results['documents'])}")
        print(f"   - MAdia: {len(scan_results['media'])}")
        print(f"   - Arquivos de sistema: {len(scan_results['system_files'])}")
        print(f"   - Arquivos duplicados: {len(scan_results['duplicate_files'])}")
        
        return scan_results
    
    def _deep_scan_directory(self, path, results, category, max_depth=8, max_files=1000, current_depth=0):
        
        if current_depth > max_depth:
            return
        
        try:
            with os.scandir(path) as entries:
                file_count = 0
                
                for entry in entries:
                    if entry.is_file():
                        try:
                            filename = entry.name.lower()
                            ext = os.path.splitext(filename)[1].lower()
                            filepath = entry.path
                            
                            
                            if ext in ['.exe', '.app', '.lnk', '.desktop', '.msi']:
                                app_name = os.path.splitext(filename)[0]
                                if app_name not in results["apps"]:
                                    results["apps"].append(app_name)
                                    results["executables"].append({
                                        "name": app_name,
                                        "path": filepath,
                                        "category": category
                                    })
                            elif ext in ['.log', '.tmp', '.cache', '.dmp', '.crash']:
                                results["logs"].append({
                                    "path": filepath,
                                    "name": filename,
                                    "size": entry.stat().st_size
                                })
                            elif ext in ['.ini', '.cfg', '.conf', '.config', '.xml', '.json', '.yaml', '.yml']:
                                results["configs"].append({
                                    "path": filepath,
                                    "name": filename,
                                    "category": category
                                })
                            elif ext in ['.sys', '.dll', '.so', '.dylib', '.drv']:
                                results["system_files"].append({
                                    "path": filepath,
                                    "name": filename,
                                    "type": "system"
                                })
                            elif ext in ['.pdf', '.doc', '.docx', '.txt', '.rtf']:
                                results["documents"].append({
                                    "path": filepath,
                                    "name": filename,
                                    "category": category
                                })
                            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3']:
                                results["media"].append({
                                    "path": filepath,
                                    "name": filename,
                                    "category": category
                                })
                            
                            file_count += 1
                            if file_count >= max_files:
                                break
                        except:
                            continue
                    
                    elif entry.is_dir() and current_depth < max_depth:
                        try:
                            dir_name = entry.name.lower()
                            
                            
                            important_dirs = [
                                'windows', 'system32', 'etc', 'var', 'log', 'tmp',
                                'programdata', 'appdata', 'local', 'roaming',
                                'library', 'system', 'users'
                            ]
                            
                            if any(keyword in dir_name for keyword in important_dirs):
                                self._deep_scan_directory(
                                    entry.path, results, category,
                                    max_depth, max_files, current_depth + 1
                                )
                            elif current_depth < 3:  
                                self._deep_scan_directory(
                                    entry.path, results, category,
                                    max_depth, max_files, current_depth + 1
                                )
                        except:
                            continue
        except:
            pass
    
    def app_scan(self, app_name: str = None) -> Dict:
        
        if app_name:
            return self._search_specific_app(app_name)
        return self._scan_all_apps()
    
    def _search_specific_app(self, app_name: str) -> Dict:
        
        app_name_lower = app_name.lower()
        results = {
            "found": False,
            "app_name": app_name,
            "locations": [],
            "versions": []
        }
        
        
        for app in self.apps_cache:
            if app_name_lower in app:
                results["found"] = True
                results["locations"].append(f"Cache: {app}")
        
        
        fast_results = self.fast_scan()
        for exe in fast_results.get("executables", []):
            if app_name_lower in exe["name"].lower():
                results["found"] = True
                results["locations"].append({
                    "path": exe["path"],
                    "name": exe["name"],
                    "category": exe.get("category", "unknown")
                })
        
        
        common_paths = {
            "steam": ["C:\\Program Files (x86)\\Steam", "C:\\Program Files\\Steam"],
            "chrome": ["C:\\Program Files\\Google\\Chrome", "C:\\Program Files (x86)\\Google\\Chrome"],
            "firefox": ["C:\\Program Files\\Mozilla Firefox", "C:\\Program Files (x86)\\Mozilla Firefox"],
            "vscode": ["C:\\Program Files\\Microsoft VS Code", "C:\\Users\\*\\AppData\\Local\\Programs\\Microsoft VS Code"]
        }
        
        if app_name_lower in common_paths:
            for path in common_paths[app_name_lower]:
                if os.path.exists(path):
                    results["found"] = True
                    results["locations"].append(f"Common path: {path}")
        
        return results
    
    def _scan_all_apps(self) -> Dict:
        
        results = self.fast_scan()
        return {
            "apps_count": len(results.get("apps", [])),
            "apps": results.get("apps", []),
            "executables": results.get("executables", []),
            "scan_time": results.get("metadata", {}).get("scan_time", "")
        }
    
    def _get_system_info(self):
        
        info = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "cpu_count": psutil.cpu_count(),
            "disks": []
        }
        
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                info["disks"].append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent_used": usage.percent
                })
            except:
                continue
        
        return info
    
    def _get_disk_analysis(self):
        
        analysis = {
            "partitions": [],
            "largest_folders": [],
            "file_types": {}
        }
        
        try:
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    analysis["partitions"].append({
                        "mountpoint": partition.mountpoint,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    })
                except:
                    continue
        except:
            pass
        
        return analysis
    
    def _analyze_disk_space(self):
        
        analysis = {
            "total_space_gb": 0,
            "used_space_gb": 0,
            "free_space_gb": 0,
            "largest_categories": []
        }
        
        try:
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    analysis["total_space_gb"] += usage.total / (1024**3)
                    analysis["used_space_gb"] += usage.used / (1024**3)
                    analysis["free_space_gb"] += usage.free / (1024**3)
                except:
                    continue
        except:
            pass
        
        return analysis
    
    def _find_duplicates(self, scan_results):
        
        duplicates = []
        file_hashes = {}
        
        
        
        files = []
        files.extend(scan_results.get("documents", []))
        files.extend(scan_results.get("media", []))
        
        for file in files:
            if isinstance(file, dict) and "name" in file:
                filename = file["name"]
                if filename in file_hashes:
                    duplicates.append({
                        "filename": filename,
                        "locations": [file_hashes[filename], file.get("path", "")]
                    })
                else:
                    file_hashes[filename] = file.get("path", "")
        
        return duplicates
    
    def _generate_cleanup_suggestions(self, scan_results):
        
        suggestions = []
        
        
        if scan_results.get("logs"):
            suggestions.append({
                "action": "clean_logs",
                "description": f"Remover {len(scan_results['logs'])} arquivos de log",
                "estimated_space": "Varia",
                "risk": "baixo"
            })
        
        
        if scan_results.get("duplicate_files"):
            suggestions.append({
                "action": "remove_duplicates",
                "description": f"Remover {len(scan_results['duplicate_files'])} arquivos duplicados",
                "estimated_space": "Varia",
                "risk": "mAdio"
            })
        
        return suggestions
    
    def _get_running_processes(self):
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['name']:
                    processes.append({
                        "name": pinfo['name'],
                        "exe": pinfo.get('exe', ''),
                        "pid": pinfo['pid'],
                        "cpu": pinfo['cpu_percent'],
                        "memory": pinfo['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        processes.sort(key=lambda x: x['memory'], reverse=True)
        return processes[:20]
    
    def _get_recent_items(self):
        
        recent_items = []
        
        if self.system == "Windows":
            recent_path = os.path.join(os.environ.get("USERPROFILE", ""), "Recent")
            if os.path.exists(recent_path):
                try:
                    for item in os.listdir(recent_path)[:15]:
                        item_path = os.path.join(recent_path, item)
                        if os.path.exists(item_path):
                            recent_items.append(item_path)
                except:
                    pass
        
        return list(set(recent_items))[:15]
    
    def _detect_usage_patterns(self):
        
        patterns = {
            "high_usage_apps": [],
            "frequent_dirs": [],
            "system_health": "good"
        }
        
        try:
            processes = self._get_running_processes()
            if processes:
                high_memory = [p for p in processes if p['memory'] > 5.0]
                patterns["high_usage_apps"] = [p['name'] for p in high_memory[:5]]
        except:
            pass
        
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            if cpu_percent > 80 or memory_percent > 85:
                patterns["system_health"] = "high_load"
            elif cpu_percent > 90 or memory_percent > 90:
                patterns["system_health"] = "critical"
        except:
            pass
        
        return patterns
    
    def _learn_from_scan(self, scan_results):
        
        if "learning" not in self.patterns:
            self.patterns["learning"] = {
                "app_categories": {},
                "user_profile": {}
            }
        
        apps = scan_results.get("apps", [])
        for app in apps:
            app_lower = app.lower()
            
            if any(word in app_lower for word in ['browser', 'chrome', 'firefox', 'edge', 'safari']):
                category = 'browser'
            elif any(word in app_lower for word in ['game', 'steam', 'epic', 'minecraft']):
                category = 'gaming'
            elif any(word in app_lower for word in ['code', 'editor', 'studio', 'pycharm', 'vscode']):
                category = 'development'
            elif any(word in app_lower for word in ['office', 'word', 'excel', 'powerpoint']):
                category = 'productivity'
            elif any(word in app_lower for word in ['media', 'player', 'vlc', 'spotify']):
                category = 'multimedia'
            elif any(word in app_lower for word in ['chat', 'message', 'whatsapp', 'discord']):
                category = 'communication'
            else:
                category = 'other'
            
            if category not in self.patterns["learning"]["app_categories"]:
                self.patterns["learning"]["app_categories"][category] = []
            
            if app not in self.patterns["learning"]["app_categories"][category]:
                self.patterns["learning"]["app_categories"][category].append(app)
        
        categories = list(self.patterns["learning"]["app_categories"].keys())
        self.patterns["learning"]["user_profile"] = {
            "app_categories": categories,
            "total_apps": len(apps),
            "last_update": datetime.now().isoformat()
        }
        
        self._save_json(pcscan.LEARNED_PATTERNS_FILE, self.patterns)
    
    def incremental_scan(self):
        
        print("Executando scan incremental...")
        
        last_summary = self.cache.get("scan_summary", {})
        if not last_summary:
            return self.quick_scan()
        
        incremental_paths = {
            "Program Files": self.priority_paths.get("Program Files"),
            "downloads": self.priority_paths.get("downloads"),
            "desktop": self.priority_paths.get("desktop"),
            "documents": self.priority_paths.get("documents")
        }
        
        new_items = {"apps": [], "documents": [], "media": []}
        
        for category, path in incremental_paths.items():
            if path and os.path.exists(path):
                try:
                    cutoff_time = time.time() - (24 * 3600)
                    
                    for entry in os.scandir(path):
                        try:
                            if entry.is_file() and entry.stat().st_mtime > cutoff_time:
                                filepath = entry.path
                                filename = os.path.basename(entry.name).lower()
                                
                                existing_apps = [app.lower() for app in last_summary.get("apps", [])]
                                if filename not in existing_apps:
                                    if os.path.splitext(filename)[1] in ['.exe', '.app', '.lnk']:
                                        new_items["apps"].append(os.path.splitext(filename)[0])
                                    elif os.path.splitext(filename)[1] in ['.pdf', '.doc', '.txt']:
                                        new_items["documents"].append({
                                            "path": filepath,
                                            "name": filename,
                                            "category": category
                                        })
                                    elif os.path.splitext(filename)[1] in ['.jpg', '.mp4', '.mp3']:
                                        new_items["media"].append({
                                            "path": filepath,
                                            "name": filename,
                                            "category": category
                                        })
                        except:
                            continue
                except:
                    continue
        
        for key in ["apps", "documents", "media"]:
            if key == "apps":
                last_summary[key] = list(set(last_summary.get(key, []) + new_items[key]))
            else:
                last_items = last_summary.get(key, [])
                new_item_paths = [item["path"] for item in new_items[key]]
                last_item_paths = [item["path"] for item in last_items]
                
                for new_item in new_items[key]:
                    if new_item["path"] not in last_item_paths:
                        last_items.append(new_item)
                
                last_summary[key] = last_items
        
        self.cache["scan_summary"] = last_summary
        self.cache["last_incremental"] = datetime.now().isoformat()
        self._save_json(pcscan.SCAN_CACHE_FILE, self.cache)
        self._load_apps_cache()
        
        print(f"OK: Scan incremental: +{len(new_items['apps'])} apps, +{len(new_items['documents'])} docs")
        return new_items
    
    def passive_learn_from_command(self, command_text, result):
        
        words = command_text.lower().split()
        apps_to_learn = []
        
        for word in words:
            if len(word) > 3 and '.' not in word:
                if word in self.apps_cache:
                    apps_to_learn.append(word)
        
        if apps_to_learn:
            self._learn_from_scan({"apps": apps_to_learn})
    
    def get_summary_for_ai(self):
        
        scan_data = self.cache.get("scan_summary", {})
        
        summary = {
            "system_type": self.system,
            "apps_count": len(scan_data.get("apps", [])),
            "top_apps": scan_data.get("apps", [])[:15],
            "recent_items_count": len(scan_data.get("recent_items", [])),
            "running_processes": len(scan_data.get("running_processes", [])),
            "patterns": self.patterns.get("learning", {}),
            "system_resources": scan_data.get("system_info", {}),
            "scan_freshness": self.cache.get("last_scan_timestamp", "unknown"),
            "app_categories": self.patterns.get("learning", {}).get("app_categories", {})
        }
        
        summary["inferred_user_type"] = self._infer_user_type()
        
        return summary
    
    def _infer_user_type(self):
        
        categories = self.patterns.get("learning", {}).get("app_categories", {})
        
        user_types = []
        
        if categories.get('development'):
            user_types.append("developer")
        if categories.get('gaming'):
            user_types.append("gamer")
        if categories.get('productivity'):
            user_types.append("professional")
        if categories.get('multimedia'):
            user_types.append("creative")
        
        return user_types if user_types else ["general"]
    
    def search_app(self, app_name):
        
        app_name_lower = app_name.lower()
        
        for app in self.apps_cache:
            if app_name_lower in app:
                scan_data = self.cache.get("scan_summary", {})
                executables = scan_data.get("executables", [])
                
                for exe in executables:
                    if exe["name"].lower() == app or app_name_lower in exe["name"].lower():
                        return {
                            "found": True,
                            "name": exe["name"],
                            "path": exe["path"],
                            "category": exe.get("category", "unknown")
                        }
        
        return {"found": False, "name": app_name}
    
    def get_system_status(self):
        
        status = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {},
            "running_apps": []
        }
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                status["disk_usage"][partition.mountpoint] = {
                    "total_gb": round(usage.total / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent_used": usage.percent
                }
            except:
                continue
        
        processes = self._get_running_processes()
        status["running_apps"] = processes[:10]
        
        if status["cpu_percent"] > 80 or status["memory_percent"] > 85:
            status["health"] = "WARNING: High Load"
        elif status["cpu_percent"] > 90 or status["memory_percent"] > 90:
            status["health"] = "Ys  Critical"
        else:
            status["health"] = "OK: Good"
        
        return status
    
    def print_statistics(self):
        
        stats = self.cache.get("stats", {})
        patterns = self.patterns
        
        print("\n" + "="*60)
        print("PC SCAN ESTATASTICAS")
        print("="*60)
        print(f"   - Asltimo scan: {self.cache.get('last_scan_timestamp', 'Nunca')}")
        print(f"   - Apps encontrados: {stats.get('apps_found', 0)}")
        print(f"   - Documentos: {stats.get('documents_found', 0)}")
        print(f"   - Arquivos de mAdia: {stats.get('media_found', 0)}")
        print(f"   - Scans no histA3rico: {len(self.history)}")
        
        if patterns.get("learning", {}).get("app_categories"):
            print(f"\n   Categorias de Apps:")
            for category, apps in patterns["learning"]["app_categories"].items():
                print(f"      - {category}: {len(apps)} apps")
        
        print("="*60)
    
    def is_app_installed(self, app_name):
        
        return any(app_name.lower() in app for app in self.apps_cache)
    
    def get_app_path(self, app_name):
        
        scan_data = self.cache.get("scan_summary", {})
        executables = scan_data.get("executables", [])
        
        for exe in executables:
            if app_name.lower() in exe["name"].lower():
                return exe["path"]
        
        return None

    def export_normalized_app_inventory(self):
        
        scan_data = self.cache.get("scan_summary", {})
        executables = scan_data.get("executables", [])
        inventory = []
        for exe in executables:
            name = str(exe.get("name", "")).strip().lower()
            if not name:
                continue
            inventory.append(
                {
                    "name": name,
                    "path": exe.get("path", ""),
                    "category": exe.get("category", "unknown"),
                }
            )

        
        if not inventory and self.apps_cache:
            inventory = [{"name": app, "path": "", "category": "cache"} for app in sorted(self.apps_cache)]
        return inventory

    def get_app_usage_frequencies(self):
        
        frequencies = {}
        categories = self.patterns.get("learning", {}).get("app_categories", {})
        for apps in categories.values():
            for app in apps:
                key = str(app).lower().strip()
                if not key:
                    continue
                frequencies[key] = frequencies.get(key, 0) + 1
        return frequencies
    
    def benchmark_scans(self):
        
        print("ai   Executando benchmark de scans...")
        
        results = {}
        
        
        print("\nas Executando FAST SCAN...")
        start = time.time()
        fast_results = self.fast_scan()
        fast_time = time.time() - start
        
        
        print("\nExecutando QUICK SCAN...")
        start = time.time()
        quick_results = self.quick_scan()
        quick_time = time.time() - start
        
        
        print("\nExecutando DEEP SCAN...")
        start = time.time()
        deep_results = self.deep_scan()
        deep_time = time.time() - start
        
        comparison = {
            "fast": {
                "time": fast_time,
                "apps": len(fast_results.get("apps", [])),
                "total_items": fast_results.get("total_items", 0)
            },
            "quick": {
                "time": quick_time,
                "apps": len(quick_results.get("apps", [])),
                "documents": len(quick_results.get("documents", [])),
                "media": len(quick_results.get("media", [])),
                "total_items": len(quick_results.get("apps", [])) + 
                              len(quick_results.get("documents", [])) + 
                              len(quick_results.get("media", []))
            },
            "deep": {
                "time": deep_time,
                "apps": len(deep_results.get("apps", [])),
                "documents": len(deep_results.get("documents", [])),
                "media": len(deep_results.get("media", [])),
                "system_files": len(deep_results.get("system_files", [])),
                "total_items": len(deep_results.get("apps", [])) + 
                              len(deep_results.get("documents", [])) + 
                              len(deep_results.get("media", [])) + 
                              len(deep_results.get("system_files", []))
            }
        }
        
        print("\n" + "="*60)
        print("BENCHMARK RESULTS")
        print("="*60)
        print(f"as FAST SCAN:    {fast_time:.1f}s - {comparison['fast']['apps']} apps")
        print(f"QUICK SCAN:   {quick_time:.1f}s - {comparison['quick']['apps']} apps, " +
              f"{comparison['quick']['documents']} docs, {comparison['quick']['media']} media")
        print(f"DEEP SCAN:    {deep_time:.1f}s - {comparison['deep']['apps']} apps, " +
              f"{comparison['deep']['documents']} docs, {comparison['deep']['media']} media, " +
              f"{comparison['deep']['system_files']} system files")
        print("="*60)
        
        return comparison
