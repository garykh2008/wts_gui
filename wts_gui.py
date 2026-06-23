import sys
import os
import re
import json
import html
import csv
import shutil
import threading
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
import ctypes

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt, Signal, QThread, QSize, QRect, QPoint
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QCheckBox, QRadioButton,
    QGroupBox, QTreeWidget, QTreeWidgetItem, QListWidget, QPlainTextEdit,
    QSplitter, QFileDialog, QMessageBox, QDateEdit, QScrollArea, QFrame,
    QMenu, QHeaderView, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QFormLayout, QDialog, QDialogButtonBox, QComboBox, QTextBrowser, QStatusBar,
    QStyledItemDelegate, QStyle, QProgressBar
)

# Optional: openpyxl for Excel export
HAS_OPENPYXL = False
try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    HAS_OPENPYXL = True
except ImportError:
    pass

# --- Window Theme Helper (Windows Only) ---

def apply_win_caption_color(widget, hex_color="#dcdfe6"):
    """Apply custom title bar color to a widget on Windows."""
    if os.name != 'nt': return
    try:
        # hex_color string to 0x00BBGGRR
        color_str = hex_color.lstrip('#')
        r, g, b = int(color_str[0:2], 16), int(color_str[2:4], 16), int(color_str[4:6], 16)
        win_color = (b << 16) | (g << 8) | r
        
        hwnd = widget.winId()
        DWMWA_CAPTION_COLOR = 35
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR, ctypes.byref(ctypes.c_int(win_color)), 4
        )
    except: pass

# --- Icon System (SVG) ---

