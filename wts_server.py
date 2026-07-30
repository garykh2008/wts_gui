import sys
import os
import re
import json
import logging
import zipfile
import shutil
import threading
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("wts")

# Global variables for application state
DATA_DIR = ""
RESOURCE_DIR = ""
LOG_DIR_PATH = ""
TMS_CLIENT_CONF_PATH = ""
NOT_SUPPORT_DEFAULT_PATH = ""
WTS_EXECUTABLE_PATH = ""
USE_WSL = False
LINUX_EDITOR_COMMAND = None

# Current active test runner state
RUNNER_LOCK = threading.Lock()
ACTIVE_SUBPROCESS = None
OUTPUT_HISTORY = []
# Absolute index of OUTPUT_HISTORY[0] once older lines get trimmed (see #7).
# SSE consumers track an absolute line number and subtract this base.
OUTPUT_HISTORY_BASE = 0
# Cap on retained output lines so long runs cannot exhaust memory. When the
# buffer exceeds MAX, it is trimmed back down to KEEP and the base advances.
OUTPUT_HISTORY_MAX = 200000
OUTPUT_HISTORY_KEEP = 150000
IS_RUNNING = False
# Snapshot of log-folder names present when the current run started, used to
# scope "current run only" analytics to genuinely new folders (replaces the
# fragile time.time()-3.0 heuristic).
CURRENT_RUN_BASELINE_FOLDERS = set()

# Session Settings File
SETTINGS_FILE = "wts_gui.settings.json"
SESSION_SETTINGS = {}

import time
import webbrowser

LAST_HEARTBEAT = time.time()

def init_paths():
    global DATA_DIR, RESOURCE_DIR, LOG_DIR_PATH, TMS_CLIENT_CONF_PATH, NOT_SUPPORT_DEFAULT_PATH
    global WTS_EXECUTABLE_PATH, USE_WSL, LINUX_EDITOR_COMMAND, SESSION_SETTINGS
    
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        DATA_DIR = os.path.dirname(sys.executable)
        RESOURCE_DIR = sys._MEIPASS
    else:
        DATA_DIR = os.path.dirname(os.path.abspath(__file__))
        RESOURCE_DIR = DATA_DIR

    LOG_DIR_PATH = os.path.join(DATA_DIR, 'log')
    TMS_CLIENT_CONF_PATH = os.path.join(os.path.dirname(DATA_DIR), 'config', 'TmsClient.conf')
    NOT_SUPPORT_DEFAULT_PATH = os.path.join(DATA_DIR, "wts_not_support.json")

    WTS_EXECUTABLE_PATH = os.path.join(DATA_DIR, 'wts')
    if os.name == 'nt':
        wts_exe_path = os.path.join(DATA_DIR, 'wts.exe')
        if os.path.exists(wts_exe_path):
            WTS_EXECUTABLE_PATH = wts_exe_path
        else:
            USE_WSL = True
            
    if os.name != 'nt':
        for e in ['gedit', 'xdg-open', 'kate', 'mousepad']:
            if shutil.which(e):
                LINUX_EDITOR_COMMAND = [e]
                break

    # Load session settings
    settings_path = os.path.join(DATA_DIR, SETTINGS_FILE)
    logger.debug(f"Loading session settings from: {settings_path}")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                SESSION_SETTINGS = json.load(f)
            logger.debug(f"Loaded session settings: {SESSION_SETTINGS}")
        except Exception as e:
            logger.error(f"Failed to load session settings: {e}")
    else:
        logger.debug(f"Session settings file does not exist.")

def save_session():
    try:
        settings_path = os.path.join(DATA_DIR, SETTINGS_FILE)
        logger.debug(f"Saving session settings to: {settings_path}")
        logger.debug(f"Session settings content: {SESSION_SETTINGS}")
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(SESSION_SETTINGS, f, indent=4)
        logger.debug(f"Session settings saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save session settings: {e}")

# --- Configuration File Parsers ---

def load_config_data(p):
    if not os.path.exists(p):
        return [], {}
    
    config_data = []
    device_lines = {}
    
    with open(p, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            s = line.strip()
            if s.startswith("#$") or s.startswith("$"):
                config_data.append({'original': line, 'modified': line, 'type': 'other', 'device': None, 'key': "", 'value': ""})
                continue

            tk = s.lstrip('#').strip()
            it, dev = 'other', None
            
            if tk.lower().startswith("wfa_control_agent_"):
                parts = tk.split('!')
                if len(parts) > 1:
                    cand = parts[0][len("wfa_control_agent_"):].lower()
                    if (cand.endswith('_ap') or cand.endswith('_sta')) and not cand.startswith('capture_') and not cand.startswith('sniff_'):
                        dev = cand
                        device_lines.setdefault(dev, []).append(i)
            
            k, v = tk, ""
            if tk:
                if tk.startswith("define!") and tk.count('!') >= 2:
                    parts = tk.split('!', 2)
                    k, v, it = parts[1], parts[2].rstrip('!'), 'define_kv_pair'
                elif '!' in tk:
                    parts = tk.split('!', 1)
                    k_cand = parts[0]
                    v_cand = parts[1].rstrip('!')
                    if k_cand and (v_cand or "ipaddr=" in v_cand):
                        k, v, it = k_cand, v_cand, ('ip_port_pair' if "ipaddr=" in v_cand else 'kv_pair')
            
            config_data.append({'original': line, 'modified': line, 'type': it, 'device': dev, 'key': k, 'value': v})
            
    return config_data, device_lines

def parse_tms_conf(path):
    """Parse a TmsClient.conf into a list of line records.

    Each record is {index, original, key, value, type}, where 'type' is
    'kv_pair' for an uncommented KEY=VALUE line and 'comment' otherwise.
    Shared by the tms-config GET/save/toggle endpoints.
    """
    records = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f):
                s = line.strip()
                k, v, t = s, "", "comment"
                if s and not s.startswith('#') and '=' in s:
                    parts = s.split('=', 1)
                    k, v, t = parts[0].strip(), parts[1].strip(), "kv_pair"
                records.append({'index': idx, 'original': line, 'key': k, 'value': v, 'type': t})
    return records

def parse_xml_data(p):
    try:
        with open(p, 'r', encoding='utf-8') as f:
            root = ET.parse(f).getroot()
            xml_test_cases = {el.tag: el for el in root if el.tag}
            ut = set()
            for el in xml_test_cases.values():
                tb = el.find('TB_LIST')
                if tb is not None and tb.text:
                    ut.update([t.strip() for t in tb.text.split(',') if t.strip()])
            all_testbeds = sorted(list(ut))
            xml_test_case_names = sorted(xml_test_cases.keys())
            
            # Form detailed info for each test case
            details = {}
            for name, el in xml_test_cases.items():
                details[name] = {}
                def recurse(pel, pre=""):
                    for c in pel:
                        if len(list(c)) > 0:
                            recurse(c, f"{pre}{c.tag}.")
                        elif c.text and c.text.strip():
                            details[name][f"{pre}{c.tag}"] = c.text.strip()
                recurse(el)
            return xml_test_case_names, all_testbeds, details
    except Exception as e:
        logger.error(f"Error parsing XML: {e}")
        return [], [], {}