SVG_ICONS = {
    "config": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>""",
    "execution": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>""",
    "analytics": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>""",
    "log": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>""",
    "info": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>""",
    "tms": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"></path></svg>""",
    "reload": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>""",
    "save": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1-2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>""",
    "search": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>""",
    "stop": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect></svg>""",
    "export": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>""",
    "eye": """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>"""
}

# Explicitly import QtSvg to help PyInstaller detect the dependency
HAS_SVG = False
try:
    from PySide6.QtSvg import QSvgRenderer
    HAS_SVG = True
except ImportError:
    pass

def get_svg_icon(name, color="#606266", size=QSize(20, 20)):
    """Convert SVG string to QIcon with dynamic color."""
    if not HAS_SVG or name not in SVG_ICONS: return QtGui.QIcon()
    
    svg_str = SVG_ICONS[name].replace('stroke="currentColor"', f'stroke="{color}"')
    renderer = QSvgRenderer(QtCore.QByteArray(svg_str.encode('utf-8')))
    pixmap = QtGui.QPixmap(size * 2) # Use 2x size for high-DPI rendering
    pixmap.fill(Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QtGui.QIcon(pixmap)

class StatusPillDelegate(QStyledItemDelegate):
    """Custom delegate to draw status as colored rounded pills."""
    def paint(self, painter, option, index):
        text = index.data()
        if not text or index.column() != 1:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Define colors based on status
        bg_color = QtGui.QColor("#909399") # Default Gray (NT)
        if text == "PASS":
            bg_color = QtGui.QColor("#67c23a") # Success Green
        elif text in ["FAIL", "ERROR"]:
            bg_color = QtGui.QColor("#f56c6c") # Danger Red
        elif text == "Not Support":
            bg_color = QtGui.QColor("#e6a23c") # Warning Orange

        # Calculate pill rect
        rect = option.rect.adjusted(12, 6, -12, -6)
        
        # Draw shadow-like border or fill
        painter.setBrush(bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        # Draw Text
        painter.setPen(QtGui.QColor("white"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, text)

        painter.restore()

class CommandWorker(QThread):
    output_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, command, use_wsl=False):
        super().__init__()
        self.command = command
        self.use_wsl = use_wsl
        self.process = None

    def run(self):
        cmd = self.command
        if os.name == 'nt' and self.use_wsl:
            cmd = ["wsl.exe"] + cmd
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                text=True, bufsize=1, 
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            for line in iter(self.process.stdout.readline, ''):
                if line: self.output_signal.emit(line)
            self.process.stdout.close()
            self.process.wait()
        except Exception as e:
            self.output_signal.emit(f"Error: {e}\n")
        finally:
            self.finished_signal.emit()

    def stop(self):
        if self.process: self.process.terminate()

# --- Modularized Tab Components ---

class ConfigTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        path_card, p_lay = self.main_win._create_card_layout("Configuration Target")
        h_lay = QHBoxLayout()
        self.main_win.config_path_edit = QLineEdit(); self.main_win.config_path_edit.setPlaceholderText("No file selected...")
        btn_browse = QPushButton("Select File"); btn_browse.setObjectName("ghost-btn")
        btn_browse.clicked.connect(self.main_win._browse_config_file)
        
        self.main_win.btn_reload_config = QPushButton("Reload"); self.main_win.btn_reload_config.setEnabled(False)
        self.main_win.btn_reload_config.setObjectName("ghost-btn")
        self.main_win.btn_reload_config.setIcon(get_svg_icon("reload", "#409eff"))
        self.main_win.btn_reload_config.clicked.connect(self.main_win._load_config_data)
        
        btn_view_raw = QPushButton("View Raw"); btn_view_raw.setObjectName("ghost-btn")
        btn_view_raw.setIcon(get_svg_icon("eye", "#606266"))
        btn_view_raw.clicked.connect(self.main_win._show_raw_config_viewer)
        
        h_lay.addWidget(self.main_win.config_path_edit); h_lay.addWidget(btn_browse); h_lay.addWidget(self.main_win.btn_reload_config); h_lay.addWidget(btn_view_raw)
        p_lay.addLayout(h_lay)
        layout.addWidget(path_card)

        toggle_card, t_lay = self.main_win._create_card_layout("Device Toggles")
        self.main_win.ap_toggles_layout = QHBoxLayout(); self.main_win.sta_toggles_layout = QHBoxLayout()
        t_lay.addLayout(self.main_win.ap_toggles_layout); t_lay.addLayout(self.main_win.sta_toggles_layout)
        layout.addWidget(toggle_card)

        content_card, c_lay = self.main_win._create_card_layout("Editable Parameters")
        self.main_win.config_tree = QTreeWidget(); self.main_win.config_tree.setHeaderLabels(["Parameter Key", "Current Value"])
        self.main_win.config_tree.setColumnWidth(0, 400); self.main_win.config_tree.setAlternatingRowColors(True)
        self.main_win.config_tree.itemDoubleClicked.connect(self.main_win._on_config_tree_double_click)
        c_lay.addWidget(self.main_win.config_tree)
        layout.addWidget(content_card)

        self.main_win.btn_save_config = QPushButton("Commit Changes to File")
        self.main_win.btn_save_config.setIcon(get_svg_icon("save", "white"))
        self.main_win.btn_save_config.setMinimumHeight(45); self.main_win.btn_save_config.setFixedWidth(300)
        self.main_win.btn_save_config.clicked.connect(self.main_win._save_config_file)
        layout.addWidget(self.main_win.btn_save_config, 0, Qt.AlignCenter)

class ExecutionTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Dashboard Area
        dash_container = QWidget()
        dash_layout = QVBoxLayout(dash_container); dash_layout.setContentsMargins(0, 0, 0, 5); dash_layout.setSpacing(8)
        
        stat_row = QHBoxLayout(); stat_row.setContentsMargins(0, 0, 0, 0); stat_row.setSpacing(15)
        self.main_win.card_total, self.main_win.lbl_total = self.main_win._create_stat_card("Selected", "#409eff")
        self.main_win.card_pass, self.main_win.lbl_pass = self.main_win._create_stat_card("Passed", "#67c23a")
        self.main_win.card_fail, self.main_win.lbl_fail = self.main_win._create_stat_card("Failed", "#f56c6c")
        stat_row.addWidget(self.main_win.card_total); stat_row.addWidget(self.main_win.card_pass); stat_row.addWidget(self.main_win.card_fail)
        stat_row.addStretch()
        dash_layout.addLayout(stat_row)

        self.main_win.progress_bar = QProgressBar(); self.main_win.progress_bar.setValue(0); self.main_win.progress_bar.setVisible(False)
        dash_layout.addWidget(self.main_win.progress_bar)
        layout.addWidget(dash_container)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget(); left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        filter_card, f_lay = self.main_win._create_card_layout("Quick Filters")
        role_row = QHBoxLayout(); role_row.addWidget(QLabel("Role: "))
        self.main_win.exec_role_all = QRadioButton("All"); self.main_win.exec_role_ap = QRadioButton("AP"); self.main_win.exec_role_sta = QRadioButton("STA")
        self.main_win.exec_role_all.setChecked(True); role_row.addWidget(self.main_win.exec_role_all); role_row.addWidget(self.main_win.exec_role_ap); role_row.addWidget(self.main_win.exec_role_sta); role_row.addStretch()
        
        self.main_win.exec_role_all.toggled.connect(self.main_win._update_test_execution_display)
        self.main_win.exec_role_ap.toggled.connect(self.main_win._update_test_execution_display)
        self.main_win.exec_role_sta.toggled.connect(self.main_win._update_test_execution_display)
        
        f_lay.addLayout(role_row)
        
        search_row = QHBoxLayout(); search_row.addWidget(QLabel("Search: "))
        self.main_win.exec_search_edit = QLineEdit(); self.main_win.exec_search_edit.setPlaceholderText("Filter by name...")
        self.main_win.exec_search_edit.textChanged.connect(self.main_win._update_test_execution_display); search_row.addWidget(self.main_win.exec_search_edit)
        f_lay.addLayout(search_row)
        
        btn_row = QHBoxLayout()
        btn_adv = QPushButton("Advanced Filtering"); btn_adv.setObjectName("ghost-btn")
        btn_adv.clicked.connect(self.main_win._show_advanced_options_popup)
        btn_ns = QPushButton("Exclude List"); btn_ns.setObjectName("ghost-btn")
        btn_ns.clicked.connect(self.main_win._show_not_support_config_window)
        btn_row.addWidget(btn_adv); btn_row.addWidget(btn_ns)
        f_lay.addLayout(btn_row)
        left_layout.addWidget(filter_card)

        self.main_win.sel_card, s_lay = self.main_win._create_card_layout("Test Suite Selection")
        ctrl_row = QHBoxLayout(); b_all = QPushButton("Select All"); b_none = QPushButton("Clear")
        b_all.setObjectName("ghost-btn"); b_none.setObjectName("ghost-btn")
        b_all.clicked.connect(self.main_win._select_all_tests); b_none.clicked.connect(self.main_win._deselect_all_tests)
        ctrl_row.addWidget(b_all); ctrl_row.addWidget(b_none); s_lay.addLayout(ctrl_row)
        
        self.main_win.scroll_area = QScrollArea(); self.main_win.scroll_area.setWidgetResizable(True)
        self.main_win.scroll_content = QWidget(); self.main_win.scroll_content.setObjectName("list-container")
        self.main_win.test_check_layout = QVBoxLayout(self.main_win.scroll_content); self.main_win.test_check_layout.setSpacing(5)
        self.main_win.scroll_area.setWidget(self.main_win.scroll_content); s_lay.addWidget(self.main_win.scroll_area)
        left_layout.addWidget(self.main_win.sel_card)
        
        run_row = QHBoxLayout()
        self.main_win.btn_run = QPushButton("START TESTING"); self.main_win.btn_run.setObjectName("action-btn"); self.main_win.btn_run.setMinimumHeight(45)
        self.main_win.btn_run.setIcon(get_svg_icon("execution", "white"))
        self.main_win.btn_run.clicked.connect(self.main_win._run_tests)
        self.main_win.btn_stop = QPushButton("ABORT"); self.main_win.btn_stop.setObjectName("danger-btn"); self.main_win.btn_stop.setMinimumHeight(45)
        self.main_win.btn_stop.setIcon(get_svg_icon("stop", "white"))
        self.main_win.btn_stop.clicked.connect(self.main_win._stop_tests)
        run_row.addWidget(self.main_win.btn_run); run_row.addWidget(self.main_win.btn_stop)
        left_layout.addLayout(run_row)

        right_widget = QWidget(); right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        term_card, t_lay = self.main_win._create_card_layout("Command Terminal")
        self.main_win.terminal = QPlainTextEdit(); self.main_win.terminal.setReadOnly(True)
        self.main_win.terminal.setObjectName("terminal-view")
        t_lay.addWidget(self.main_win.terminal)
        right_layout.addWidget(term_card)

        layout.addWidget(splitter)
        layout.setStretchFactor(dash_container, 0)
        layout.setStretchFactor(splitter, 1)
        splitter.addWidget(left_widget); splitter.addWidget(right_widget); splitter.setStretchFactor(1, 2)

class AnalyticsTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        opt_card, o_lay = self.main_win._create_card_layout("Scan & Filter Parameters")
        h = QHBoxLayout(); h.addWidget(QLabel("Role: ")); self.main_win.res_role_all = QRadioButton("All"); self.main_win.res_role_ap = QRadioButton("AP"); self.main_win.res_role_sta = QRadioButton("STA")
        self.main_win.res_role_all.setChecked(True); h.addWidget(self.main_win.res_role_all); h.addWidget(self.main_win.res_role_ap); h.addWidget(self.main_win.res_role_sta); h.addSpacing(30)
        h.addWidget(QLabel("Logs since: ")); self.main_win.res_date_edit = QDateEdit(); self.main_win.res_date_edit.setCalendarPopup(True); self.main_win.res_date_edit.setDate(QtCore.QDate.currentDate())
        h.addWidget(self.main_win.res_date_edit); btn_scan = QPushButton("Scan Results"); btn_scan.clicked.connect(self.main_win._analyze_results)
        btn_scan.setIcon(get_svg_icon("search", "white"))
        btn_exp = QPushButton("Export"); btn_exp.setObjectName("ghost-btn"); btn_exp.clicked.connect(self.main_win._export_results)
        btn_exp.setIcon(get_svg_icon("export", "#606266"))
        h.addWidget(btn_scan); h.addWidget(btn_exp); o_lay.addLayout(h)
        
        h2 = QHBoxLayout(); self.main_win.chk_hide_nt = QCheckBox("Hide NT"); self.main_win.chk_hide_ns = QCheckBox("Hide Excluded")
        self.main_win.chk_hide_nt.toggled.connect(self.main_win._on_result_view_toggle); self.main_win.chk_hide_ns.toggled.connect(self.main_win._on_result_view_toggle)
        h2.addWidget(self.main_win.chk_hide_nt); h2.addWidget(self.main_win.chk_hide_ns); h2.addStretch(); o_lay.addLayout(h2)
        layout.addWidget(opt_card)
        
        res_card, r_lay = self.main_win._create_card_layout("Testing Summary")
        self.main_win.result_table = QTableWidget(0, 3); self.main_win.result_table.setHorizontalHeaderLabels(["Test Case Name", "Final Status", "Log Directory"])
        self.main_win.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.main_win.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.main_win.result_table.setItemDelegateForColumn(1, StatusPillDelegate(self.main_win))
        self.main_win.result_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.main_win.result_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.main_win.result_table.setContextMenuPolicy(Qt.CustomContextMenu); self.main_win.result_table.customContextMenuRequested.connect(self.main_win._show_result_context_menu)
        r_lay.addWidget(self.main_win.result_table)
        layout.addWidget(res_card)

class LogBrowserTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        f_card, fl = self.main_win._create_card_layout("Folder Filter")
        self.main_win.log_date_edit = QDateEdit(); self.main_win.log_date_edit.setCalendarPopup(True); self.main_win.log_date_edit.setDate(QtCore.QDate.currentDate().addMonths(-1))
        btn_ref = QPushButton("Refresh List"); btn_ref.clicked.connect(self.main_win._load_log_folders)
        btn_ref.setIcon(get_svg_icon("reload", "white"))
        fl.addWidget(QLabel("Show folders after:")); fl.addWidget(self.main_win.log_date_edit); fl.addWidget(btn_ref); ll.addWidget(f_card)
        list_card, lsl = self.main_win._create_card_layout("Folders"); self.main_win.log_folder_list = QListWidget(); self.main_win.log_folder_list.itemSelectionChanged.connect(self.main_win._on_log_folder_select)
        self.main_win.log_folder_list.setContextMenuPolicy(Qt.CustomContextMenu); self.main_win.log_folder_list.customContextMenuRequested.connect(self.main_win._on_log_folder_right_click)
        lsl.addWidget(self.main_win.log_folder_list); ll.addWidget(list_card)
        
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        file_card, fcl = self.main_win._create_card_layout("Log Files")
        self.main_win.log_file_table = QTableWidget(0, 2); self.main_win.log_file_table.setHorizontalHeaderLabels(["Filename", "Size"])
        self.main_win.log_file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch); self.main_win.log_file_table.itemDoubleClicked.connect(self.main_win._open_log_file)
        fcl.addWidget(self.main_win.log_file_table); rl.addWidget(file_card)
        
        splitter.addWidget(left); splitter.addWidget(right); splitter.setStretchFactor(1, 2); layout.addWidget(splitter)

class MasterInfoTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Horizontal)
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        f_card, fl = self.main_win._create_card_layout("Quick Find")
        self.main_win.xml_role_all = QRadioButton("All"); self.main_win.xml_role_ap = QRadioButton("AP"); self.main_win.xml_role_sta = QRadioButton("STA"); self.main_win.xml_role_all.setChecked(True)
        hr = QHBoxLayout(); hr.addWidget(self.main_win.xml_role_all); hr.addWidget(self.main_win.xml_role_ap); hr.addWidget(self.main_win.xml_role_sta); fl.addLayout(hr)
        
        self.main_win.xml_role_all.toggled.connect(self.main_win._update_viewer_display)
        self.main_win.xml_role_ap.toggled.connect(self.main_win._update_viewer_display)
        self.main_win.xml_role_sta.toggled.connect(self.main_win._update_viewer_display)
        
        self.main_win.xml_search_edit = QLineEdit(); self.main_win.xml_search_edit.setPlaceholderText("Search parameters..."); fl.addWidget(self.main_win.xml_search_edit)
        self.main_win.xml_search_edit.textChanged.connect(self.main_win._update_viewer_display)
        
        ll.addWidget(f_card); list_card, lsl = self.main_win._create_card_layout("Test Definitions")
        self.main_win.xml_list = QListWidget(); self.main_win.xml_list.itemSelectionChanged.connect(self.main_win._on_test_case_select); lsl.addWidget(self.main_win.xml_list); ll.addWidget(list_card)
        
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        det_card, dcl = self.main_win._create_card_layout("Parameter Details")
        self.main_win.xml_detail_tree = QTreeWidget(); self.main_win.xml_detail_tree.setHeaderLabels(["Key", "Value"]); self.main_win.xml_detail_tree.setColumnWidth(0, 300)
        dcl.addWidget(self.main_win.xml_detail_tree); rl.addWidget(det_card); splitter.addWidget(left); splitter.addWidget(right); splitter.setStretchFactor(1, 2); layout.addWidget(splitter)

class TmsConfigTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        action_row = QHBoxLayout()
        btn_rel = QPushButton("Reload TmsClient.conf"); btn_sav = QPushButton("Save Config"); btn_sav.setObjectName("action-btn")
        btn_rel.setIcon(get_svg_icon("reload", "white"))
        btn_sav.setIcon(get_svg_icon("save", "white"))
        self.main_win.chk_tms_upload = QCheckBox("Sync with TMS Portal"); action_row.addWidget(btn_rel); action_row.addWidget(btn_sav); action_row.addSpacing(20); action_row.addWidget(self.main_win.chk_tms_upload); action_row.addStretch(); layout.addLayout(action_row)
        btn_rel.clicked.connect(self.main_win._load_tms_data); btn_sav.clicked.connect(self.main_win._save_tms_file); self.main_win.chk_tms_upload.clicked.connect(self.main_win._on_tms_upload_toggle)
        t_card, tl = self.main_win._create_card_layout("Raw Configuration Mapping")
        self.main_win.tms_tree = QTreeWidget(); self.main_win.tms_tree.setHeaderLabels(["Config Key", "Value"]); self.main_win.tms_tree.setColumnWidth(0, 350)
        self.main_win.tms_tree.itemDoubleClicked.connect(self.main_win._on_tms_tree_double_click); tl.addWidget(self.main_win.tms_tree); layout.addWidget(t_card)

# --- Main Application Window ---

class WtsGuiApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.APP_VERSION = "3.4"
        self.app_initialized = False
        self.setWindowTitle(f"WTS GUI Dashboard v{self.APP_VERSION}")
        self.resize(1200, 900)

        # Data Models
        self.settings_file = "wts_gui.settings.json"
        self.session_settings = {}
        self.xml_test_cases = {}
        self.xml_test_case_names = []
        self.all_testbeds = []
        self.ignore_testbeds_vars = {}
        self.include_testbeds_vars = {}
        self.filter_not_pass_only = False
        self.not_support_list = set()
        self.tms_data = []
        self.config_data = []
        self.device_lines = {}
        self.test_history_map = {}
        self.current_worker = None
        self.linux_editor_command = None

        # Execution Stats
        self.total_selected = 0
        self.pass_count = 0
        self.fail_count = 0

        # Path Setup
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.bin_dir = os.path.dirname(sys.executable)
        else:
            self.bin_dir = os.path.dirname(os.path.abspath(__file__))

        self.use_wsl = False
        self.wts_executable_path = os.path.join(self.bin_dir, 'wts')
        if os.name == 'nt':
            wts_exe_path = os.path.join(self.bin_dir, 'wts.exe')
            if os.path.exists(wts_exe_path): self.wts_executable_path = wts_exe_path
            else: self.use_wsl = True

        self.log_dir_path = os.path.join(self.bin_dir, 'log')
        self.tms_client_conf_path = os.path.join(os.path.dirname(self.bin_dir), 'config', 'TmsClient.conf')
        self.not_support_default_path = os.path.join(self.bin_dir, "wts_not_support.json")

        self._setup_style()
        self._init_ui()
        
        if not self._check_environment():
            QMessageBox.critical(self, "Environment Error", "This program must be run from the 'bin' directory of the WTS tool.")
            sys.exit(1)

        self._load_last_session()
        self._load_tms_data()
        self._find_and_cache_text_editor()
        self._load_log_folders()
        self.app_initialized = True
        QtCore.QTimer.singleShot(500, self._check_not_support_file)

    def _setup_style(self):
        """Standardized and unified modern style with optimized typography and robust interactivity."""
        # Use a modern font stack
        self.font_family = "'Segoe UI Variable Text', 'Inter', 'Segoe UI', 'Microsoft YaHei UI', sans-serif"
        self.mono_font_family = "'Cascadia Code', 'Consolas', 'Monaco', monospace"

        self.setStyleSheet(f"""
            QMainWindow {{ 
                background-color: #ebedf0; 
                font-family: {self.font_family};
            }}
            
            /* Dialog Styling - Mid-Gray Background with No Border */
            QDialog {{ 
                background-color: #dcdfe6; 
                border: none;
                font-family: {self.font_family};
            }}
            
            /* High Contrast GroupBox inside Dialogs (White on Mid-Gray) */
            QDialog QGroupBox {{
                background-color: #ffffff;
                border: 1px solid #c0c4cc;
                border-radius: 8px;
                margin-top: 25px;
            }}
            QDialog QLabel {{ color: #303133; }}

            /* TabWidget Styling */
            QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
            QTabBar::tab {{ 
                background: #dcdfe6; border: none; padding: 10px 25px; 
                border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 2px;
                color: #606266; font-weight: 500; font-size: 13px;
            }}
            QTabBar::tab:selected {{ background: white; color: #409eff; border-bottom: 2px solid #409eff; font-weight: 600; }}
            QTabBar::tab:hover:!selected {{ background: #e4e7ed; }}

            /* Unified GroupBox (Card) */
            QGroupBox {{ 
                font-weight: 600; font-size: 13px; color: #303133;
                border: 1px solid #dcdfe6; border-radius: 8px; background-color: white;
                margin-top: 20px; padding-top: 20px;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 15px; padding: 0 8px; top: 0px; }}

            /* Inputs */
            QLineEdit, QDateEdit, QComboBox {{ 
                border: 1px solid #dcdfe6; border-radius: 4px; padding: 7px; background: white; color: #303133;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: #409eff; }}
            
            /* Buttons */
            QPushButton {{ 
                background-color: #409eff; color: white; border-radius: 4px; padding: 8px 16px; 
                font-weight: 600; border: none; font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #66b1ff; }}
            QPushButton:pressed {{ background-color: #3a8ee6; }}
            QPushButton:disabled {{ background-color: #c0c4cc; }}
            
            QPushButton#action-btn {{ background-color: #67c23a; }}
            QPushButton#action-btn:hover {{ background-color: #85ce61; }}
            
            QPushButton#danger-btn {{ background-color: #f56c6c; }}
            QPushButton#danger-btn:hover {{ background-color: #f78989; }}
            
            QPushButton#ghost-btn {{ background-color: white; color: #606266; border: 1px solid #dcdfe6; }}
            QPushButton#ghost-btn:hover {{ color: #409eff; border-color: #c6e2ff; background-color: #ecf5ff; }}

            /* Data Views (Tree/List/Table) */
            QTreeWidget, QListWidget, QTableWidget {{ 
                border: 1px solid #ebeef5; border-radius: 4px; background: white; outline: none; gridline-color: #f0f2f5;
                font-size: 13px;
            }}
            QHeaderView::section {{ 
                background-color: #f5f7fa; padding: 8px; border: none; 
                border-bottom: 1px solid #ebeef5; font-weight: 600; color: #909399; 
                font-size: 12px;
            }}
            
            /* States: Selected, Hover, and Selected+Hover */
            QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{ 
                background-color: #ecf5ff; 
                color: #409eff; 
            }}
            QTableWidget::item:hover, QTreeWidget::item:hover, QListWidget::item:hover {{ 
                background-color: #f5f7fa; 
                color: #303133; 
            }}
            QTableWidget::item:selected:hover, QTreeWidget::item:selected:hover, QListWidget::item:selected:hover {{ 
                background-color: #d9ecff; 
                color: #409eff; 
            }}

            /* List Containers */
            QScrollArea {{ border: none; background-color: white; }}
            QWidget#list-container {{ background-color: white; }}

            /* Terminal View */
            QPlainTextEdit#terminal-view {{
                background-color: #1e1e1e; color: #f0f0f0; border-radius: 4px; 
                font-family: {self.mono_font_family}; 
                font-size: 13px; padding: 12px; line-height: 150%;
            }}

            /* ScrollBar */
            QScrollBar:vertical {{ border: none; background: #f5f7fa; width: 10px; margin: 0px; }}
            QScrollBar::handle:vertical {{ background: #dcdfe6; border-radius: 5px; min-height: 30px; margin: 2px; }}
            QScrollBar::handle:vertical:hover {{ background: #c0c4cc; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

            /* Dashboard Cards */
            QFrame#stat-card {{
                background-color: white; border: 1px solid #dcdfe6; border-radius: 8px; 
            }}
            QLabel#stat-value {{ font-size: 22px; font-weight: 700; }}
            QLabel#stat-label {{ font-size: 10px; color: #909399; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; }}

            /* Progress Bar */
            QProgressBar {{
                border: none; background-color: #ebeef5; height: 6px; border-radius: 3px; text-align: center;
                font-size: 10px; font-weight: 600;
            }}
            QProgressBar::chunk {{ background-color: #409eff; border-radius: 3px; }}

            QCheckBox, QRadioButton, QLabel {{ color: #606266; font-size: 13px; }}
            QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
        """)

    def _init_ui(self):
        container = QWidget()
        self.setCentralWidget(container)
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setIconSize(QSize(18, 18))
        main_layout.addWidget(self.tabs)

        # Initialize Modularized Tabs with Icons
        self.config_tab = ConfigTab(self); self.tabs.addTab(self.config_tab, get_svg_icon("config", "#409eff"), "Config Editor")
        self.execution_tab = ExecutionTab(self); self.tabs.addTab(self.execution_tab, get_svg_icon("execution", "#409eff"), "Execution")
        self.result_tab = AnalyticsTab(self); self.tabs.addTab(self.result_tab, get_svg_icon("analytics", "#409eff"), "Analytics")
        self.log_tab = LogBrowserTab(self); self.tabs.addTab(self.log_tab, get_svg_icon("log", "#409eff"), "Log Browser")
        self.xml_tab = MasterInfoTab(self); self.tabs.addTab(self.xml_tab, get_svg_icon("info", "#409eff"), "MasterInfo")
        self.tms_tab = TmsConfigTab(self); self.tabs.addTab(self.tms_tab, get_svg_icon("tms", "#409eff"), "TMS Config")

        self.statusBar().setStyleSheet(f"background: white; border-top: 1px solid #dcdfe6; padding: 5px; color: #909399; font-size: 12px; font-family: {self.font_family};")
        self.statusBar().showMessage("WTS Ready")

    # --- UI Component Helpers ---

    def _create_card_layout(self, title):
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(20, 25, 20, 20)
        layout.setSpacing(12)
        return group, layout

    def _create_stat_card(self, label, color="#409eff"):
        card = QFrame(); card.setObjectName("stat-card")
        card.setFixedSize(120, 60)
        l = QVBoxLayout(card); l.setContentsMargins(5, 5, 5, 5); l.setSpacing(2)
        val = QLabel("0"); val.setObjectName("stat-value"); val.setStyleSheet(f"color: {color};")
        lbl = QLabel(label); lbl.setObjectName("stat-label")
        l.addWidget(val, 0, Qt.AlignCenter); l.addWidget(lbl, 0, Qt.AlignCenter)
        return card, val

    # --- Shared Business Logic ---

    def _check_environment(self):
        try: return os.path.basename(self.bin_dir) == 'bin' and os.path.exists(self.wts_executable_path)
        except: return False

    def _load_last_session(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f: self.session_settings = json.load(f)
            except: pass
        cp = self.session_settings.get('config_path')
        if cp and os.path.exists(cp): self.config_path_edit.setText(cp); self._load_config_data()
        self.log_date_edit.setDate(QtCore.QDate.fromString(self.session_settings.get('log_filter_date', ""), "yyyy-MM-dd") or QtCore.QDate.currentDate().addMonths(-1))
        self.res_date_edit.setDate(QtCore.QDate.fromString(self.session_settings.get('result_filter_date', ""), "yyyy-MM-dd") or QtCore.QDate.currentDate())
        self.filter_not_pass_only = self.session_settings.get('filter_not_pass_only', False)
        for tb in self.session_settings.get('ignored_testbeds', []): self.ignore_testbeds_vars[tb] = True
        for tb in self.session_settings.get('included_testbeds', []): self.include_testbeds_vars[tb] = True

    def _save_session(self):
        if not self.app_initialized: return
        self.session_settings.update({'log_filter_date': self.log_date_edit.date().toString("yyyy-MM-dd"), 'result_filter_date': self.res_date_edit.date().toString("yyyy-MM-dd"),
            'test_execution_role': "AP" if self.exec_role_ap.isChecked() else ("STA" if self.exec_role_sta.isChecked() else "All"), 'filter_not_pass_only': self.filter_not_pass_only,
            'ignored_testbeds': [tb for tb, v in self.ignore_testbeds_vars.items() if v], 'included_testbeds': [tb for tb, v in self.include_testbeds_vars.items() if v]})
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f: json.dump(self.session_settings, f, indent=4)
        except: pass

    def _browse_config_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select AllInitConfig", "", "Text files (*.txt);;All files (*.*)")
        if p: self.config_path_edit.setText(p); self._load_config_data()

    def _load_config_data(self):
        p = self.config_path_edit.text()
        if not os.path.exists(p): return
        self.config_data = []; self.device_lines = {}
        with open(p, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                s = line.strip()
                if s.startswith("#$") or s.startswith("$"):
                    self.config_data.append({'original': line, 'modified': line, 'type': 'other', 'device': None, 'key': "", 'value': ""})
                    continue

                tk = s.lstrip('#').strip()
                it, dev = 'other', None
                
                if tk.startswith("wfa_control_agent_"):
                    parts = tk.split('!')
                    if len(parts) > 1:
                        cand = parts[0].split('wfa_control_agent_')[1]
                        if (cand.endswith('_ap') or cand.endswith('_sta')) and not cand.startswith('capture_') and not cand.startswith('sniff_'):
                            dev = cand; self.device_lines.setdefault(dev, []).append(i)
                
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
                
                self.config_data.append({'original': line, 'modified': line, 'type': it, 'device': dev, 'key': k, 'value': v})
        
        self._refresh_config_tree()
        self._create_device_toggles(); self.btn_reload_config.setEnabled(True); self.session_settings['config_path'] = p; self._save_session()
        xp = os.path.join(os.path.dirname(p), 'MasterTestInfo.xml'); self._load_xml_data(xp) if os.path.exists(xp) else None

    def _create_device_toggles(self):
        for l in [self.ap_toggles_layout, self.sta_toggles_layout]:
            while l.count():
                w = l.takeAt(0).widget()
                if w: w.deleteLater()
        self.ap_toggles_layout.addWidget(QLabel("<b>APs:</b>")); self.sta_toggles_layout.addWidget(QLabel("<b>STAs:</b>"))
        for dev in sorted(self.device_lines.keys()):
            is_en = True
            for idx in self.device_lines[dev]:
                if self.config_data[idx]['modified'].strip().startswith('#'):
                    is_en = False
                    break
            c = QCheckBox(dev); c.setChecked(is_en); c.clicked.connect(lambda v, d=dev: self._toggle_device(d, v))
            (self.ap_toggles_layout if "_ap" in dev else self.sta_toggles_layout).addWidget(c)
        self.ap_toggles_layout.addStretch(); self.sta_toggles_layout.addStretch()

    def _toggle_device(self, dev, en):
        for idx in self.device_lines[dev]:
            curr = self.config_data[idx]['modified']
            if en: self.config_data[idx]['modified'] = curr.lstrip()[1:].lstrip() if curr.lstrip().startswith('#') else curr
            else: self.config_data[idx]['modified'] = "# " + curr if not curr.lstrip().startswith('#') else curr
        self._refresh_config_tree(); self._update_test_execution_display()

    def _refresh_config_tree(self):
        self.config_tree.clear()
        for idx, d in enumerate(self.config_data):
            if d['type'] == 'other': continue 
            
            mod = d['modified'].strip()
            is_commented = mod.startswith('#')
            
            display_k, display_v = d['key'], d['value']
            if is_commented:
                display_k = f"[OFF] {display_k}"

            item = QTreeWidgetItem([display_k, display_v])
            item.setData(0, Qt.UserRole, idx) 
            
            if is_commented:
                item.setForeground(0, QtGui.QColor("#909399"))
            else:
                item.setBackground(1, QtGui.QColor("#fdf6ec"))
                item.setForeground(0, QtGui.QColor("#303133"))
                
            self.config_tree.addTopLevelItem(item)

    def _save_config_file(self):
        p = self.config_path_edit.text()
        if p:
            try:
                with open(p, 'w', encoding='utf-8', newline='\n') as f:
                    for d in self.config_data: f.write(d['modified'])
                QMessageBox.information(self, "Success", "Config saved successfully."); self._load_config_data()
            except Exception as e: QMessageBox.critical(self, "Error", str(e))

    def _on_config_tree_double_click(self, it, col):
        if col != 1: return
        idx = it.data(0, Qt.UserRole); data = self.config_data[idx]
        if data['type'] == 'ip_port_pair': self._edit_ip_port(it, idx)
        elif data['type'] in ['kv_pair', 'define_kv_pair']:
            v, ok = QtWidgets.QInputDialog.getText(self, "Edit Value", f"Field: {it.text(0)}", QLineEdit.Normal, it.text(1))
            if ok:
                it.setText(1, v); k = it.text(0).replace("[OFF] ", "")
                self.config_data[idx]['value'] = v
                new_line = f"define!{k}!{v}!\n" if data['type'] == 'define_kv_pair' else f"{k}!{v}!\n"
                if it.text(0).startswith("[OFF]"):
                    self.config_data[idx]['modified'] = "# " + new_line
                else:
                    self.config_data[idx]['modified'] = new_line

    def _edit_ip_port(self, it, idx):
        vs = it.text(1); ip = re.search(r"ipaddr=([^,]+)", vs).group(1) if "ipaddr=" in vs else ""; pt = re.search(r"port=(\d+)", vs).group(1) if "port=" in vs else ""
        d = QDialog(self); d.setWindowTitle("Edit Connection"); l = QFormLayout(d); i_in = QLineEdit(ip); p_in = QLineEdit(pt)
        l.addRow("Agent IP:", i_in); l.addRow("Control Port:", p_in); bt = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bt.accepted.connect(d.accept); bt.rejected.connect(d.reject); l.addWidget(bt)
        if d.exec() == QDialog.Accepted:
            nv = f"ipaddr={i_in.text()},port={p_in.text()}"; it.setText(1, nv); 
            self.config_data[idx]['value'] = nv
            k = it.text(0).replace("[OFF] ", "")
            new_line = f"{k}!{nv}!\n"
            if it.text(0).startswith("[OFF]"):
                self.config_data[idx]['modified'] = "# " + new_line
            else:
                self.config_data[idx]['modified'] = new_line

    def _show_raw_config_viewer(self):
        if not self.config_data: return
        d = QDialog(self); d.setWindowTitle("Raw Configuration Viewer"); d.resize(800, 700); l = QVBoxLayout(d)
        apply_win_caption_color(d, "#dcdfe6")
        txt = QPlainTextEdit(); txt.setReadOnly(True)
        txt.setStyleSheet(f"font-family: {self.mono_font_family}; font-size: 13px; background-color: #f8f9fa; border: 1px solid #dcdfe6;")
        full_content = "".join([d['modified'] for d in self.config_data])
        txt.setPlainText(full_content)
        l.addWidget(txt); bb = QDialogButtonBox(QDialogButtonBox.Close); bb.rejected.connect(d.reject); l.addWidget(bb); d.exec()

    def _load_xml_data(self, p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                root = ET.parse(f).getroot(); self.xml_test_cases = {el.tag: el for el in root if el.tag}
                ut = set()
                for el in self.xml_test_cases.values():
                    tb = el.find('TB_LIST')
                    if tb is not None and tb.text: ut.update([t.strip() for t in tb.text.split(',') if t.strip()])
                self.all_testbeds = sorted(list(ut)); self.xml_test_case_names = sorted(self.xml_test_cases.keys())
                self._update_viewer_display(); self._update_test_execution_display()
        except: pass

    def _update_viewer_display(self):
        role = "AP" if self.xml_role_ap.isChecked() else ("STA" if self.xml_role_sta.isChecked() else "All")
        search = self.xml_search_edit.text().lower(); self.xml_list.clear()
        for n in self.xml_test_case_names:
            if role == "AP" and not n.split('-', 1)[-1].startswith('4.'): continue
            if role == "STA" and not n.split('-', 1)[-1].startswith('5.'): continue
            if search and search not in n.lower(): continue
            self.xml_list.addItem(n)

    def _on_test_case_select(self):
        self.xml_detail_tree.clear(); sel = self.xml_list.selectedItems()
        if not sel: return
        el = self.xml_test_cases.get(sel[0].text())
        if el is not None:
            def recurse(pel, pre=""):
                for c in pel:
                    if len(list(c)) > 0: recurse(c, f"{pre}{c.tag}.")
                    elif c.text and c.text.strip(): QTreeWidgetItem(self.xml_detail_tree, [f"{pre}{c.tag}", c.text.strip()])
            recurse(el); self.xml_detail_tree.expandAll()

    def _update_test_execution_display(self):
        role = "AP" if self.exec_role_ap.isChecked() else ("STA" if self.exec_role_sta.isChecked() else "All")
        search = self.exec_search_edit.text().lower()
        ui = [tb for tb, v in self.ignore_testbeds_vars.items() if v]; ad = [tb for tb in self.all_testbeds if not self._is_testbed_enabled(tb)]
        ei = list(set(ui + ad)); uinc = [tb for tb, v in self.include_testbeds_vars.items() if v]
        self._save_session()
        while self.test_check_layout.count():
            it = self.test_check_layout.takeAt(0).widget()
            if it: it.deleteLater()
        self.test_checkboxes = {}; count = 0
        for n in self.xml_test_case_names:
            if role != "All" and ((role=="AP" and not n.split('-', 1)[-1].startswith('4.')) or (role=="STA" and not n.split('-', 1)[-1].startswith('5.'))): continue
            if search and search not in n.lower() or n in self.not_support_list: continue
            el = self.xml_test_cases.get(n); tbs = []
            if el is not None:
                te = el.find('TB_LIST')
                if te is not None and te.text: tbs = [t.strip() for t in te.text.split(',')]
            if uinc and not any(tb in uinc for tb in tbs) or any(tb in ei for tb in tbs): continue
            if self.filter_not_pass_only:
                hist = self.test_history_map.get(n, [])
                if hist and hist[-1]['result'] == "PASS": continue
            c = QCheckBox(n); self.test_check_layout.addWidget(c); self.test_checkboxes[n] = c; count += 1
        self.sel_card.setTitle(f"Test Suite Selection ({count} Visible)")

    def _is_testbed_enabled(self, tb):
        for s in ["_ap", "_sta"]:
            dev = f"{tb}{s}"
            if dev in self.device_lines:
                for idx in self.device_lines[dev]:
                    if self.config_data[idx]['modified'].strip().startswith('#'): 
                        return False
        return True

    def _show_advanced_options_popup(self):
        d = QDialog(self); d.setWindowTitle("Execution Overrides"); d.resize(650, 550); l = QVBoxLayout(d)
        apply_win_caption_color(d, "#dcdfe6")
        cn = QCheckBox("Show FAIL/NT Cases Only"); cn.setChecked(self.filter_not_pass_only)
        cn.toggled.connect(lambda v: [setattr(self, 'filter_not_pass_only', v), self._update_test_execution_display()]); l.addWidget(cn)
        sp = QSplitter(Qt.Horizontal)
        for t, vd, is_ign in [("Include List", self.include_testbeds_vars, False), ("Exclude List", self.ignore_testbeds_vars, True)]:
            g = QGroupBox(t); gl = QVBoxLayout(g); sc = QScrollArea(); sc.setWidgetResizable(True)
            ct = QWidget(); ct.setObjectName("list-container"); cl = QVBoxLayout(ct); sc.setWidget(ct)
            for tb in self.all_testbeds:
                auto = is_ign and not self._is_testbed_enabled(tb); text = f"{tb} (OFF)" if auto else tb
                c = QCheckBox(text); c.setChecked(vd.get(tb, False) or auto)
                if auto: c.setEnabled(False)
                else: c.toggled.connect(lambda v, t=tb, vd=vd: [vd.update({t: v}), self._update_test_execution_display()])
                cl.addWidget(c)
            gl.addWidget(sc); sp.addWidget(g)
        l.addWidget(sp); btn = QPushButton("Close Dashboard"); btn.clicked.connect(d.accept); l.addWidget(btn, 0, Qt.AlignRight); d.exec()

    def _select_all_tests(self):
        for c in self.test_checkboxes.values(): c.setChecked(True)
    def _deselect_all_tests(self):
        for c in self.test_checkboxes.values(): c.setChecked(False)

    def _write_terminal(self, t):
        clr = "#f0f0f0"
        res_match = re.search(r"FINAL TEST RESULT\s*--->\s*(PASS|FAIL)", t, re.IGNORECASE)
        if res_match:
            res = res_match.group(1).upper()
            if res == "PASS":
                clr = "#67c23a"; self.pass_count += 1; self.lbl_pass.setText(str(self.pass_count))
            else:
                clr = "#f56c6c"; self.fail_count += 1; self.lbl_fail.setText(str(self.fail_count))
            self.progress_bar.setValue(self.pass_count + self.fail_count)
        elif "---" in t: clr = "#409eff"
        escaped_t = html.escape(t).replace('\n', '<br>')
        self.terminal.appendHtml(f"<span style='color: {clr};'>{escaped_t}</span>")
        self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def _run_tests(self):
        sel = [n for n, c in self.test_checkboxes.items() if c.isChecked()]
        if not sel: return QMessageBox.warning(self, "No Selection", "Please select test cases.")
        self.total_selected = len(sel); self.pass_count = 0; self.fail_count = 0
        self.lbl_total.setText(str(self.total_selected)); self.lbl_pass.setText("0"); self.lbl_fail.setText("0")
        self.progress_bar.setRange(0, self.total_selected); self.progress_bar.setValue(0); self.progress_bar.setVisible(True)
        self.terminal.clear(); pr = "EHT"; pp = os.path.basename(os.path.dirname(self.config_path_edit.text()))
        if "WTS-" in pp: pr = pp.split('-', 1)[1]
        cmd = [self.wts_executable_path, pr, sel[0]] if len(sel) == 1 else [self.wts_executable_path, "-p", pr, "-g", "wts_group_test.txt"]
        if len(sel) > 1:
            with open("wts_group_test.txt", 'w') as f:
                for t in sel: f.write(f"{t}\n")
        if QMessageBox.question(self, "Verify", f"Start batch run of {len(sel)} tests?") == QMessageBox.Yes:
            self._write_terminal(f"Initiating process...\n\n")
            self.current_worker = CommandWorker(cmd, self.use_wsl); self.current_worker.output_signal.connect(self._write_terminal)
            self.current_worker.finished_signal.connect(lambda: [self._write_terminal("\n--- FINISHED ---"), self.btn_run.setEnabled(True)])
            self.btn_run.setEnabled(False); self.current_worker.start()

    def _stop_tests(self):
        if self.current_worker: self.current_worker.stop()

    def _analyze_results(self):
        self._save_session(); self.result_table.setRowCount(0); role = "AP" if self.res_role_ap.isChecked() else ("STA" if self.res_role_sta.isChecked() else "All")
        tc_targets = [n for n in self.xml_test_case_names if (role=="All" or (role=="AP" and n.split('-', 1)[-1].startswith('4.')) or (role=="STA" and n.split('-', 1)[-1].startswith('5.')))]
        if not os.path.exists(self.log_dir_path): return
        self.test_history_map = {}; fd = self.res_date_edit.date().toPython()
        dirs = sorted([d for d in os.listdir(self.log_dir_path) if os.path.isdir(os.path.join(self.log_dir_path, d))], key=lambda d: os.path.getmtime(os.path.join(self.log_dir_path, d)))
        for f in dirs:
            m = re.search(r'([A-Za-z]{3}-\d{2}-\d{4})', f)
            if m and datetime.strptime(m.group(1), "%b-%d-%Y").date() < fd: continue
            p = os.path.join(self.log_dir_path, f)
            for file in os.listdir(p):
                if file.startswith("log_") and file.endswith(".log"):
                    tc = file[4:-4]
                    if tc in tc_targets:
                        res = "FAIL"
                        try:
                            with open(os.path.join(p, file), 'r', encoding='utf-8', errors='ignore') as logf:
                                if "PASS" in logf.read(): res = "PASS"
                        except: res = "ERROR"
                        self.test_history_map.setdefault(tc, []).append({'result': res, 'folder': f})
        self._populate_results_table(tc_targets)

    def _populate_results_table(self, cases):
        self.result_table.setRowCount(0); hnt, hns = self.chk_hide_nt.isChecked(), self.chk_hide_ns.isChecked(); st = {"PASS": 0, "FAIL": 0, "NT": 0, "NS": 0}
        for tc in cases:
            hist = self.test_history_map.get(tc, []); res, folder = "NT", ""
            if tc in self.not_support_list: res = "Not Support"
            elif hist: res, folder = hist[-1]['result'], hist[-1]['folder']
            st[res if res in st else "FAIL"] += 1
            if (hnt and res == "NT") or (hns and res == "Not Support"): continue
            r = self.result_table.rowCount(); self.result_table.insertRow(r); self.result_table.setItem(r, 0, QTableWidgetItem(tc))
            ri = QTableWidgetItem(res); ri.setTextAlignment(Qt.AlignCenter); self.result_table.setItem(r, 1, ri); self.result_table.setItem(r, 2, QTableWidgetItem(folder))
        self.statusBar().showMessage(f"Analytics: {st['PASS']} PASS, {st['FAIL']} FAIL, {st['NT']} NT")

    def _on_result_view_toggle(self):
        role = "AP" if self.res_role_ap.isChecked() else ("STA" if self.res_role_sta.isChecked() else "All")
        self._populate_results_table([n for n in self.xml_test_case_names if (role=="All" or (role=="AP" and n.split('-', 1)[-1].startswith('4.')) or (role=="STA" and n.split('-', 1)[-1].startswith('5.')))])

    def _load_log_folders(self):
        self.log_folder_list.clear(); fd = self.log_date_edit.date().toPython()
        if not os.path.exists(self.log_dir_path): return
        dirs = sorted([d for d in os.listdir(self.log_dir_path) if os.path.isdir(os.path.join(self.log_dir_path, d))], key=lambda d: os.path.getmtime(os.path.join(self.log_dir_path, d)), reverse=True)
        for d in dirs:
            m = re.search(r'([A-Za-z]{3}-\d{2}-\d{4})', d)
            if not m or datetime.strptime(m.group(1), "%b-%d-%Y").date() >= fd: self.log_folder_list.addItem(d)

    def _on_log_folder_select(self):
        self.log_file_table.setRowCount(0); sel = self.log_folder_list.selectedItems()
        if not sel: return
        p = os.path.join(self.log_dir_path, sel[0].text())
        for f in sorted(os.listdir(p)):
            if f.endswith(".log") or "pcapng" in f:
                r = self.log_file_table.rowCount(); self.log_file_table.insertRow(r); self.log_file_table.setItem(r, 0, QTableWidgetItem(f))
                self.log_file_table.setItem(r, 1, QTableWidgetItem(f"{os.path.getsize(os.path.join(p, f))/1024:.1f} KB"))

    def _open_log_file(self, it):
        p = os.path.join(self.log_dir_path, self.log_folder_list.currentItem().text(), self.log_file_table.item(it.row(), 0).text())
        if os.name == 'nt': os.startfile(p)
        elif self.linux_editor_command: subprocess.Popen(self.linux_editor_command + [p])

    def _show_documentation(self):
        d = QDialog(self); d.setWindowTitle("WTS User Guide"); d.resize(900, 700); l = QVBoxLayout(d)
        apply_win_caption_color(d, "#dcdfe6")
        d.setStyleSheet("background-color: white;")
        b = QTextBrowser(); l.addWidget(b)
        bd = os.path.dirname(os.path.abspath(__file__)); pts = [os.path.join(sys._MEIPASS, "README.md") if hasattr(sys, '_MEIPASS') else None, os.path.join(bd, "README.md"), os.path.join(os.path.dirname(bd), "README.md"), "README.md"]
        c = "# Manual Missing\nDocumentation not found."
        for p in [x for x in pts if x and os.path.exists(x)]:
            try:
                with open(p, "r", encoding="utf-8") as f: c = f.read(); break
            except: pass
        b.setMarkdown(c); d.exec()

    def _show_about(self): QMessageBox.about(self, "About", f"WTS GUI Dashboard v{self.APP_VERSION}\nCopyright 2026 Realtek Corp.")

    def _on_log_folder_right_click(self, pos):
        it = self.log_folder_list.itemAt(pos)
        if it:
            m = QMenu(); za = m.addAction("Zip Archive and Export...")
            if m.exec(self.log_folder_list.mapToGlobal(pos)) == za: self._zip_folder(it.text())

    def _zip_folder(self, f):
        p, _ = QFileDialog.getSaveFileName(self, "Save Archive", f"{f}.zip", "Archives (*.zip)")
        if p:
            shutil.make_archive(os.path.splitext(p)[0], 'zip', self.log_dir_path, f)
            QMessageBox.information(self, "Success", "Log zipped and saved.")

    def _show_result_context_menu(self, pos):
        it = self.result_table.itemAt(pos)
        if it:
            m = QMenu(); ha = m.addAction("Show Run History")
            if m.exec(self.result_table.mapToGlobal(pos)) == ha: self._show_history(self.result_table.item(it.row(), 0).text())

    def _show_history(self, tc):
        h = self.test_history_map.get(tc, [])
        if not h: return
        d = QDialog(self); d.setWindowTitle(f"Historical Records: {tc}"); d.resize(600, 400); l = QVBoxLayout(d)
        apply_win_caption_color(d, "#dcdfe6")
        t = QTableWidget(len(h), 2); t.setHorizontalHeaderLabels(["Result", "Folder"]); t.setItemDelegateForColumn(0, StatusPillDelegate(self))
        for i, rec in enumerate(reversed(h)):
            t.setItem(i, 0, QTableWidgetItem(rec['result'])); t.setItem(i, 1, QTableWidgetItem(rec['folder']))
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch); l.addWidget(t); d.exec()

    def _export_results(self):
        p, f = QFileDialog.getSaveFileName(self, "Export Results", "testing_report.csv", "CSV (*.csv);;Excel (*.xlsx)")
        if not p: return
        if "xlsx" in f and HAS_OPENPYXL: self._export_excel(p)
        else:
            with open(p, 'w', newline='', encoding='utf-8-sig') as csvf:
                w = csv.writer(csvf); w.writerow(["Case", "Result", "Log"]); [w.writerow([self.result_table.item(r, c).text() for c in range(3)]) for r in range(self.result_table.rowCount())]

    def _export_excel(self, p):
        wb = openpyxl.Workbook(); ws = wb.active; ws.append(["Case", "Result", "Log"]); [ws.append([self.result_table.item(r, c).text() for c in range(3)]) for r in range(self.result_table.rowCount())]; wb.save(p)

    def _load_tms_data(self):
        if not os.path.exists(self.tms_client_conf_path): return
        self.tms_tree.clear(); self.tms_data = []
        with open(self.tms_client_conf_path, 'r', encoding='utf-8') as f:
            for line in f:
                s = line.strip(); k, v, t = s, "", "comment"
                if s and not s.startswith('#') and '=' in s: parts = s.split('=', 1); k, v, t = parts[0].strip(), parts[1].strip(), "kv_pair"
                self.tms_data.append({'original': line, 'key': k, 'value': v, 'type': t})
                it = QTreeWidgetItem([k, v])
                if t == "comment": it.setForeground(0, QtGui.QColor("#909399"))
                self.tms_tree.addTopLevelItem(it)
        for d in self.tms_data:
            if d['key'] == 'TMS_feature': self.chk_tms_upload.setChecked(d['value'].lower() == 'enabled')

    def _on_tms_tree_double_click(self, it, col):
        if col == 1:
            idx = self.tms_tree.indexOfTopLevelItem(it)
            if self.tms_data[idx]['type'] == 'kv_pair':
                v, ok = QtWidgets.QInputDialog.getText(self, "Edit Parameter", f"Update {it.text(0)}:", QLineEdit.Normal, it.text(1))
                if ok: it.setText(1, v); self.tms_data[idx]['value'] = v

    def _save_tms_file(self):
        if self._perform_tms_save():
            QMessageBox.information(self, "Success", "TMS config updated.")

    def _perform_tms_save(self):
        try:
            with open(self.tms_client_conf_path, 'w', encoding='utf-8', newline='\n') as f:
                for d in self.tms_data: f.write(f"{d['key']}={d['value']}\n" if d['type'] == 'kv_pair' else d['original'])
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return False

    def _on_tms_upload_toggle(self):
        en = "Enabled" if self.chk_tms_upload.isChecked() else "Disabled"
        for i, d in enumerate(self.tms_data):
            if d['key'] in ['TMS_feature', 'FTP_feature']: d['value'] = en; self.tms_tree.topLevelItem(i).setText(1, en)
        self._perform_tms_save()

    def _check_not_support_file(self):
        p = self.session_settings.get('not_support_path', self.not_support_default_path)
        if os.path.exists(p) and QMessageBox.question(self, "Excluded Items", f"Found saved exclusion list at:\n{p}\n\nApply these exclusions?") == QMessageBox.Yes: self._load_not_support_data(p)

    def _load_not_support_data(self, p):
        try:
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if isinstance(d, list): self.not_support_list = set(d); self._update_test_execution_display(); self.session_settings['not_support_path'] = p; self._save_session()
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to load exclusions: {e}")

    def _save_not_support_data(self, p, data):
        try:
            with open(p, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
            self.session_settings['not_support_path'] = p; self._save_session(); QMessageBox.information(self, "Success", "Exclusion list saved.")
        except Exception as e: QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _show_not_support_config_window(self):
        d = QDialog(self); d.setWindowTitle("Manage Excluded Test Cases"); d.resize(800, 600); l = QVBoxLayout(d)
        apply_win_caption_color(d, "#dcdfe6")
        ah = QHBoxLayout(); btn_imp = QPushButton("Import List"); btn_sav = QPushButton("Save As..."); btn_imp.setObjectName("ghost-btn"); btn_sav.setObjectName("ghost-btn")
        ah.addWidget(btn_imp); ah.addWidget(btn_sav); ah.addStretch(); l.addLayout(ah)
        g = QGroupBox("Master Exclusion Registry"); gl = QVBoxLayout(g); sc = QScrollArea(); sc.setWidgetResizable(True)
        ct = QWidget(); ct.setObjectName("list-container"); cl = QVBoxLayout(ct); sc.setWidget(ct); vars_dict = {}
        def refresh_ui():
            while cl.count():
                w = cl.takeAt(0).widget()
                if w: w.deleteLater()
            vars_dict.clear()
            for n in self.xml_test_case_names:
                c = QCheckBox(n); c.setChecked(n in self.not_support_list); cl.addWidget(c); vars_dict[n] = c
        refresh_ui(); gl.addWidget(sc); l.addWidget(g)
        bh = QHBoxLayout(); b_all = QPushButton("Select All"); b_none = QPushButton("Clear All"); b_app = QPushButton("Save & Close Dashboard"); b_app.setObjectName("action-btn")
        bh.addWidget(b_all); bh.addWidget(b_none); bh.addStretch(); bh.addWidget(b_app); l.addLayout(bh)
        btn_imp.clicked.connect(lambda: [(p := QFileDialog.getOpenFileName(d, "Import", "", "JSON (*.json)")[0]) and [self._load_not_support_data(p), refresh_ui()]])
        btn_sav.clicked.connect(lambda: [(p := QFileDialog.getSaveFileName(d, "Save", "wts_not_support.json", "JSON (*.json)")[0]) and self._save_not_support_data(p, [n for n, c in vars_dict.items() if c.isChecked()])])
        b_all.clicked.connect(lambda: [c.setChecked(True) for c in vars_dict.values()]); b_none.clicked.connect(lambda: [c.setChecked(False) for c in vars_dict.values()])
        b_app.clicked.connect(lambda: [setattr(self, 'not_support_list', {n for n, c in vars_dict.items() if c.isChecked()}), self._update_test_execution_display(), d.accept()]); d.exec()

    def _find_and_cache_text_editor(self):
        if os.name != 'nt':
            for e in ['gedit', 'xdg-open', 'kate', 'mousepad']:
                if shutil.which(e): self.linux_editor_command = [e]; break

    def closeEvent(self, event):
        if self.current_worker:
            if QMessageBox.question(self, "Exit Active Session", "A test process is currently running. Stop it and exit?") == QMessageBox.Yes: self.current_worker.stop(); event.accept()
            else: event.ignore()
        else: event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setFont(QtGui.QFont("Segoe UI Variable Text", 9))
    window = WtsGuiApp(); window.show(); sys.exit(app.exec())