def locate_wts_executable(config_path):
    if not config_path:
        return WTS_EXECUTABLE_PATH
        
    config_dir = os.path.dirname(config_path)
    
    # Candidate 1: Same directory as config file (e.g. WTS_root/bin/)
    for name in ['wts.exe', 'wts']:
        p = os.path.join(config_dir, name)
        if os.path.exists(p):
            return p
            
    # Candidate 2: Sibling 'bin' directory (e.g. if config is in WTS_root/config/)
    sibling_bin = os.path.join(os.path.dirname(config_dir), 'bin')
    for name in ['wts.exe', 'wts']:
        p = os.path.join(sibling_bin, name)
        if os.path.exists(p):
            return p
            
    # Candidate 3: parent directory
    parent_dir = os.path.dirname(config_dir)
    for name in ['wts.exe', 'wts']:
        p = os.path.join(parent_dir, name)
        if os.path.exists(p):
            return p
            
    # Fallback to default
    return WTS_EXECUTABLE_PATH

def resolve_wts_paths(config_path):
    if not config_path:
        return {
            "wts_root": "",
            "bin_dir": DATA_DIR,
            "log_dir": os.path.join(DATA_DIR, 'log'),
            "config_dir": os.path.join(os.path.dirname(DATA_DIR), 'config'),
            "tms_conf": os.path.join(os.path.dirname(DATA_DIR), 'config', 'TmsClient.conf'),
            "not_support": os.path.join(DATA_DIR, "wts_not_support.json"),
            "wts_exe": WTS_EXECUTABLE_PATH
        }
        
    config_dir = os.path.dirname(os.path.abspath(config_path))
    
    # Primary UCC layout: config file is in UCC/cmds/<Role>/
    # wts relative to config file: ../../bin
    # log relative to config file: ../../bin/log
    # TmsClient.conf relative to config file: ../../config
    bin_dir_primary = os.path.abspath(os.path.join(config_dir, '..', '..', 'bin'))
    log_dir_primary = os.path.join(bin_dir_primary, 'log')
    config_dir_primary = os.path.abspath(os.path.join(config_dir, '..', '..', 'config'))
    tms_conf_primary = os.path.join(config_dir_primary, 'TmsClient.conf')
    not_support_primary = os.path.join(bin_dir_primary, "wts_not_support.json")
    
    # Detect primary executable
    wts_exe_primary = os.path.join(bin_dir_primary, 'wts')
    if os.name == 'nt':
        wts_exe_path = os.path.join(bin_dir_primary, 'wts.exe')
        if os.path.exists(wts_exe_path):
            wts_exe_primary = wts_exe_path
    else:
        if os.path.exists(os.path.join(bin_dir_primary, 'wts')):
            wts_exe_primary = os.path.join(bin_dir_primary, 'wts')
            
    # Check if primary UCC layout files or directories actually exist on disk
    if os.path.exists(bin_dir_primary) or os.path.exists(tms_conf_primary):
        return {
            "wts_root": os.path.abspath(os.path.join(config_dir, '..', '..')),
            "bin_dir": bin_dir_primary,
            "log_dir": log_dir_primary,
            "config_dir": config_dir_primary,
            "tms_conf": tms_conf_primary,
            "not_support": not_support_primary,
            "wts_exe": wts_exe_primary
        }
        
    # Fallback to secondary layout
    wts_exe = locate_wts_executable(config_path)
    bin_dir = os.path.dirname(wts_exe)
    
    if os.path.basename(config_dir) == 'bin':
        wts_root = os.path.dirname(config_dir)
    elif os.path.basename(config_dir) == 'config':
        wts_root = os.path.dirname(config_dir)
    else:
        wts_root = os.path.dirname(bin_dir) if bin_dir != DATA_DIR else config_dir
            
    log_dir = os.path.join(bin_dir, 'log')
    config_dir_path = os.path.join(wts_root, 'config')
    tms_conf = os.path.join(config_dir_path, 'TmsClient.conf')
    not_support = os.path.join(bin_dir, "wts_not_support.json")
    
    return {
        "wts_root": wts_root,
        "bin_dir": bin_dir,
        "log_dir": log_dir,
        "config_dir": config_dir_path,
        "tms_conf": tms_conf,
        "not_support": not_support,
        "wts_exe": wts_exe
    }

def get_active_wts_paths():
    cfg_path = SESSION_SETTINGS.get("config_path", "")
    return resolve_wts_paths(cfg_path)

def safe_path_within(base_dir, *parts):
    """Join *parts under base_dir and confirm the result stays inside base_dir.

    Returns the absolute path, or None if the join escapes base_dir (e.g. via
    '..' or an absolute path). Used to guard the log/download endpoints against
    path traversal and arbitrary-file access.
    """
    if not base_dir:
        return None
    base_abs = os.path.abspath(base_dir)
    candidate = os.path.abspath(os.path.join(base_abs, *parts))
    if candidate == base_abs or candidate.startswith(base_abs + os.sep):
        return candidate
    return None

# --- Subprocess execution background thread ---

def to_wsl_path(win_path):
    if not win_path:
        return ""
    win_path = os.path.abspath(win_path)
    match = re.match(r'^([a-zA-Z]):(.*)$', win_path)
    if match:
        drive = match.group(1).lower()
        path = match.group(2).replace('\\', '/')
        return f"/mnt/{drive}{path}"
    return win_path.replace('\\', '/')

def parse_date_from_folder_name(name):
    # Try format 1: Month-DD-YYYY (e.g. Jun-26-2026)
    m1 = re.search(r'([A-Za-z]{3}-\d{1,2}-\d{4})', name)
    if m1:
        try:
            return datetime.strptime(m1.group(1), "%b-%d-%Y").date()
        except Exception: pass
        
    # Try format 2: YYYY-MM-DD (e.g. 2026-06-26)
    m2 = re.search(r'(\d{4}-\d{2}-\d{2})', name)
    if m2:
        try:
            return datetime.strptime(m2.group(1), "%Y-%m-%d").date()
        except Exception: pass
        
    # Try format 3: YYYY_MM_DD (e.g. 2026_06_26)
    m3 = re.search(r'(\d{4}_\d{2}_\d{2})', name)
    if m3:
        try:
            return datetime.strptime(m3.group(1), "%Y_%m_%d").date()
        except Exception: pass
        
    # Try format 4: YYYYMMDD (e.g. 20260626)
    m4 = re.search(r'(\d{8})', name)
    if m4:
        try:
            return datetime.strptime(m4.group(1), "%Y%m%d").date()
        except Exception: pass
        
    return None

def _append_output(line):
    """Append one line of runner output, trimming the buffer if it grows past
    OUTPUT_HISTORY_MAX so a long run cannot exhaust memory."""
    global OUTPUT_HISTORY_BASE
    OUTPUT_HISTORY.append(line)
    if len(OUTPUT_HISTORY) > OUTPUT_HISTORY_MAX:
        drop = len(OUTPUT_HISTORY) - OUTPUT_HISTORY_KEEP
        del OUTPUT_HISTORY[:drop]
        OUTPUT_HISTORY_BASE += drop

def run_tests_thread(cmd, use_wsl, cwd=None):
    global ACTIVE_SUBPROCESS, IS_RUNNING

    cmd_to_run = cmd
    if os.name == 'nt' and use_wsl:
        wsl_exe_path = to_wsl_path(cmd[0])
        cmd_to_run = ["wsl.exe", wsl_exe_path] + cmd[1:]

    env = dict(os.environ)
    if hasattr(sys, '_MEIPASS'):
        for key in ['LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH']:
            orig_key = key + '_ORIG'
            if orig_key in env:
                env[key] = env[orig_key]
            else:
                env.pop(key, None)

    try:
        ACTIVE_SUBPROCESS = subprocess.Popen(
            cmd_to_run, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            env=env,
            cwd=cwd,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        for line in iter(ACTIVE_SUBPROCESS.stdout.readline, ''):
            if line:
                _append_output(line)

        ACTIVE_SUBPROCESS.stdout.close()
        ACTIVE_SUBPROCESS.wait()
    except Exception as e:
        _append_output(f"Error running command: {e}\n")
    finally:
        with RUNNER_LOCK:
            IS_RUNNING = False
            ACTIVE_SUBPROCESS = None

def find_paired_wireless_ip_index(config_data, agent_idx):
    if agent_idx < 0 or agent_idx >= len(config_data):
        return None
    
    agent_d = config_data[agent_idx]
    dev = agent_d.get("device")
    if not dev:
        return None
        
    val = agent_d.get("value", "")
    match = re.search(r'ipaddr=([^,!]+)', val)
    ip = match.group(1).strip() if match else ""
    
    # Target keys can either start with $ or not
    target_keys = {
        f"${dev}_wireless_ip".lower(),
        f"{dev}_wireless_ip".lower()
    }
    
    # 1. Proximity Search (scan forward up to 3 lines)
    for offset in range(1, 4):
        next_idx = agent_idx + offset
        if next_idx < len(config_data):
            d = config_data[next_idx]
            if d.get("type") in ("define_kv_pair", "kv_pair"):
                k = d.get("key", "").strip().lower()
                if k in target_keys:
                    logger.debug(f"Proximity matched paired wireless IP '{k}' at index {next_idx} for device {dev}")
                    return next_idx
                    
    # 2. Fallback Search (entire file match using IP address if available)
    if ip:
        for idx, d in enumerate(config_data):
            if d.get("type") in ("define_kv_pair", "kv_pair"):
                k = d.get("key", "").strip().lower()
                v = d.get("value", "").strip()
                if k in target_keys and v == ip:
                    logger.debug(f"IP matched paired wireless IP '{k}' at index {idx} for device {dev}")
                    return idx
                    
    return None

# --- Helper Functions for Checking Device Status (Check Alive) ---
def is_valid_ip(s):
    s = s.strip()
    try:
        socket.inet_aton(s)
        return True
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, s)
        return True
    except (socket.error, AttributeError):
        pass
    return False

def check_tcp_port(ip, port, timeout=1.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def ping_ip(ip, timeout=1.0):
    if os.name == 'nt':
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout + 0.5)
        return res.returncode == 0
    except Exception:
        return False

# --- HTTP Request Handler ---

class WtsHTTPRequestHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        logger.debug(f"[HTTP] {format%args}")
        sys.stdout.flush()
        
    def _send_cors_headers(self):
        # NOTE: The web UI is served from this same origin, so no
        # Access-Control-Allow-Origin header is emitted. Omitting it prevents
        # other websites the user is browsing from reading this local API
        # cross-origin (which would otherwise expose file read / delete / run).
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        global LAST_HEARTBEAT
        LAST_HEARTBEAT = time.time()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        
        if path.startswith("/api/"):
            self.handle_api_get(path, query)
        elif path.startswith("/web-download/"):
            self.handle_zip_download(path)
        else:
            self.handle_static_serve(path)

    def handle_zip_download(self, path):
        filename = path.replace("/web-download/", "")
        filename = os.path.basename(filename)
        file_path = safe_path_within(DATA_DIR, filename)

        if file_path and os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(os.path.getsize(file_path)))
            self._send_cors_headers()
            self.end_headers()
            try:
                # Stream in chunks so large archives don't get read fully into memory.
                with open(file_path, 'rb') as f:
                    shutil.copyfileobj(f, self.wfile)
            except Exception as e:
                logger.error(f"Failed to write download: {e}")
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        global LAST_HEARTBEAT
        LAST_HEARTBEAT = time.time()
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        # Read content length
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        if path.startswith("/api/"):
            self.handle_api_post(path, post_data)
        else:
            self.send_error(404, "Not Found")

    # Serve static frontend files
    def handle_static_serve(self, path):
        # Normalize path
        if path == "/" or path == "":
            path = "/index.html"
            
        # Static files directory
        static_dir = os.path.join(RESOURCE_DIR, "web")
        file_path = os.path.abspath(os.path.join(static_dir, path.lstrip("/")))
        
        # Security check to prevent path traversal
        if not file_path.startswith(os.path.abspath(static_dir)):
            self.send_error(403, "Access Denied")
            return
            
        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            
            # Content Type
            ext = os.path.splitext(file_path)[1].lower()
            mime_types = {
                ".html": "text/html",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".ico": "image/x-icon",
                ".svg": "image/svg+xml",
                ".woff": "font/woff",
                ".woff2": "font/woff2",
                ".ttf": "font/ttf"
            }
            content_type = mime_types.get(ext, "application/octet-stream")
            self.send_header("Content-Type", content_type)
            self._send_cors_headers()
            self.end_headers()
            
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error(404, f"File Not Found: {path}")

    # --- API GET Router ---
    def handle_api_get(self, path, query):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        
        response_data = None
        
        try:
            if path == "/api/status":
                response_data = {
                    "running": IS_RUNNING,
                    "bin_dir": DATA_DIR,
                    "settings": SESSION_SETTINGS
                }
                
            elif path == "/api/manual":
                readme_paths = [
                    os.path.join(sys._MEIPASS, "README.md") if hasattr(sys, '_MEIPASS') else None,
                    os.path.join(RESOURCE_DIR, "README.md"),
                    os.path.join(os.path.dirname(RESOURCE_DIR), "README.md"),
                    "README.md"
                ]
                content = "# Manual Missing\nDocumentation not found."
                for rp in [x for x in readme_paths if x and os.path.exists(x)]:
                    try:
                        with open(rp, "r", encoding="utf-8") as f:
                            content = f.read()
                            break
                    except Exception: pass
                
                self.end_headers()
                self.wfile.write(content.encode('utf-8'))
                return
                
            elif path == "/api/fs/list":
                target_path = query.get("path", [""])[0]
                
                # Default to drives on Windows if empty
                if not target_path:
                    if os.name == 'nt':
                        import string
                        import ctypes
                        drives = []
                        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                        for letter in string.ascii_uppercase:
                            if bitmask & 1:
                                drives.append(f"{letter}:\\")
                            bitmask >>= 1
                        response_data = {
                            "currentPath": "",
                            "parentPath": "",
                            "drives": drives,
                            "entries": []
                        }
                    else:
                        target_path = "/"
                        
                if target_path:
                    target_path = os.path.abspath(target_path)
                    if not os.path.exists(target_path) or not os.path.isdir(target_path):
                        response_data = {"error": f"Path not found: {target_path}"}
                    else:
                        parent_path = os.path.dirname(target_path)
                        if parent_path == target_path:
                            parent_path = ""
                            
                        entries = []
                        try:
                            for item in os.listdir(target_path):
                                full_p = os.path.join(target_path, item)
                                is_dir = os.path.isdir(full_p)
                                is_file = os.path.isfile(full_p)
                                is_valid_file = is_file and any(item.lower().endswith(ext) for ext in ['.txt', '.conf', '.xml'])
                                
                                if is_dir or is_valid_file:
                                    entries.append({
                                        "name": item,
                                        "isDir": is_dir
                                    })
                            entries.sort(key=lambda e: (not e["isDir"], e["name"].lower()))
                            response_data = {
                                "currentPath": target_path,
                                "parentPath": parent_path,
                                "drives": [],
                                "entries": entries
                            }
                        except Exception as e:
                            response_data = {"error": f"Failed to read directory: {str(e)}"}
                            
            elif path == "/api/config":
                cfg_path = query.get("path", [SESSION_SETTINGS.get("config_path", "")])[0]
                logger.debug(f"/api/config path: {cfg_path}")
                if not cfg_path or not os.path.exists(cfg_path):
                    logger.error(f"/api/config: File not found at {cfg_path}")
                    response_data = {"error": "Config file not found", "path": cfg_path}
                else:
                    # Cache last selected config path
                    SESSION_SETTINGS["config_path"] = cfg_path
                    save_session()
                    
                    config_data, device_lines = load_config_data(cfg_path)
                    
                    # Compute enabled status of devices
                    devices = []
                    for dev, line_indices in device_lines.items():
                        for idx in line_indices:
                            d = config_data[idx]
                            val = d["value"]
                            # Parse IP address to show in UI label
                            ip_label = ""
                            match = re.search(r'ipaddr=([^,!]+)', val)
                            if match:
                                ip_label = match.group(1)
                            
                            devices.append({
                                "name": dev,
                                "ip": ip_label,
                                "enabled": not d["modified"].strip().startswith('#'),
                                "index": idx
                            })
                        
                    response_data = {
                        "path": cfg_path,
                        "devices": devices,
                        "parameters": [
                            {
                                "index": idx,
                                "key": d["key"],
                                "value": d["value"],
                                "type": d["type"],
                                "commented": d["modified"].strip().startswith('#'),
                                "device": d["device"]
                            } for idx, d in enumerate(config_data) if d["type"] != "other"
                        ]
                    }
                    
            elif path == "/api/config/check-alive":
                cfg_path = query.get("path", [SESSION_SETTINGS.get("config_path", "")])[0]
                logger.debug(f"/api/config/check-alive path: {cfg_path}")
                if not cfg_path or not os.path.exists(cfg_path):
                    logger.error(f"/api/config/check-alive: File not found at {cfg_path}")
                    response_data = {"error": "Config file not found", "path": cfg_path}
                else:
                    config_data, device_lines = load_config_data(cfg_path)
                    
                    targets = []
                    # Identify all uncommented settings that contain IP addresses
                    for idx, d in enumerate(config_data):
                        # skip if commented out or type is 'other'
                        if d["modified"].strip().startswith('#') or d["type"] == "other":
                            continue
                        
                        key = d["key"].strip()
                        val = d["value"].strip()
                        
                        # Only check keys that look like device/component settings (start with wfa_, contain agent, or HostAPDIPAddress)
                        key_lower = key.lower()
                        if not (key_lower.startswith("wfa_") or "agent" in key_lower or key_lower == "hostapdipaddress"):
                            continue
                        
                        # Skip if key contains wireless (case-insensitive)
                        if "wireless" in key_lower:
                            continue
                            
                        # Case 1: IP + Port pair (ipaddr=X,port=Y format)
                        ip_match = re.search(r'ipaddr=([^,!]+)', val)
                        port_match = re.search(r'port=(\d+)', val)
                        
                        if ip_match:
                            ip = ip_match.group(1).strip()
                            port = int(port_match.group(1).strip()) if port_match else None
                            if ip:
                                targets.append({
                                    "key": key,
                                    "ip": ip,
                                    "port": port,
                                    "type": "tcp" if port is not None else "ping"
                                })
                        else:
                            # Case 2: raw value might be an IP address without port
                            if is_valid_ip(val):
                                targets.append({
                                    "key": key,
                                    "ip": val,
                                    "port": None,
                                    "type": "ping"
                                })
                                
                    # Execute checks in parallel
                    def check_target(t):
                        status = "offline"
                        if t["type"] == "tcp":
                            if check_tcp_port(t["ip"], t["port"]):
                                status = "online"
                        else:
                            if ping_ip(t["ip"]):
                                status = "online"
                        return {
                            "key": t["key"],
                            "ip": t["ip"],
                            "port": t["port"],
                            "type": t["type"],
                            "status": status
                        }
                    
                    results = []
                    if targets:
                        with ThreadPoolExecutor(max_workers=min(len(targets), 16)) as executor:
                            results = list(executor.map(check_target, targets))
                            
                    response_data = {"success": True, "results": results}
                    
            elif path == "/api/xml-data":
                cfg_path = query.get("path", [SESSION_SETTINGS.get("config_path", "")])[0]
                logger.debug(f"/api/xml-data config path: {cfg_path}")
                if cfg_path and os.path.exists(cfg_path):
                    xml_path = os.path.join(os.path.dirname(cfg_path), 'MasterTestInfo.xml')
                    logger.debug(f"/api/xml-data searching MasterTestInfo.xml at: {xml_path}")
                    if os.path.exists(xml_path):
                        case_names, testbeds, details = parse_xml_data(xml_path)
                        response_data = {
                            "testCases": case_names,
                            "testbeds": testbeds,
                            "details": details
                        }
                    else:
                        logger.error(f"/api/xml-data: MasterTestInfo.xml not found at {xml_path}")
                        response_data = {"error": "MasterTestInfo.xml not found near configuration"}
                else:
                    logger.error(f"/api/xml-data: Config path does not exist: {cfg_path}")
                    response_data = {"error": "Select AllInitConfig first to load XML test specifications"}
                    
            elif path == "/api/exclude":
                ex_path = get_active_wts_paths()["not_support"]
                logger.debug(f"/api/exclude path: {ex_path}")
                exclusions = []
                if os.path.exists(ex_path):
                    try:
                        with open(ex_path, 'r', encoding='utf-8') as f:
                            exclusions = json.load(f)
                    except Exception: pass
                else:
                    logger.debug(f"/api/exclude file not found at: {ex_path} (will use empty list)")
                response_data = {
                    "path": ex_path,
                    "exclusions": exclusions
                }
                
            elif path == "/api/tms-config":
                tms_conf_path = get_active_wts_paths()["tms_conf"]
                logger.debug(f"/api/tms-config path: {tms_conf_path}")
                if not os.path.exists(tms_conf_path):
                    logger.error(f"/api/tms-config: File not found at {tms_conf_path}")
                tms_records = parse_tms_conf(tms_conf_path)
                tms_upload_enabled = any(
                    r["key"] == "TMS_feature" and r["value"].lower() == "enabled"
                    for r in tms_records if r["type"] == "kv_pair"
                )
                tms_tree = [
                    {"index": r["index"], "key": r["key"], "value": r["value"],
                     "type": r["type"], "original": r["original"]}
                    for r in tms_records
                ]
                response_data = {
                    "path": tms_conf_path,
                    "parameters": tms_tree,
                    "tmsUploadEnabled": tms_upload_enabled
                }
                
            elif path == "/api/logs":
                start_date_str = query.get("startDate", [""])[0]
                if start_date_str:
                    SESSION_SETTINGS["log_filter_date"] = start_date_str
                    save_session()
                folders = []
                log_dir = get_active_wts_paths()["log_dir"]
                logger.debug(f"/api/logs directory: {log_dir}")
                if os.path.exists(log_dir):
                    dirs = sorted(
                        [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))],
                        key=lambda d: os.path.getmtime(os.path.join(log_dir, d)),
                        reverse=True
                    )
                    
                    filter_date = None
                    if start_date_str:
                        try: filter_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                        except Exception: pass
                        
                    for d in dirs:
                        folder_date = parse_date_from_folder_name(d)
                        if folder_date and filter_date and folder_date < filter_date:
                            continue
                        folders.append(d)
                else:
                    logger.error(f"/api/logs: Directory not found at {log_dir}")
                response_data = {"folders": folders}
                
            elif path == "/api/logs/files":
                folder = query.get("folder", [""])[0]
                files = []
                if folder:
                    log_dir = get_active_wts_paths()["log_dir"]
                    p = safe_path_within(log_dir, folder)
                    logger.debug(f"/api/logs/files path: {p}")
                    if p and os.path.exists(p) and os.path.isdir(p):
                        for f in sorted(os.listdir(p)):
                            if f.lower().endswith(".log") or "pcap" in f.lower():
                                fp = os.path.join(p, f)
                                files.append({
                                    "name": f,
                                    "size": f"{os.path.getsize(fp)/1024:.1f} KB"
                                })
                    else:
                        logger.error(f"/api/logs/files: Directory not found at {p}")
                response_data = {"files": files}
                
            elif path == "/api/logs/view":
                folder = query.get("folder", [""])[0]
                file_name = query.get("file", [""])[0]
                if folder and file_name:
                    log_dir = get_active_wts_paths()["log_dir"]
                    if folder == ".":
                        # Only files sitting directly in DATA_DIR, by basename.
                        # Reject absolute paths / traversal to prevent arbitrary reads.
                        p = safe_path_within(DATA_DIR, os.path.basename(file_name))
                    else:
                        p = safe_path_within(log_dir, folder, file_name)

                    logger.debug(f"/api/logs/view path: {p}")
                    if p and os.path.exists(p):
                        lower_name = file_name.lower()
                        if lower_name.endswith(".log") or lower_name.endswith(".md") or lower_name.endswith(".conf") or lower_name.endswith(".txt"):
                            # Read text file
                            self.end_headers()
                            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                                self.wfile.write(f.read().encode('utf-8'))
                            return
                        else:
                            # It's binary (pcap). Download it.
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/octet-stream')
                            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_name)}"')
                            self.send_header('Content-Length', str(os.path.getsize(p)))
                            self._send_cors_headers()
                            self.end_headers()
                            # Stream in chunks; pcap captures can be large.
                            with open(p, 'rb') as f:
                                shutil.copyfileobj(f, self.wfile)
                            return
                    else:
                        logger.error(f"/api/logs/view: File not found at {p}")
                response_data = {"error": "File not found"}
                
            elif path == "/api/results":
                # Scans results in log/ for specific test cases
                # Returns latest status (PASS, FAIL, NT, Not Support) for each test case
                role = query.get("role", ["All"])[0]
                start_date_str = query.get("startDate", [""])[0]
                if start_date_str:
                    SESSION_SETTINGS["result_filter_date"] = start_date_str
                    save_session()
                cfg_path = query.get("path", [""])[0]
                
                wts_paths = resolve_wts_paths(cfg_path)
                log_dir = wts_paths["log_dir"]
                xml_path = os.path.join(os.path.dirname(cfg_path), 'MasterTestInfo.xml') if cfg_path else ""
                logger.debug(f"/api/results scanning path: {log_dir}, xml: {xml_path}")
                
                case_names = []
                if xml_path and os.path.exists(xml_path):
                    try:
                        root = ET.parse(xml_path).getroot()
                        case_names = sorted([el.tag for el in root if el.tag])
                    except Exception: pass
                else:
                    logger.error(f"/api/results: XML file not found at {xml_path}")
                
                # Excluded list
                ex_path = wts_paths["not_support"]
                not_support_list = set()
                if os.path.exists(ex_path):
                    try:
                        with open(ex_path, 'r', encoding='utf-8') as f:
                            not_support_list = set(json.load(f))
                    except Exception: pass
                
                current_run_only = query.get("currentRunOnly", ["false"])[0].lower() == "true"
                
                # Filters
                tc_targets = []
                for n in case_names:
                    if role == "AP" and not n.split('-', 1)[-1].startswith('4.'): continue
                    if role == "STA" and not n.split('-', 1)[-1].startswith('5.'): continue
                    tc_targets.append(n)
                    
                filter_date = None
                if start_date_str:
                    try: filter_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                    except Exception: pass
                    
                test_history_map = {}
                if os.path.exists(log_dir):
                    dirs = sorted(
                        [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))],
                        key=lambda d: os.path.getmtime(os.path.join(log_dir, d))
                    )
                    for f in dirs:
                        folder_path = os.path.join(log_dir, f)
                        if current_run_only:
                            # Only folders that did not exist when the run started.
                            if f in CURRENT_RUN_BASELINE_FOLDERS:
                                continue
                        else:
                            folder_date = parse_date_from_folder_name(f)
                            if folder_date and filter_date and folder_date < filter_date:
                                continue
                        p = folder_path
                        for file in os.listdir(p):
                            if file.startswith("log_") and file.endswith(".log"):
                                tc = file[4:-4]
                                if tc in tc_targets:
                                    try:
                                        with open(os.path.join(p, file), 'r', encoding='utf-8', errors='ignore') as logf:
                                            content = logf.read()
                                        
                                        # Only record result if test case has actually finished executing
                                        if "FINAL TEST RESULT" in content or "END: TEST CASE" in content or "Execution Time [" in content or "Stopping FTP server" in content:
                                            if re.search(r'FINAL TEST RESULT\s*--->\s*PASS', content, re.IGNORECASE) or "\nPASS\n" in content:
                                                res = "PASS"
                                            else:
                                                res = "FAIL"
                                            test_history_map.setdefault(tc, []).append({'result': res, 'folder': f})
                                    except Exception:
                                        pass
                
                # Generate final list
                results = []
                for tc in tc_targets:
                    hist = test_history_map.get(tc, [])
                    res, folder = "NT", ""
                    if tc in not_support_list:
                        res = "Not Support"
                    elif hist:
                        res, folder = hist[-1]['result'], hist[-1]['folder']
                        
                    results.append({
                        "case": tc,
                        "status": res,
                        "logFolder": folder,
                        "history": list(reversed(hist)) # latest run first
                    })
                response_data = {"results": results}
                
            elif path == "/api/run/stream":
                # Server Sent Events (SSE) streaming of test runner output
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self._send_cors_headers()
                self.end_headers()
                
                # sent_index is an ABSOLUTE line number. OUTPUT_HISTORY may be
                # trimmed from the front (OUTPUT_HISTORY_BASE tracks how many
                # lines were dropped), so we translate to a local index each
                # iteration and skip ahead if the client fell behind the window.
                sent_index = 0
                while True:
                    try:
                        wrote_any = False
                        while True:
                            local_idx = sent_index - OUTPUT_HISTORY_BASE
                            if local_idx < 0:
                                # Client is behind the trimmed window; jump forward.
                                sent_index = OUTPUT_HISTORY_BASE
                                continue
                            if local_idx >= len(OUTPUT_HISTORY):
                                break
                            line = OUTPUT_HISTORY[local_idx]
                            self.wfile.write(f"data: {json.dumps(line)}\n\n".encode('utf-8'))
                            sent_index += 1
                            wrote_any = True
                        if wrote_any:
                            self.wfile.flush()
                        elif not IS_RUNNING:
                            # Test run is finished
                            self.wfile.write(b"event: finished\ndata: \n\n")
                            self.wfile.flush()
                            break
                        else:
                            # Send heartbeat to keep connection alive
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                            time.sleep(0.2)
                    except Exception:
                        # Client disconnected
                        break
                return
            
            else:
                self.send_error(404, f"API Route Not Found: {path}")
                return
                
        except Exception as e:
            response_data = {"error": f"Internal Server Error: {str(e)}"}
            
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    # --- API POST Router ---
    def handle_api_post(self, path, post_data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self._send_cors_headers()
        
        response_data = None
        
        try:
            # Parse json body
            body = {}
            if post_data:
                try: body = json.loads(post_data.decode('utf-8'))
                except Exception: pass
                
            if path == "/api/config/save":
                cfg_path = body.get("path", "")
                parameters = body.get("parameters", [])
                
                if not cfg_path or not os.path.exists(cfg_path):
                    response_data = {"error": "Invalid configuration path"}
                else:
                    config_data, _ = load_config_data(cfg_path)
                    
                    # Update configuration lines
                    for param in parameters:
                        idx = param.get("index")
                        val = param.get("value")
                        commented = param.get("commented", False)
                        
                        if idx is not None and 0 <= idx < len(config_data):
                            d = config_data[idx]
                            k = d['key']
                            
                            new_line = ""
                            if d['type'] == 'define_kv_pair':
                                new_line = f"define!{k}!{val}!\n"
                            elif d['type'] in ['kv_pair', 'ip_port_pair']:
                                new_line = f"{k}!{val}!\n"
                                
                            if commented:
                                config_data[idx]['modified'] = "# " + new_line
                            else:
                                config_data[idx]['modified'] = new_line
                                
                    # Save back to file
                    try:
                        with open(cfg_path, 'w', encoding='utf-8', newline='\n') as f:
                            for d in config_data:
                                f.write(d['modified'])
                        response_data = {"success": True, "message": "Config saved successfully"}
                    except Exception as e:
                        response_data = {"error": f"Failed to save file: {str(e)}"}
                        
            elif path == "/api/config/toggle-device":
                cfg_path = body.get("path", "")
                idx = body.get("index")
                enabled = body.get("enabled", True)
                
                if not cfg_path or not os.path.exists(cfg_path):
                    response_data = {"error": "Invalid configuration path"}
                elif idx is None:
                    response_data = {"error": "Missing parameter index"}
                else:
                    config_data, device_lines = load_config_data(cfg_path)
                    if 0 <= idx < len(config_data):
                        dev = config_data[idx].get("device")
                        
                        def set_line_state(line_idx, state_enabled):
                            curr = config_data[line_idx]['modified']
                            if state_enabled:
                                config_data[line_idx]['modified'] = curr.lstrip()[1:].lstrip() if curr.lstrip().startswith('#') else curr
                            else:
                                config_data[line_idx]['modified'] = "# " + curr if not curr.lstrip().startswith('#') else curr
                            
                            paired_idx = find_paired_wireless_ip_index(config_data, line_idx)
                            if paired_idx is not None:
                                curr_paired = config_data[paired_idx]['modified']
                                if state_enabled:
                                    config_data[paired_idx]['modified'] = curr_paired.lstrip()[1:].lstrip() if curr_paired.lstrip().startswith('#') else curr_paired
                                else:
                                    config_data[paired_idx]['modified'] = "# " + curr_paired if not curr_paired.lstrip().startswith('#') else curr_paired
                        
                        if enabled:
                            set_line_state(idx, True)
                            if dev and dev in device_lines:
                                for other_idx in device_lines[dev]:
                                    if other_idx != idx:
                                        set_line_state(other_idx, False)
                        else:
                            set_line_state(idx, False)
                        
                        # Save changes
                        try:
                            with open(cfg_path, 'w', encoding='utf-8', newline='\n') as f:
                                for d in config_data:
                                    f.write(d['modified'])
                            response_data = {"success": True}
                        except Exception as e:
                            response_data = {"error": f"Failed to save configuration: {str(e)}"}
                    else:
                        response_data = {"error": f"Line index {idx} out of range"}
                        
            elif path == "/api/exclude/save":
                exclusions = body.get("exclusions", [])
                ex_path = get_active_wts_paths()["not_support"]
                try:
                    with open(ex_path, 'w', encoding='utf-8') as f:
                        json.dump(exclusions, f, indent=4)
                    SESSION_SETTINGS["not_support_path"] = ex_path
                    save_session()
                    response_data = {"success": True}
                except Exception as e:
                    response_data = {"error": str(e)}
                    
            elif path == "/api/tms-config/save":
                parameters = body.get("parameters", [])
                tms_conf_path = get_active_wts_paths()["tms_conf"]
                try:
                    # Load current TMS config representation
                    tms_data = parse_tms_conf(tms_conf_path)

                    # Update values
                    for param in parameters:
                        idx = param.get("index")
                        val = param.get("value")
                        if idx is not None and 0 <= idx < len(tms_data):
                            tms_data[idx]['value'] = val

                    # Save back
                    with open(tms_conf_path, 'w', encoding='utf-8', newline='\n') as f:
                        for d in tms_data:
                            f.write(f"{d['key']}={d['value']}\n" if d['type'] == 'kv_pair' else d['original'])

                    response_data = {"success": True}
                except Exception as e:
                    response_data = {"error": str(e)}
                    
            elif path == "/api/tms-config/toggle-upload":
                enabled = body.get("enabled", False)
                en_str = "Enabled" if enabled else "Disabled"
                tms_conf_path = get_active_wts_paths()["tms_conf"]
                try:
                    tms_data = parse_tms_conf(tms_conf_path)

                    for i, d in enumerate(tms_data):
                        if d['key'] in ['TMS_feature', 'FTP_feature']:
                            tms_data[i]['value'] = en_str
                            
                    with open(tms_conf_path, 'w', encoding='utf-8', newline='\n') as f:
                        for d in tms_data:
                            f.write(f"{d['key']}={d['value']}\n" if d['type'] == 'kv_pair' else d['original'])
                            
                    response_data = {"success": True}
                except Exception as e:
                    response_data = {"error": str(e)}
                    
            elif path == "/api/logs/delete-file":
                folder = body.get("folder", "")
                file_name = body.get("file", "")
                if folder and file_name:
                    log_dir = get_active_wts_paths()["log_dir"]
                    p = safe_path_within(log_dir, folder, file_name)
                    if p and os.path.exists(p) and os.path.isfile(p):
                        try:
                            os.remove(p)
                            response_data = {"success": True}
                        except Exception as e:
                            response_data = {"error": str(e)}
                    else:
                        response_data = {"error": "File not found"}
                else:
                    response_data = {"error": "Missing parameters"}
                    
            elif path == "/api/logs/delete-folder":
                folders = body.get("folders", [])
                failed = []
                log_dir = get_active_wts_paths()["log_dir"]
                for folder in folders:
                    p = safe_path_within(log_dir, folder)
                    if p and os.path.exists(p) and os.path.isdir(p):
                        try:
                            shutil.rmtree(p)
                        except Exception as e:
                            failed.append(f"{folder}: {e}")
                    else:
                        failed.append(f"{folder}: invalid path")
                if failed:
                    response_data = {"error": "Failed to delete some folders", "details": failed}
                else:
                    response_data = {"success": True}
                    
            elif path == "/api/logs/zip":
                folders = body.get("folders", [])
                output_name = body.get("outputName", "logs_export.zip")
                # Reduce to a bare filename so the archive can only be written
                # inside DATA_DIR (prevents '..'/absolute-path arbitrary writes).
                output_name = os.path.basename(output_name) or "logs_export.zip"
                if not output_name.lower().endswith(".zip"):
                    output_name += ".zip"

                suggested_path = safe_path_within(DATA_DIR, output_name)
                
                if folders:
                    log_dir = get_active_wts_paths()["log_dir"]
                    try:
                        with zipfile.ZipFile(suggested_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                            for folder in folders:
                                folder_path = safe_path_within(log_dir, folder)
                                if not folder_path or not os.path.isdir(folder_path):
                                    continue
                                for root, dirs, files in os.walk(folder_path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        arcname = os.path.relpath(file_path, log_dir)
                                        zipf.write(file_path, arcname)
                        response_data = {
                            "success": True, 
                            "downloadUrl": f"/web-download/{output_name}",
                            "message": f"Saved archive to local workspace: {suggested_path}"
                        }
                    except Exception as e:
                        response_data = {"error": str(e)}
                else:
                    response_data = {"error": "No folders specified"}
                    
            elif path == "/api/logs/open-external":
                folder = body.get("folder", "")
                file_name = body.get("file", "")
                if folder and file_name:
                    log_dir = get_active_wts_paths()["log_dir"]
                    p = safe_path_within(log_dir, folder, file_name)
                    if p and os.path.exists(p):
                        env = dict(os.environ)
                        if hasattr(sys, '_MEIPASS'):
                            for key in ['LD_LIBRARY_PATH', 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH']:
                                orig_key = key + '_ORIG'
                                if orig_key in env: env[key] = env[orig_key]
                                else: env.pop(key, None)
                                
                        lower_name = file_name.lower()
                        is_pcap = any(lower_name.endswith(ext) for ext in [".pcap", ".pcapng", ".pcap.gz", ".pcapng.gz"])
                        
                        if is_pcap:
                            if os.name == 'nt':
                                ws_paths = [
                                    r"C:\Program Files\Wireshark\Wireshark.exe",
                                    r"C:\Program Files (x86)\Wireshark\Wireshark.exe"
                                ]
                                ws_exe = None
                                for wp in ws_paths:
                                    if os.path.exists(wp):
                                        ws_exe = wp
                                        break
                                if ws_exe:
                                    subprocess.Popen([ws_exe, p], env=env)
                                    response_data = {"success": True, "message": "Opened in Wireshark"}
                                else:
                                    try:
                                        os.startfile(p)
                                        response_data = {"success": True, "message": "Opened with system default"}
                                    except Exception as e:
                                        response_data = {"error": f"Wireshark not found and system failed to open: {e}"}
                            else:
                                if shutil.which("wireshark"):
                                    subprocess.Popen(["wireshark", p], env=env)
                                    response_data = {"success": True}
                                elif shutil.which("xdg-open"):
                                    subprocess.Popen(["xdg-open", p], env=env)
                                    response_data = {"success": True}
                                else:
                                    response_data = {"error": "Wireshark or xdg-open not found on this system"}
                        else:
                            # Log files
                            if os.name == 'nt':
                                try:
                                    os.startfile(p)
                                    response_data = {"success": True}
                                except Exception as e:
                                    response_data = {"error": str(e)}
                            elif LINUX_EDITOR_COMMAND:
                                subprocess.Popen(LINUX_EDITOR_COMMAND + [p], env=env)
                                response_data = {"success": True}
                            else:
                                response_data = {"error": "No text editor available. Preview log file in the browser instead."}
                    else:
                        response_data = {"error": "File does not exist"}
                else:
                    response_data = {"error": "Missing parameters"}
                    
            elif path == "/api/run":
                cfg_path = body.get("configPath", "")
                selected_tests = body.get("tests", [])

                global IS_RUNNING, CURRENT_RUN_BASELINE_FOLDERS, OUTPUT_HISTORY_BASE

                # Acquire the runner lock so the "already running?" check and the
                # IS_RUNNING flip happen atomically (prevents two concurrent
                # /api/run calls from both launching a subprocess).
                with RUNNER_LOCK:
                    if IS_RUNNING:
                        response_data = {"error": "A test execution is already running"}
                    elif not selected_tests:
                        response_data = {"error": "No test cases selected"}
                    else:
                        IS_RUNNING = True  # claim the slot before releasing the lock

                # response_data is still None only when we successfully claimed the slot.
                if response_data is None:
                    # Resolve WTS paths
                    wts_paths = resolve_wts_paths(cfg_path)
                    wts_path = wts_paths["wts_exe"]
                    wts_bin_dir = wts_paths["bin_dir"]

                    # Snapshot log folders present now so "current run only"
                    # analytics can later identify folders created by this run.
                    log_dir = wts_paths["log_dir"]
                    baseline = set()
                    if os.path.isdir(log_dir):
                        try:
                            baseline = {d for d in os.listdir(log_dir)
                                        if os.path.isdir(os.path.join(log_dir, d))}
                        except Exception:
                            baseline = set()
                    CURRENT_RUN_BASELINE_FOLDERS = baseline

                    # Reset output buffer for the new run.
                    OUTPUT_HISTORY.clear()
                    OUTPUT_HISTORY_BASE = 0

                    # Compute project role prefix
                    project_role = "EHT"
                    parent_dir_name = os.path.basename(os.path.dirname(cfg_path))
                    if "WTS-" in parent_dir_name:
                        project_role = parent_dir_name.split('-', 1)[1]

                    # Determine if we should use WSL dynamically
                    use_wsl = False
                    if os.name == 'nt':
                        if not wts_path.lower().endswith('.exe'):
                            use_wsl = True

                    # Prepare command line
                    try:
                        if len(selected_tests) == 1:
                            cmd = [wts_path, project_role, selected_tests[0]]
                        else:
                            cmd = [wts_path, "-p", project_role, "-g", "wts_group_test.txt"]
                            # Write group test cases file in wts_bin_dir
                            group_file_path = os.path.join(wts_bin_dir, "wts_group_test.txt")
                            with open(group_file_path, 'w', encoding='utf-8') as f:
                                for t in selected_tests:
                                    f.write(f"{t}\n")

                        # Start thread to execute subprocess
                        t = threading.Thread(target=run_tests_thread, args=(cmd, use_wsl, wts_bin_dir))
                        t.daemon = True
                        t.start()

                        response_data = {"success": True, "message": "Tests execution initiated"}
                    except Exception as e:
                        # Failed before the worker thread could take over; release the slot.
                        with RUNNER_LOCK:
                            IS_RUNNING = False
                        response_data = {"error": f"Failed to start test execution: {e}"}
                    
            elif path == "/api/stop":
                with RUNNER_LOCK:
                    proc = ACTIVE_SUBPROCESS if IS_RUNNING else None
                if proc:
                    try:
                        proc.terminate()
                        response_data = {"success": True, "message": "Tests execution terminated"}
                    except Exception as e:
                        response_data = {"error": f"Failed to stop tests: {str(e)}"}
                else:
                    response_data = {"error": "No active test running"}
                    
            elif path == "/api/shutdown":
                # Trigger server shutdown gracefully
                response_data = {"success": True, "message": "Server shutting down"}
                def shutdown_soon():
                    import time
                    time.sleep(0.5)
                    os._exit(0)
                threading.Thread(target=shutdown_soon).start()
                
            else:
                self.send_error(404, f"API Route Not Found: {path}")
                return
                
        except Exception as e:
            response_data = {"error": f"Internal Server Error: {str(e)}"}
            
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

# Custom server to handle random open port
def run_server(port=8000):
    global LAST_HEARTBEAT

    # Configure logging. Default level INFO hides the verbose per-request DEBUG
    # lines; set WTS_LOG_LEVEL=DEBUG to see them.
    level_name = os.environ.get("WTS_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )

    init_paths()
    
    server_address = ('127.0.0.1', port)
    
    # Simple retry mechanism if port is busy
    max_retries = 20
    httpd = None
    for p in range(port, port + max_retries):
        try:
            server_address = ('127.0.0.1', p)
            httpd = ThreadingHTTPServer(server_address, WtsHTTPRequestHandler)
            port = p
            break
        except OSError:
            continue
            
    if httpd is None:
        logger.critical("Could not find any free port to bind server.")
        sys.exit(1)
        
    print(f"WTS_SERVER_PORT={port}")
    sys.stdout.flush()
    
    # Reset heartbeat tracker and launch auto-shutdown thread
    LAST_HEARTBEAT = time.time()
    
    def monitor_heartbeat():
        # Wait 15 seconds before checking to allow browser to launch and load page
        time.sleep(15.0)
        while True:
            # If no heartbeat has been received for over 60 seconds, shut down
            # the server -- unless a test run is in progress, so closing the tab
            # (or a transient disconnect) never kills a running test.
            if time.time() - LAST_HEARTBEAT > 60.0 and not IS_RUNNING:
                logger.warning("No browser heartbeat received. Shutting down server automatically...")
                sys.stdout.flush()
                os._exit(0)
            time.sleep(5.0)
            
    t = threading.Thread(target=monitor_heartbeat)
    t.daemon = True
    t.start()
    
    # Open default browser
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/")
    except Exception as e:
        logger.warning(f"Error launching browser: {e}")
        sys.stdout.flush()
        
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    default_port = 8000
    if len(sys.argv) > 1:
        try: default_port = int(sys.argv[1])
        except Exception: pass
    run_server(default_port)
