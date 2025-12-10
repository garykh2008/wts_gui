import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import subprocess
import sys
import threading
import shutil
import os
import csv

# Try to import tkcalendar for a better date picking experience.
try:
	from tkcalendar import DateEntry
	HAS_CALENDAR = True
except ImportError:
	HAS_CALENDAR = False

# pyinstaller --name wts_gui --onefile --windowed wts_gui.py


class WtsGuiApp(tk.Tk):
	def __init__(self):

		super().__init__()
		self.APP_VERSION = "2.0"
		self.app_initialized = False # Flag to prevent overwriting settings during initialization
		self.title(f"WTS GUI v{self.APP_VERSION}")
		self.geometry("1024x768")

		self.config_file_path = tk.StringVar()
		self.xml_file_path = tk.StringVar()
		self.settings_file = "wts_gui.settings.json"
		self.session_settings = {} # Stores last opened file paths

		self.xml_search_term = tk.StringVar()
		self.xml_test_cases = {} # To store parsed TestCase elements
		self.xml_test_case_names = [] # To store all test case names for filtering

		self.viewer_role_filter = tk.StringVar(value="All")
		self.test_execution_search_term = tk.StringVar()
		self.test_role_filter = tk.StringVar(value="All")
		self.result_role_filter = tk.StringVar(value="All")
		self.log_filter_date = tk.StringVar()
		self.filter_not_pass_only = tk.BooleanVar(value=False)
		self.all_testbeds = [] # Cache for all unique testbeds found in XML
		self.ignore_testbeds_vars = {} # BooleanVars for ignore checkboxes in Advanced Options
		self.include_testbeds_vars = {} # BooleanVars for include checkboxes in Advanced Options

		# --- TmsClient.conf related ---
		# --- Path setup for bundled and script execution ---
		# Determine the base directory differently if running as a bundled executable
		self.linux_editor_command = None
		if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
			# Running in a PyInstaller bundle, executable is in 'bin'
			self.bin_dir = os.path.dirname(sys.executable)
		else:
			# Running as a normal .py script, script is in 'bin'
			self.bin_dir = os.path.dirname(os.path.abspath(__file__))

		# Determine if we should use native Windows executable or WSL
		self.use_wsl = False
		self.wts_executable_path = os.path.join(self.bin_dir, 'wts')

		if os.name == 'nt':
			# Check if native Windows executable exists
			wts_exe_path = os.path.join(self.bin_dir, 'wts.exe')
			if os.path.exists(wts_exe_path):
				self.wts_executable_path = wts_exe_path
			else:
				# Fallback to WSL if wts.exe is missing
				self.use_wsl = True
				self.wts_executable_path = os.path.join(self.bin_dir, 'wts')

		self.log_dir_path = os.path.join(self.bin_dir, 'log')
		wts_root_dir = os.path.dirname(self.bin_dir)
		self.tms_client_conf_path = os.path.join(wts_root_dir, 'config', 'TmsClient.conf')
		self.tms_data = []
		self.upload_to_tms_var = tk.BooleanVar()
		self.current_process = None # Track the running process

		self.selection_canvas = None

		# --- Not Support Feature ---
		self.not_support_list = set()
		self.not_support_file_name = "wts_not_support.json"
		self.not_support_default_path = os.path.join(self.bin_dir, self.not_support_file_name)

		self._create_menu()
		self._create_widgets()

		# Bind closing event to ensure background processes are killed
		self.protocol("WM_DELETE_WINDOW", self._on_closing)

		if os.name == 'nt':
			self.bind_all("<MouseWheel>", self._on_global_mousewheel)
		else:
			self.bind_all("<Button-4>", self._on_global_mousewheel)
			self.bind_all("<Button-5>", self._on_global_mousewheel)

		if not self._check_environment():
			self.withdraw() # Hide the main window before showing the error
			messagebox.showerror("Environment Error", "This program must be run from the 'bin' directory of the WTS tool,\nand the 'wts' executable must be in the same directory.")
			self.destroy()
			return

		self._load_last_session()
		self._load_tms_data()
		self._find_and_cache_text_editor()
		self._load_log_folders()

		self.app_initialized = True

		self.after(500, self._check_not_support_file) # Check after a short delay to ensure UI is ready

	def _create_menu(self):
		menubar = tk.Menu(self)
		self.config(menu=menubar)

		help_menu = tk.Menu(menubar, tearoff=0)
		menubar.add_cascade(label="Help", menu=help_menu)
		help_menu.add_command(label="Documentation", command=self._show_documentation)
		help_menu.add_command(label="About", command=self._show_about)

	def _show_about(self):
		about_text = (
			f"WTS GUI\n"
			f"Version: {self.APP_VERSION}\n\n"
			f"A Graphical User Interface for the Wireless Test System (WTS).\n"
			f"Provides easy configuration, test execution, and result analysis.\n\n"
			f"Copyright © 2025 Realtek Semiconductor Corp. All rights reserved.\n"
		)
		messagebox.showinfo("About WTS GUI", about_text)

	def _show_documentation(self):
		doc_window = tk.Toplevel(self)
		doc_window.title("Documentation")
		doc_window.geometry("800x600")

		text_area = tk.Text(doc_window, wrap=tk.WORD, padx=10, pady=10)
		text_area.pack(fill=tk.BOTH, expand=True)

		# Add Scrollbar
		scrollbar = ttk.Scrollbar(doc_window, orient="vertical", command=text_area.yview)
		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		text_area.config(yscrollcommand=scrollbar.set)
		scrollbar.place(relx=1, rely=0, relheight=1, anchor="ne") # Overlay scrollbar

		# Configure markdown tags
		text_area.tag_config("h1", font=("Helvetica", 18, "bold"), spacing3=10)
		text_area.tag_config("h2", font=("Helvetica", 14, "bold"), spacing3=5)
		text_area.tag_config("h3", font=("Helvetica", 12, "bold"), spacing3=2)
		text_area.tag_config("bold", font=("Helvetica", 10, "bold"))
		text_area.tag_config("code", font=("Courier New", 10), background="#f0f0f0")
		text_area.tag_config("list", lmargin1=20, lmargin2=30)

		# Try to load README.md
		content = "Documentation not found (README.md)."

		# Determine path based on execution mode
		if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
			# Running in a PyInstaller bundle
			# When bundled with --add-data, files are in sys._MEIPASS
			potential_paths = [os.path.join(sys._MEIPASS, "README.md")]
		else:
			# Running as a normal .py script
			base_dir = os.path.dirname(os.path.abspath(__file__))
			potential_paths = [
				os.path.join(base_dir, "README.md"),
				os.path.join(os.path.dirname(base_dir), "README.md"), # If in bin/
				"README.md"
			]

		for p in potential_paths:
			if os.path.exists(p):
				try:
					with open(p, "r", encoding="utf-8") as f:
						content = f.read()
					break
				except Exception:
					pass

		self._render_markdown(text_area, content)
		text_area.config(state=tk.DISABLED)

	def _render_markdown(self, text_widget, content):
		for line in content.splitlines():
			line_strip = line.strip()
			tags = ()

			if line.startswith("# "):
				tags = ("h1",)
				line = line[2:]
			elif line.startswith("## "):
				tags = ("h2",)
				line = line[3:]
			elif line.startswith("### "):
				tags = ("h3",)
				line = line[4:]
			elif line_strip.startswith("* ") or line_strip.startswith("- "):
				tags = ("list",)
				# Keep indentation but replace bullet
				# Simple logic: just render line

			# Handle inline bold (**text**) - Simple implementation
			# Split by **, toggle bold tag
			parts = re.split(r'(\*\*.*?\*\*)', line)
			for part in parts:
				if part.startswith("**") and part.endswith("**"):
					text_widget.insert(tk.END, part[2:-2], tags + ("bold",))
				elif "`" in part: # Basic code block handling in line
					subparts = re.split(r'(`.*?`)', part)
					for subpart in subparts:
						if subpart.startswith("`") and subpart.endswith("`"):
							text_widget.insert(tk.END, subpart[1:-1], tags + ("code",))
						else:
							text_widget.insert(tk.END, subpart, tags)
				else:
					text_widget.insert(tk.END, part, tags)

			text_widget.insert(tk.END, "\n", tags)

	def _create_widgets(self):
		# Create main frame
		main_frame = ttk.Frame(self, padding="10")
		main_frame.pack(fill=tk.BOTH, expand=True)

		# Create notebook (tab controller)
		self.notebook = ttk.Notebook(main_frame)
		self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)

		# --- AllInitConfig Tab ---
		self.config_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.config_tab, text="AllInitConfig Editor")
		self._create_config_tab(self.config_tab)

		# --- Test Execution Tab ---
		self.execution_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.execution_tab, text="Test Execution")
		self._create_test_execution_tab(self.execution_tab)

		# --- Test Result Tab ---
		self.result_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.result_tab, text="Test Result")
		self._create_test_result_tab(self.result_tab)

		# --- Log Viewer Tab ---
		self.log_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.log_tab, text="Log Viewer")
		self._create_log_viewer_tab(self.log_tab)

		# --- MasterTestInfo Tab ---
		self.xml_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.xml_tab, text="MasterTestInfo Viewer")
		self._create_xml_tab(self.xml_tab)

		# --- TmsClient.conf Tab ---
		self.tms_tab = ttk.Frame(self.notebook)
		self.notebook.add(self.tms_tab, text="TmsClient.conf Editor")
		self._create_tms_tab(self.tms_tab)

	def _create_config_tab(self, parent):
		# File selection frame
		file_frame = ttk.LabelFrame(parent, text="Config File Path", padding="10")
		file_frame.pack(fill=tk.X, padx=5, pady=5)

		ttk.Entry(file_frame, textvariable=self.config_file_path, width=80).pack(side=tk.LEFT, fill=tk.X, expand=True)
		ttk.Button(file_frame, text="Browse...", command=self._browse_config_file).pack(side=tk.LEFT, padx=5)
		self.reload_button = ttk.Button(file_frame, text="Reload", command=self._load_config_data, state="disabled")
		self.reload_button.pack(side=tk.LEFT)

		# Device Control Frame
		control_frame = ttk.LabelFrame(parent, text="Device Control", padding="10")
		control_frame.pack(fill=tk.X, padx=5, pady=5)

		# Data display and edit frame
		data_frame = ttk.LabelFrame(parent, text="Config Content", padding="10")
		data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Use a Treeview to display the content
		self.config_tree = ttk.Treeview(data_frame, columns=("Key", "Value"), show="headings")
		self.config_tree.heading("Key", text="Key")
		self.config_tree.heading("Value", text="Value")
		self.config_tree.column("Key", width=300)
		self.config_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Configure tags for styling
		self.config_tree.tag_configure('editable', background='#FFFFE0') # Light yellow background
		self.config_tree.tag_configure('comment', foreground='grey')


		# Edit functionality
		self.config_tree.bind("<Double-1>", self._on_config_tree_double_click)

		# Scrollbar
		scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=self.config_tree.yview)
		scrollbar.pack(side=tk.RIGHT, fill="y")
		self.config_tree.configure(yscrollcommand=scrollbar.set)

		# Add placeholder for device toggles
		self.ap_toggles_frame = ttk.Frame(control_frame)
		self.sta_toggles_frame = ttk.Frame(control_frame)

		# Save button
		save_button = ttk.Button(parent, text="Save AllInitConfig", command=self._save_config_file)
		save_button.pack(pady=10)

	def _create_xml_tab(self, parent):
		# Paned window for left/right view
		paned_window = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
		paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Left Pane: Test Case List
		left_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(left_pane, weight=1)

		# --- Filter Frame ---
		filter_frame = ttk.LabelFrame(left_pane, text="Filter Options", padding="10")
		filter_frame.pack(fill=tk.X, pady=(0, 5))

		# Role filter
		role_frame = ttk.Frame(filter_frame)
		role_frame.pack(fill=tk.X)
		ttk.Label(role_frame, text="Role:").pack(side=tk.LEFT, padx=(0, 10))
		ttk.Radiobutton(role_frame, text="All", variable=self.viewer_role_filter, value="All", command=self._update_viewer_display).pack(side=tk.LEFT)
		ttk.Radiobutton(role_frame, text="AP", variable=self.viewer_role_filter, value="AP", command=self._update_viewer_display).pack(side=tk.LEFT, padx=5)
		ttk.Radiobutton(role_frame, text="STA", variable=self.viewer_role_filter, value="STA", command=self._update_viewer_display).pack(side=tk.LEFT)

		# Search filter
		search_frame = ttk.Frame(filter_frame)
		search_frame.pack(fill=tk.X, pady=(5,0))
		ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
		search_entry = ttk.Entry(search_frame, textvariable=self.xml_search_term)
		search_entry.pack(fill=tk.X, expand=True)
		self.xml_search_term.trace_add("write", self._update_viewer_display)

		list_frame = ttk.Frame(left_pane)
		list_frame.pack(fill=tk.BOTH, expand=True)
		self.test_case_listbox = tk.Listbox(list_frame)
		self.test_case_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.test_case_listbox.yview)
		list_scrollbar.pack(side=tk.RIGHT, fill="y")
		self.test_case_listbox.config(yscrollcommand=list_scrollbar.set)
		self.test_case_listbox.bind("<<ListboxSelect>>", self._on_test_case_select)

		# Right Pane: Test Case Details
		right_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(right_pane, weight=3)

		# XML tree view display
		data_frame = ttk.LabelFrame(right_pane, text="Test Case Details", padding="10")
		data_frame.pack(fill=tk.BOTH, expand=True)

		# Use a Treeview to display the content in a key-value format
		self.xml_tree = ttk.Treeview(data_frame, columns=("Parameter", "Value"), show="headings")
		self.xml_tree.heading("Parameter", text="Parameter")
		self.xml_tree.heading("Value", text="Value")
		self.xml_tree.column("Parameter", width=300)
		self.xml_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Scrollbars
		scrollbar_y = ttk.Scrollbar(data_frame, orient="vertical", command=self.xml_tree.yview)
		scrollbar_y.pack(side=tk.RIGHT, fill="y")
		self.xml_tree.configure(yscrollcommand=scrollbar_y.set)

	def _create_test_execution_tab(self, parent):
		paned_window = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
		paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# --- Left Pane: Test Case Selection ---
		left_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(left_pane, weight=1)

		# --- Filter Frame ---
		filter_frame = ttk.LabelFrame(left_pane, text="Filter Options", padding="10")
		filter_frame.pack(fill=tk.X, pady=(0, 5))

		# Role filter
		role_frame = ttk.Frame(filter_frame)
		role_frame.pack(fill=tk.X)
		ttk.Label(role_frame, text="Role:").pack(side=tk.LEFT, padx=(0, 10))
		ttk.Radiobutton(role_frame, text="All", variable=self.test_role_filter, value="All", command=self._update_test_execution_display).pack(side=tk.LEFT)
		ttk.Radiobutton(role_frame, text="AP", variable=self.test_role_filter, value="AP", command=self._update_test_execution_display).pack(side=tk.LEFT, padx=5)
		ttk.Radiobutton(role_frame, text="STA", variable=self.test_role_filter, value="STA", command=self._update_test_execution_display).pack(side=tk.LEFT)

		# Search filter
		search_frame = ttk.Frame(filter_frame)
		search_frame.pack(fill=tk.X, pady=(5,0))
		ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
		search_entry = ttk.Entry(search_frame, textvariable=self.test_execution_search_term)
		search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
		self.test_execution_search_term.trace_add("write", self._update_test_execution_display)

		ttk.Button(search_frame, text="Advanced Option", command=self._show_advanced_options_popup).pack(side=tk.LEFT, padx=(5, 0))

		# Action frame for additional config buttons
		action_frame = ttk.Frame(filter_frame)
		action_frame.pack(fill=tk.X, pady=(5, 0))
		ttk.Button(action_frame, text="Config Not Support", command=self._show_not_support_config_window).pack(side=tk.LEFT)

		# Test case selection frame
		self.selection_frame = ttk.LabelFrame(left_pane, text="Test Case Selection", padding="10")
		self.selection_frame.pack(fill=tk.BOTH, expand=True)

		# Buttons for selection control
		select_button_frame = ttk.Frame(self.selection_frame)
		select_button_frame.pack(fill=tk.X, pady=(0, 5))
		ttk.Button(select_button_frame, text="Select All", command=self._select_all_tests).pack(side=tk.LEFT)
		ttk.Button(select_button_frame, text="Deselect All", command=self._deselect_all_tests).pack(side=tk.LEFT, padx=5)

		# Scrollable frame for checkboxes
		canvas = tk.Canvas(self.selection_frame)
		self.selection_canvas = canvas
		scrollbar = ttk.Scrollbar(self.selection_frame, orient="vertical", command=canvas.yview)
		self.test_checkbutton_frame = ttk.Frame(canvas)
		canvas.configure(yscrollcommand=scrollbar.set)

		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		canvas_frame = canvas.create_window((0, 0), window=self.test_checkbutton_frame, anchor="nw")

		def on_frame_configure(event):
			canvas.configure(scrollregion=canvas.bbox("all"))
		self.test_checkbutton_frame.bind("<Configure>", on_frame_configure)

		def on_canvas_configure(event):
			canvas.itemconfig(canvas_frame, width=event.width)
		canvas.bind("<Configure>", on_canvas_configure)

		self.test_checkbuttons = {}

		# Control Buttons Frame
		button_frame = ttk.Frame(left_pane)
		button_frame.pack(pady=10, fill=tk.X)

		# Run button
		run_button = ttk.Button(button_frame, text="Run Selected Tests", command=self._run_tests)
		run_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

		# Stop button
		stop_button = ttk.Button(button_frame, text="Stop Tests", command=self._stop_tests)
		stop_button.pack(side=tk.LEFT, fill=tk.X, expand=True)

		# --- Right Pane: Terminal Output ---
		right_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(right_pane, weight=3)

		terminal_frame = ttk.LabelFrame(right_pane, text="Terminal Output", padding="10")
		terminal_frame.pack(fill=tk.BOTH, expand=True)
		self.terminal_output = tk.Text(terminal_frame, wrap=tk.WORD, state=tk.DISABLED, bg="black", fg="white", insertbackground="white", font=("Consolas", 12))
		self.terminal_output.pack(fill=tk.BOTH, expand=True)
		# Configure tags for colored output
		self.terminal_output.tag_configure("pass", foreground="lime green")
		self.terminal_output.tag_configure("fail", foreground="red")
		self.terminal_output.tag_configure("info", foreground="cyan")

	def _update_selection_count(self):
		total = len(self.test_checkbuttons)
		selected = sum(1 for var in self.test_checkbuttons.values() if var.get())
		self.selection_frame.config(text=f"Test Case Selection ({selected}/{total})")

	def _create_tms_tab(self, parent):
		# Action buttons frame
		action_frame = ttk.LabelFrame(parent, text="File Actions", padding="10")
		action_frame.pack(fill=tk.X, padx=5, pady=5)
		ttk.Button(action_frame, text="Reload", command=self._load_tms_data).pack(side=tk.LEFT, padx=5)
		ttk.Button(action_frame, text="Save", command=self._save_tms_file).pack(side=tk.LEFT)
		tms_upload_cb = ttk.Checkbutton(action_frame, text="Upload To TMS", variable=self.upload_to_tms_var, command=self._on_tms_upload_toggle)
		tms_upload_cb.pack(side=tk.LEFT, padx=10)

		# Data display frame
		data_frame = ttk.LabelFrame(parent, text="TmsClient.conf Content", padding="10")
		data_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Use a Treeview to display the content
		self.tms_tree = ttk.Treeview(data_frame, columns=("Key", "Value"), show="headings")
		self.tms_tree.heading("Key", text="Key")
		self.tms_tree.heading("Value", text="Value")
		self.tms_tree.column("Key", width=300)
		self.tms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Configure tags for styling
		self.tms_tree.tag_configure('editable', background='#FFFFE0') # Light yellow background
		self.tms_tree.tag_configure('comment', foreground='grey')

		# Scrollbar
		scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=self.tms_tree.yview)
		scrollbar.pack(side=tk.RIGHT, fill="y")
		self.tms_tree.configure(yscrollcommand=scrollbar.set)

		self.tms_tree.bind("<Double-1>", self._on_tms_tree_double_click)

	def _create_log_viewer_tab(self, parent):
		paned_window = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
		paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# --- Left Pane: Log Folder List ---
		left_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(left_pane, weight=1)

		# Filter frame
		filter_frame = ttk.LabelFrame(left_pane, text="Filter Logs", padding="10")
		filter_frame.pack(fill=tk.X, pady=(0, 5))
		ttk.Label(filter_frame, text="Show logs on or after (YYYY-MM-DD):").pack(anchor='w')

		# Use DateEntry if available, otherwise fall back to a standard Entry.
		if HAS_CALENDAR:
			# The DateEntry widget handles its own validation and format.
			# It automatically updates the bound textvariable.
			# date_pattern uses Babel syntax: 'y' is year, 'M' is month, 'd' is day.
			# Removed custom colors and added locale='en_US' to improve compatibility with WSL/Linux X servers.
			date_entry = DateEntry(filter_frame, textvariable=self.log_filter_date, date_pattern='yyyy-MM-dd', locale='en_US', width=12, borderwidth=2)
			date_entry.pack(fill=tk.X, pady=(0, 5))
			date_entry.bind("<<DateEntrySelected>>", self._load_log_folders)
		else:
			date_entry = ttk.Entry(filter_frame, textvariable=self.log_filter_date)
			date_entry.pack(fill=tk.X, pady=(0, 5))
			date_entry.bind("<Return>", self._load_log_folders)
		ttk.Button(filter_frame, text="Filter / Refresh", command=self._load_log_folders).pack(anchor='w')
		# Log folder list
		log_list_frame = ttk.LabelFrame(left_pane, text="Log Folders", padding="10")
		log_list_frame.pack(fill=tk.BOTH, expand=True)

		self.log_folder_tree = ttk.Treeview(log_list_frame, show="tree")
		self.log_folder_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		log_folder_scrollbar = ttk.Scrollbar(log_list_frame, orient="vertical", command=self.log_folder_tree.yview)
		log_folder_scrollbar.pack(side=tk.RIGHT, fill="y")
		self.log_folder_tree.configure(yscrollcommand=log_folder_scrollbar.set)
		self.log_folder_tree.bind("<<TreeviewSelect>>", self._on_log_folder_select)

		# Right-click binding for Zip and Save
		self.log_folder_tree.bind("<Button-3>", self._on_log_folder_right_click)
		if os.name != "nt":
			self.log_folder_tree.bind("<Button-2>", self._on_log_folder_right_click)

		# --- Right Pane: Log File List ---
		right_pane = ttk.Frame(paned_window, padding=5)
		paned_window.add(right_pane, weight=2)

		file_list_frame = ttk.LabelFrame(right_pane, text="Files in Selected Log Folder", padding="10")
		file_list_frame.pack(fill=tk.BOTH, expand=True)

		self.log_file_tree = ttk.Treeview(file_list_frame, columns=("File", "Size"), show="headings")
		self.log_file_tree.heading("File", text="File")
		self.log_file_tree.heading("Size", text="Size")
		self.log_file_tree.column("File", width=300)
		self.log_file_tree.column("Size", width=100, anchor='e')
		self.log_file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		log_file_scrollbar = ttk.Scrollbar(file_list_frame, orient="vertical", command=self.log_file_tree.yview)
		log_file_scrollbar.pack(side=tk.RIGHT, fill="y")
		self.log_file_tree.configure(yscrollcommand=log_file_scrollbar.set)
		self.log_file_tree.bind("<Double-1>", self._open_log_file)

	def _save_result_role(self):
		self.session_settings['test_result_role'] = self.result_role_filter.get()
		self._save_session()

	def _create_test_result_tab(self, parent):
		# --- Filter Frame ---
		filter_frame = ttk.LabelFrame(parent, text="Analysis Options", padding="10")
		filter_frame.pack(fill=tk.X, padx=5, pady=5)

		# Role Filter
		ttk.Label(filter_frame, text="Role:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Radiobutton(filter_frame, text="All", variable=self.result_role_filter, value="All", command=self._save_result_role).pack(side=tk.LEFT)
		ttk.Radiobutton(filter_frame, text="AP", variable=self.result_role_filter, value="AP", command=self._save_result_role).pack(side=tk.LEFT, padx=5)
		ttk.Radiobutton(filter_frame, text="STA", variable=self.result_role_filter, value="STA", command=self._save_result_role).pack(side=tk.LEFT, padx=(0, 20))

		ttk.Label(filter_frame, text="Analyze logs on or after:").pack(side=tk.LEFT, padx=(0, 5))

		# Reuse the same date variable or create a new one? Let's create a new one to keep states independent.
		self.result_filter_date = tk.StringVar()
		# Initialize with today's date
		self.result_filter_date.set(datetime.now().strftime("%Y-%m-%d"))

		if HAS_CALENDAR:
			date_entry = DateEntry(filter_frame, textvariable=self.result_filter_date, date_pattern='yyyy-MM-dd', locale='en_US', width=12, borderwidth=2)
			date_entry.pack(side=tk.LEFT, padx=(0, 10))
		else:
			date_entry = ttk.Entry(filter_frame, textvariable=self.result_filter_date, width=12)
			date_entry.pack(side=tk.LEFT, padx=(0, 10))

		analyze_button = ttk.Button(filter_frame, text="Analyze Result", command=self._analyze_results)
		analyze_button.pack(side=tk.LEFT, padx=(0, 10))

		export_button = ttk.Button(filter_frame, text="Export Result", command=self._export_results_to_excel)
		export_button.pack(side=tk.LEFT, padx=(0, 10))

		self.hide_nt_var = tk.BooleanVar(value=False)
		ttk.Checkbutton(filter_frame, text="Hide NT", variable=self.hide_nt_var, command=self._on_result_view_toggle).pack(side=tk.LEFT)

		self.hide_ns_var = tk.BooleanVar(value=False)
		ttk.Checkbutton(filter_frame, text="Hide Not Support", variable=self.hide_ns_var, command=self._on_result_view_toggle).pack(side=tk.LEFT, padx=(5, 0))

		# --- Results Frame ---
		self.results_frame = ttk.LabelFrame(parent, text="Analysis Results", padding="10")
		self.results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		columns = ("Test Case", "Result", "Log Folder")
		self.result_tree = ttk.Treeview(self.results_frame, columns=columns, show="headings")

		# Define headings
		self.result_tree.heading("Test Case", text="Test Case")
		self.result_tree.heading("Result", text="Result")
		self.result_tree.heading("Log Folder", text="Log Folder")

		# Define columns
		self.result_tree.column("Test Case", width=250)
		self.result_tree.column("Result", width=80, anchor="center")
		self.result_tree.column("Log Folder", width=200)

		self.result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Scrollbar
		scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.result_tree.yview)
		scrollbar.pack(side=tk.RIGHT, fill="y")
		self.result_tree.configure(yscrollcommand=scrollbar.set)

		# Tag configurations for coloring
		self.result_tree.tag_configure('PASS', background='#ccffcc') # Light green
		self.result_tree.tag_configure('FAIL', background='#ffcccc') # Light red
		self.result_tree.tag_configure('NT', background='white', foreground='black') # NT style
		self.result_tree.tag_configure('Not Support', background='#e0e0e0', foreground='grey') # Light grey for NS

		# Right-click binding for history
		# Bind Button-3 (Right Click) for all platforms as it is the standard context menu trigger.
		self.result_tree.bind("<Button-3>", self._show_history_popup)

		# On Linux/macOS, Button-2 is sometimes used for context menus or middle click.
		# Adding it as a fallback/alternative binding.
		if os.name != "nt":
			self.result_tree.bind("<Button-2>", self._show_history_popup)

	def _show_history_popup(self, event):
		item_id = self.result_tree.identify_row(event.y)
		if not item_id:
			return

		self.result_tree.selection_set(item_id)
		test_case = self.result_tree.item(item_id, "values")[0]
		history = self.test_history_map.get(test_case, [])

		if not history:
			messagebox.showinfo("No History", f"No history found for {test_case}")
			return

		# Create popup window
		top = tk.Toplevel(self)
		top.title(f"History: {test_case}")
		top.geometry("600x300")

		tree = ttk.Treeview(top, columns=("Result", "Log Folder"), show="headings")
		tree.heading("Result", text="Result")
		tree.heading("Log Folder", text="Log Folder")
		tree.column("Result", width=80, anchor="center")
		tree.column("Log Folder", width=450)

		tree.tag_configure('PASS', background='#ccffcc')
		tree.tag_configure('FAIL', background='#ffcccc')

		tree.pack(fill=tk.BOTH, expand=True)

		# Scrollbar
		scrollbar = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
		scrollbar.pack(side=tk.RIGHT, fill="y")
		tree.configure(yscrollcommand=scrollbar.set)

		# Populate history (newest first for better readability in popup)
		for record in reversed(history):
			tree.insert("", "end", values=(record['result'], record['folder']), tags=(record['result'],))

		# Bind right-click on history items
		tree.bind("<Button-3>", lambda event: self._on_history_item_right_click(event, tree))
		if os.name != "nt":
			tree.bind("<Button-2>", lambda event: self._on_history_item_right_click(event, tree))

	def _on_history_item_right_click(self, event, tree):
		item_id = tree.identify_row(event.y)
		if not item_id:
			return

		tree.selection_set(item_id)
		values = tree.item(item_id, "values")
		if not values:
			return

		folder_name = values[1]

		menu = tk.Menu(tree, tearoff=0)
		menu.add_command(label="Zip and Save As...", command=lambda: self._zip_and_save_log(folder_name))
		menu.post(event.x_root, event.y_root)

	def _zip_and_save_log(self, folder_name):
		source_path = os.path.join(self.log_dir_path, folder_name)
		if not os.path.exists(source_path):
			messagebox.showerror("Error", f"Log folder not found: {source_path}")
			return

		save_path = filedialog.asksaveasfilename(
			defaultextension=".zip",
			filetypes=[("Zip files", "*.zip"), ("All files", "*.*")],
			initialfile=f"{folder_name}.zip",
			title="Save Log as Zip"
		)

		if not save_path:
			return

		try:
			# Create a zip archive
			# shutil.make_archive expects the base_name without extension if format is specified,
			# but here save_path usually includes it. We'll use root_dir and base_dir to structure it.

			# Remove extension from save_path for make_archive base_name argument if it exists
			base_name = os.path.splitext(save_path)[0]

			shutil.make_archive(base_name, 'zip', root_dir=self.log_dir_path, base_dir=folder_name)
			messagebox.showinfo("Success", f"Log folder saved to:\n{save_path}")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to zip and save log: {e}")

	def _analyze_results(self):
		# Save current filter date
		self.session_settings['result_filter_date'] = self.result_filter_date.get()
		# Save current role filter
		self.session_settings['test_result_role'] = self.result_role_filter.get()
		self._save_session()

		# Clear existing results
		for item in self.result_tree.get_children():
			self.result_tree.delete(item)

		# 1. Determine the target test cases (The "Population")
		role = self.result_role_filter.get()
		target_test_cases = self.xml_test_case_names

		if not target_test_cases:
			messagebox.showinfo("Info", "No test cases loaded. Please load MasterTestInfo.xml first.")
			return

		if role == "AP":
			target_test_cases = [name for name in target_test_cases if name.split('-', 1)[-1].startswith('4.')]
		elif role == "STA":
			target_test_cases = [name for name in target_test_cases if name.split('-', 1)[-1].startswith('5.')]

		# 2. Parse filter date
		filter_date = None
		try:
			if self.result_filter_date.get():
				filter_date = datetime.strptime(self.result_filter_date.get(), "%Y-%m-%d").date()
		except ValueError:
			messagebox.showwarning("Invalid Date", "Please use YYYY-MM-DD format for the date filter.")
			return

		if not os.path.exists(self.log_dir_path):
			messagebox.showinfo("Info", "Log directory does not exist.")
			# Even if log dir missing, show NT for all
			self._populate_results_tree(target_test_cases, {})
			return

		# 3. Scan logs and build a map of {test_case: [list of results]}
		# We want ALL results for history, but show LATEST in tree.
		self.test_history_map = {} # Stores {test_case: [{'result':..., 'folder':...}, ...]}

		try:
			all_dirs = [d for d in os.listdir(self.log_dir_path) if os.path.isdir(os.path.join(self.log_dir_path, d))]
			# Sort by modification time (oldest to newest)
			all_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(self.log_dir_path, d)))
		except Exception as e:
			messagebox.showerror("Error", f"Failed to list log directories: {e}")
			return

		for folder_name in all_dirs:
			folder_path = os.path.join(self.log_dir_path, folder_name)
			folder_mtime = os.path.getmtime(folder_path)

			# Check date filter
			try:
				date_match = re.search(r'([A-Za-z]{3}-\d{2}-\d{4})', folder_name)
				if date_match:
					folder_date = datetime.strptime(date_match.group(1), "%b-%d-%Y").date()
					if filter_date and folder_date < filter_date:
						continue
			except ValueError:
				if filter_date: continue

			# Scan for log_*.log files
			try:
				for filename in os.listdir(folder_path):
					if filename.startswith("log_") and filename.endswith(".log"):
						test_case_name = filename[4:-4]

						# Only process if this is one of our target test cases
						if test_case_name in target_test_cases:

							# Determine PASS/FAIL
							result = "FAIL"
							try:
								with open(os.path.join(folder_path, filename), 'r', encoding='utf-8', errors='ignore') as f:
									if "PASS" in f.read():
										result = "PASS"
							except:
								result = "ERROR"

							# Append to history
							if test_case_name not in self.test_history_map:
								self.test_history_map[test_case_name] = []

							self.test_history_map[test_case_name].append({
								'result': result,
								'folder': folder_name,
								'file': filename,
								'timestamp': folder_mtime
							})
			except Exception:
				pass # Skip folder if unreadable

		# 4. Populate Treeview
		self._populate_results_tree(target_test_cases)

	def _export_results_to_excel(self):
		if not self.result_tree.get_children():
			messagebox.showinfo("Info", "No results to export. Please analyze results first.")
			return

		# Check if openpyxl is installed
		has_openpyxl = False
		try:
			import openpyxl
			has_openpyxl = True
		except ImportError as e:
			print(f"OpenPyXL import error: {e}")
			# Show warning to help debug why it's missing in the build
			messagebox.showwarning("Export Feature Limit", f"Excel (.xlsx) export is unavailable because the 'openpyxl' library could not be loaded.\n\nError: {e}\n\nFalling back to CSV format.")
		except Exception as e:
			print(f"OpenPyXL unexpected error: {e}")

		filetypes = []
		default_ext = ".csv"

		if has_openpyxl:
			filetypes.append(("Excel files", "*.xlsx"))
			default_ext = ".xlsx"

		filetypes.append(("CSV files", "*.csv"))
		filetypes.append(("All files", "*.*"))

		filepath = filedialog.asksaveasfilename(
			title="Export Results",
			defaultextension=default_ext,
			filetypes=filetypes
		)

		if not filepath:
			return

		if filepath.lower().endswith('.xlsx') and has_openpyxl:
			self._export_to_excel_openpyxl(filepath)
		else:
			self._export_to_csv(filepath)

	def _export_to_csv(self, filepath):
		try:
			# Use utf-8-sig for better Excel compatibility with non-ASCII characters
			with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
				writer = csv.writer(f)
				# Write header
				writer.writerow(["Test Case", "Result", "Log Folder"])

				# Write data from treeview
				for item_id in self.result_tree.get_children():
					values = self.result_tree.item(item_id, "values")
					writer.writerow(values)

			messagebox.showinfo("Success", f"Results exported to:\n{filepath}")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to export results: {e}")

	def _export_to_excel_openpyxl(self, filepath):
		try:
			import openpyxl
			from openpyxl.styles import PatternFill, Font, Alignment

			wb = openpyxl.Workbook()
			ws = wb.active
			ws.title = "Test Results"

			# Define Styles
			header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
			header_fill = PatternFill(start_color='5B9BD5', end_color='5B9BD5', fill_type='solid') # Blue

			pass_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid') # Light Green
			pass_font = Font(color='006100') # Dark Green

			fail_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid') # Light Red
			fail_font = Font(color='9C0006') # Dark Red

			center_align = Alignment(horizontal='center')
			bold_font = Font(bold=True)

			# Write Summary Statistics
			ws.append(["Summary:"])
			ws.cell(row=1, column=1).font = bold_font
			ws.append([f"PASS: {self.count_pass}"])
			ws.cell(row=2, column=1).font = bold_font
			ws.append([f"FAIL: {self.count_fail}"])
			ws.cell(row=3, column=1).font = bold_font
			ws.append([f"NT: {self.count_nt}"])
			ws.cell(row=4, column=1).font = bold_font
			ws.append([f"Not Support: {self.count_ns}"])
			ws.cell(row=5, column=1).font = bold_font

			# Calculate total based on current role filter
			current_role = self.result_role_filter.get()
			total_count = 0
			if current_role == "AP":
				total_count = len([name for name in self.xml_test_case_names if name.split('-', 1)[-1].startswith('4.')])
			elif current_role == "STA":
				total_count = len([name for name in self.xml_test_case_names if name.split('-', 1)[-1].startswith('5.')])
			else:
				total_count = len(self.xml_test_case_names)

			ws.append([f"Total Test Cases ({current_role}): {total_count}"])
			ws.cell(row=6, column=1).font = bold_font

			# Add a couple of empty rows for spacing
			ws.append([])
			ws.append([])

			# Write Header
			headers = ["Test Case", "Result", "Log Folder"]
			ws.append(headers)

			for cell in ws[1]:
				cell.font = header_font
				cell.fill = header_fill
				cell.alignment = center_align

			# Write Data
			for item_id in self.result_tree.get_children():
				values = self.result_tree.item(item_id, "values")
				test_case = values[0]
				result = values[1]
				log_folder = values[2]

				ws.append([test_case, result, log_folder])

				# Apply Styles to the last row added
				last_row = ws.max_row

				# Result column (B) styling
				result_cell = ws.cell(row=last_row, column=2)
				result_cell.alignment = center_align

				if result == "PASS":
					result_cell.fill = pass_fill
					result_cell.font = pass_font
				elif result in ["FAIL", "ERROR"]:
					result_cell.fill = fail_fill
					result_cell.font = fail_font

			# Feature: Freeze Top Row
			ws.freeze_panes = "A2"

			# Feature: Auto Filter
			ws.auto_filter.ref = ws.dimensions

			# Feature: Auto-adjust column widths
			for col in ws.columns:
				max_length = 0
				column = col[0].column_letter # Get the column name
				for cell in col:
					try:
						if len(str(cell.value)) > max_length:
							max_length = len(str(cell.value))
					except:
						pass
				adjusted_width = (max_length + 2) * 1.2
				ws.column_dimensions[column].width = min(adjusted_width, 100) # Cap width at 100

			wb.save(filepath)
			messagebox.showinfo("Success", f"Results exported to:\n{filepath}")

		except Exception as e:
			messagebox.showerror("Error", f"Failed to export results to Excel: {e}")

	def _on_result_view_toggle(self):
		# Refresh the tree view using the existing data in self.test_history_map
		# We need to reconstruct the target test cases list based on the role filter
		role = self.result_role_filter.get()
		target_test_cases = self.xml_test_case_names
		if role == "AP":
			target_test_cases = [name for name in target_test_cases if name.split('-', 1)[-1].startswith('4.')]
		elif role == "STA":
			target_test_cases = [name for name in target_test_cases if name.split('-', 1)[-1].startswith('5.')]

		self._populate_results_tree(target_test_cases)

	def _populate_results_tree(self, test_cases):
		# Clear existing items
		for item in self.result_tree.get_children():
			self.result_tree.delete(item)

		hide_nt = self.hide_nt_var.get()
		hide_ns = self.hide_ns_var.get()

		self.count_pass = 0
		self.count_fail = 0
		self.count_nt = 0
		self.count_ns = 0
		self.total_visible = 0

		for test_case in test_cases:
			history = self.test_history_map.get(test_case, [])

			result = "NT"
			folder = ""

			# Check if Not Support
			if test_case in self.not_support_list:
				result = "Not Support"
			elif history:
				latest = history[-1]
				result = latest['result']
				folder = latest['folder']

			if result == "PASS":
				self.count_pass += 1
			elif result == "Not Support":
				self.count_ns += 1
			elif result == "NT":
				self.count_nt += 1
			else:
				self.count_fail += 1 # FAIL or ERROR

			# Filtering logic
			if hide_nt and result == "NT":
				continue
			if hide_ns and result == "Not Support":
				continue

			values = (test_case, result, folder)

			self.result_tree.insert("", "end", values=values, tags=(result,))
			self.total_visible += 1

		# Update frame text with counts
		self.results_frame.config(text=f"Analysis Results (PASS: {self.count_pass}, FAIL: {self.count_fail}, NT: {self.count_nt}, NS: {self.count_ns}, Total: {len(test_cases)})")

	def _browse_config_file(self):
		filepath = filedialog.askopenfilename(
			title="Select AllInitConfig File",
			filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
		)
		if filepath:
			self.config_file_path.set(filepath)
			self._load_config_data()

	def _browse_xml_file(self):
		filepath = filedialog.askopenfilename(
			title="Select MasterTestInfo.xml File",
			filetypes=(("XML files", "*.xml"), ("All files", "*.*"))
		)
		if filepath:
			self.xml_file_path.set(filepath)
			self._load_xml_data() # Automatically load after selecting

	def _load_last_session(self):
		"""Loads the last opened file paths from the settings file."""
		if os.path.exists(self.settings_file):
			try:
				with open(self.settings_file, 'r', encoding='utf-8') as f:
					try:
						self.session_settings = json.load(f)
					except json.JSONDecodeError:
						# Handle old plain text format for backward compatibility
						f.seek(0)
						last_file = f.read().strip()
						if last_file and os.path.exists(last_file):
							self.config_file_path.set(last_file)
							self._load_config_data()
							self.session_settings = {'config_path': last_file}
			except Exception as e:
				print(f"Could not load last session settings: {e}")

		# Capture saved role filters and other settings BEFORE loading config/XML,
		# because loading XML resets filters and might trigger auto-save, which would overwrite them with defaults.
		saved_test_exec_role = self.session_settings.get('test_execution_role')
		saved_test_result_role = self.session_settings.get('test_result_role')
		saved_viewer_role = self.session_settings.get('viewer_role')

		config_path = self.session_settings.get('config_path')
		if config_path and os.path.exists(config_path):
			self.config_file_path.set(config_path)
			self._load_config_data()

		# Load cached editor for non-windows systems
		if os.name != 'nt':
			editor_cmd = self.session_settings.get('linux_editor_cmd')
			if editor_cmd:
				self.linux_editor_command = [editor_cmd]

		# Load saved date filters
		log_date = self.session_settings.get('log_filter_date')
		if log_date:
			self.log_filter_date.set(log_date)

		result_date = self.session_settings.get('result_filter_date')
		if result_date:
			self.result_filter_date.set(result_date)

		# Restore saved role filters
		if saved_test_exec_role:
			self.test_role_filter.set(saved_test_exec_role)

		# Restore Not Pass Only filter
		saved_not_pass_only = self.session_settings.get('filter_not_pass_only', False)
		self.filter_not_pass_only.set(saved_not_pass_only)

		# Restore Ignored Testbeds
		saved_ignored_testbeds = self.session_settings.get('ignored_testbeds', [])
		if saved_ignored_testbeds and self.all_testbeds:
			for tb in self.all_testbeds:
				if tb not in self.ignore_testbeds_vars:
					self.ignore_testbeds_vars[tb] = tk.BooleanVar(value=False)
				if tb in saved_ignored_testbeds:
					self.ignore_testbeds_vars[tb].set(True)

		# Restore Included Testbeds
		saved_included_testbeds = self.session_settings.get('included_testbeds', [])
		if saved_included_testbeds and self.all_testbeds:
			for tb in self.all_testbeds:
				if tb not in self.include_testbeds_vars:
					self.include_testbeds_vars[tb] = tk.BooleanVar(value=False)
				if tb in saved_included_testbeds:
					self.include_testbeds_vars[tb].set(True)

		# Force update display to filter the list based on the restored settings
		if saved_test_exec_role or saved_not_pass_only or saved_ignored_testbeds or saved_included_testbeds:
			self._update_test_execution_display()

		if saved_test_result_role:
			self.result_role_filter.set(saved_test_result_role)

		if saved_viewer_role:
			self.viewer_role_filter.set(saved_viewer_role)
			self._update_viewer_display()

		# Removed: Auto-analyze results on load as per user request. Analysis will only happen on button click.

	def _save_session(self):
		"""Saves file paths to the settings file."""
		if not self.app_initialized:
			return

		with open(self.settings_file, 'w', encoding='utf-8') as f:
			json.dump(self.session_settings, f, indent=4)

	def _load_config_data(self):
		filepath = self.config_file_path.get()
		if not os.path.exists(filepath):
			self.reload_button.config(state="disabled")
			messagebox.showerror("Error", f"File not found: {filepath}")
			return

		# Clear old data
		for item in self.config_tree.get_children():
			self.config_tree.delete(item)

		# Store original lines and parsed data
		self.config_data = []
		self.device_lines = {}

		# Read and parse the file
		with open(filepath, 'r', encoding='utf-8') as f:
			for i, line in enumerate(f):
				original_line = line.strip()
				key = ""
				value = ""
				tags = ("other",)

				# First, try to associate the line with a device regardless of whether it's a comment
				# This ensures commented-out devices are still found and categorized.
				temp_key = original_line.lstrip('#').strip() # Look at the line content without the comment marker
				device_name = None
				if temp_key.startswith("wfa_control_agent_"):
					device_name_candidate = temp_key.split('!')[0]
					device_name = device_name_candidate.split('wfa_control_agent_')[1]
					if device_name.endswith('_ap') or device_name.endswith('_sta'):
						if device_name not in self.device_lines: self.device_lines[device_name] = []
						self.device_lines[device_name].append(i)
					else:
						device_name = None # Not a valid device name

				self.config_data.append({'original': line, 'modified': line, 'type': 'other', 'device': device_name})

				# Handle comments and blank lines
				if not original_line or original_line.startswith('#'):
					key = original_line
					tags = ('comment',)
				else:
					# Handle define!$variable!value! format
					if original_line.startswith("define!") and original_line.count('!') >= 2:
						parts = original_line.split('!', 2)
						key = parts[1]
						value = parts[2].rstrip('!')
						tags = ('editable',)
						self.config_data[i]['type'] = 'define_kv_pair'
					# Handle standard key!value! format
					elif '!' in original_line:
						parts = original_line.split('!', 1)
						key = parts[0]
						value = parts[1].rstrip('!')
						tags = ('editable',)
						self.config_data[i]['type'] = 'kv_pair' if "ipaddr=" not in value else 'ip_port_pair'
					else:
						# Handle lines that don't fit the pattern
						key = original_line
						tags = ("other",)

				self.config_tree.insert("", "end", iid=i, values=(key, value), tags=tags)

		self._create_device_toggles()

		# Enable the reload button since a file was successfully loaded
		self.reload_button.config(state="normal")

		self.session_settings['config_path'] = filepath
		self._save_session()

		# Automatically load MasterTestInfo.xml from the same directory
		config_dir = os.path.dirname(filepath)
		xml_path = os.path.join(config_dir, 'MasterTestInfo.xml')
		self.xml_file_path.set(xml_path)
		self._load_xml_data()

	def _create_device_toggles(self):
		# Clear existing toggles
		for widget in self.ap_toggles_frame.winfo_children(): widget.destroy()
		for widget in self.sta_toggles_frame.winfo_children(): widget.destroy()

		ttk.Label(self.ap_toggles_frame, text="Testbed APs:").pack(side=tk.LEFT, padx=(0, 5))
		ttk.Label(self.sta_toggles_frame, text="Testbed STAs:").pack(side=tk.LEFT, padx=(0, 5))

		sorted_devices = sorted(self.device_lines.keys())

		for device_name in sorted_devices:
			frame = self.ap_toggles_frame if "_ap" in device_name else self.sta_toggles_frame
			var = tk.BooleanVar()
			# Check if the primary control agent line is commented out
			is_enabled = True
			for line_idx in self.device_lines.get(device_name, []):
				if f'wfa_control_agent_{device_name}!' in self.config_data[line_idx]['original']:
					if self.config_data[line_idx]['original'].strip().startswith('#'):
						is_enabled = False
						break
			var.set(is_enabled)
			cb = ttk.Checkbutton(frame, text=device_name, variable=var, command=lambda d=device_name, v=var: self._toggle_device(d, v))
			cb.pack(side=tk.LEFT, padx=2)

		self.ap_toggles_frame.pack(fill=tk.X, expand=True, pady=2)
		self.sta_toggles_frame.pack(fill=tk.X, expand=True, pady=2)

	def _is_testbed_enabled(self, testbed_name):
		"""
		Checks if a testbed is enabled in the configuration.
		A testbed is considered disabled if ANY of its associated devices (AP or STA) are disabled.
		"""
		if not hasattr(self, 'device_lines') or not self.device_lines:
			return True # Assume enabled if config not loaded or no devices found

		# Find related devices: {testbed_name}_ap or {testbed_name}_sta
		related_devices = []
		for device_name in self.device_lines.keys():
			if device_name == f"{testbed_name}_ap" or device_name == f"{testbed_name}_sta":
				related_devices.append(device_name)

		if not related_devices:
			return True # No matching devices found, assume enabled (or virtual)

		for device_name in related_devices:
			# Check if this device is enabled
			is_device_enabled = True
			for line_idx in self.device_lines.get(device_name, []):
				line_content = self.config_data[line_idx]['modified'] # Check modified content
				if f'wfa_control_agent_{device_name}!' in line_content:
					if line_content.strip().startswith('#'):
						is_device_enabled = False
						break

			if not is_device_enabled:
				return False # If any device is disabled, the testbed is disabled

		return True

	def _on_config_tree_double_click(self, event):
		# Identify the clicked region
		region = self.config_tree.identify("region", event.x, event.y)
		if region != "cell":
			return

		column = self.config_tree.identify_column(event.x)
		# We only want to edit the "Value" column, which is #2
		if column != "#2":
			return

		item_id = self.config_tree.identify_row(event.y)
		line_idx = int(item_id)
		line_type = self.config_data[line_idx].get('type')

		if line_type == "ip_port_pair":
			self._edit_ip_port_popup(item_id)
			return

		if line_type not in ["kv_pair", "define_kv_pair"]:
			return

		# Get the bounding box of the cell
		x, y, width, height = self.config_tree.bbox(item_id, column)

		# Create an entry widget over the cell
		entry = ttk.Entry(self.config_tree, width=width)
		entry.place(x=x, y=y, width=width, height=height)

		# Set the current value and focus
		current_value = self.config_tree.set(item_id, column)
		entry.insert(0, current_value)
		entry.focus_force()

		# Bind events to save or cancel the edit
		entry.bind("<Return>", lambda e: self._save_cell_edit(entry, item_id, column))
		entry.bind("<FocusOut>", lambda e: self._save_cell_edit(entry, item_id, column))
		entry.bind("<Escape>", lambda e: entry.destroy())

	def _save_cell_edit(self, entry, item_id, column):
		new_value = entry.get()
		self.config_tree.set(item_id, column, new_value)

		# Update the underlying data source so it can be saved
		line_idx = int(item_id)
		item_data = self.config_data[line_idx]
		key = self.config_tree.item(item_id, "values")[0]

		if item_data['type'] == 'define_kv_pair':
			# Format: define!$key!value!
			item_data['modified'] = f"define!{key}!{new_value}!\n"
		elif item_data['type'] == 'kv_pair':
			# Format: key!value!
			item_data['modified'] = f"{key}!{new_value}!\n"

		entry.destroy()

	def _edit_ip_port_popup(self, item_id):
		# Get the current key and value
		key, value_str = self.config_tree.item(item_id, "values")

		# Parse the IP and port from the value string
		ip_match = re.search(r"ipaddr=([^,]+)", value_str)
		port_match = re.search(r"port=([\d]+)", value_str)

		current_ip = ip_match.group(1) if ip_match else ""
		current_port = port_match.group(1) if port_match else ""

		# Create a popup window
		top = tk.Toplevel(self) #NOSONAR
		top.title(f"Edit: {key}")
		top.transient(self)
		# Wait for window to be visible before grabbing focus (fixes Linux issue)
		top.wait_visibility()
		top.grab_set()

		frame = ttk.Frame(top, padding="10")
		frame.pack(expand=True, fill="both")

		# IP Address field
		ttk.Label(frame, text="IP Address:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
		ip_var = tk.StringVar(value=current_ip)
		ttk.Entry(frame, textvariable=ip_var, width=40).grid(row=0, column=1, padx=5, pady=5)

		# Port field
		ttk.Label(frame, text="Port:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
		port_var = tk.StringVar(value=current_port)
		ttk.Entry(frame, textvariable=port_var, width=40).grid(row=1, column=1, padx=5, pady=5)

		def save_and_close():
			new_ip = ip_var.get()
			new_port = port_var.get()
			new_value_str = f"ipaddr={new_ip},port={new_port}"
			self.config_tree.set(item_id, "Value", new_value_str)

			# Update underlying data
			line_idx = int(item_id)
			item_data = self.config_data[line_idx]
			# ip_port_pair is essentially a kv_pair with specific value format
			item_data['modified'] = f"{key}!{new_value_str}!\n"

			top.destroy()

		save_button = ttk.Button(frame, text="Save", command=save_and_close)
		save_button.grid(row=2, column=0, columnspan=2, pady=10)

	def _toggle_device(self, device_name, var):
		is_enabled = var.get()
		line_indices = self.device_lines.get(device_name, [])

		for line_idx in line_indices:
			current_line = self.config_data[line_idx]['modified']

			# If enabling, remove '#' from the start.
			if is_enabled:
				if current_line.lstrip().startswith("#"):
					self.config_data[line_idx]['modified'] = current_line.lstrip()[1:]
			# If disabling, add '#' to the start, but only if it's not already a comment.
			else:
				if not current_line.lstrip().startswith("#"):
					self.config_data[line_idx]['modified'] = "#" + current_line

		# For simplicity, just reload the treeview from the modified data
		self._reload_treeview_from_config_data()

		# Update test execution display as filtering might change based on enabled devices
		self._update_test_execution_display()

	def _save_config_file(self):
		filepath = self.config_file_path.get()
		if not filepath:
			messagebox.showerror("Error", "No config file path specified.")
			return

		try:
			with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
				for child_id in self.config_tree.get_children():
					line_idx = int(child_id)
					f.write(self.config_data[line_idx]['modified'])

			messagebox.showinfo("Success", f"File saved successfully to:\n{filepath}")
			# Reload data to reflect saved state
			self._load_config_data()
		except Exception as e:
			messagebox.showerror("Save Failed", f"An error occurred while saving the file: {e}")

	def _reload_treeview_from_config_data(self):
		# This helper function re-parses and re-displays the data in self.config_data
		# This is useful after a toggle operation to update the view.
		for item in self.config_tree.get_children():
			self.config_tree.delete(item)

		for i, data in enumerate(self.config_data):
			original_line = data['modified'].strip() # Use modified line
			line_type = data.get('type', 'other')
			key = ""
			value = ""
			tags = ()

			if not original_line or original_line.startswith('#'):
				key = original_line
				tags = ("comment",)
			else:
				if line_type == 'define_kv_pair':
					parts = original_line.split('!', 2)
					key = parts[1]
					value = parts[2].rstrip('!')
					tags = ('editable',)
				elif line_type in ['kv_pair', 'ip_port_pair']:
					parts = original_line.split('!', 1)
					key = parts[0]
					value = parts[1].rstrip('!')
					tags = ('editable',)
				else:
					key = original_line
					tags = ("other",)

			self.config_tree.insert("", "end", iid=i, values=(key, value), tags=tags)

	def _load_xml_data(self):
		filepath = self.xml_file_path.get()
		if not os.path.exists(filepath):
			messagebox.showerror("Error", f"File not found: {filepath}")
			return

		# Clear old data
		self.test_case_listbox.delete(0, tk.END)
		for item in self.xml_tree.get_children():
			self.xml_tree.delete(item)
		self.xml_test_cases.clear()
		self.xml_test_case_names.clear()

		# NOTE: Do not reset filters here (search_term, viewer_role_filter) as they might be preserved.

		# Parse XML
		try:
			# Use 'with open' to ensure proper file handling and encoding
			with open(filepath, 'r', encoding='utf-8') as f:
				tree = ET.parse(f)
				root = tree.getroot()

				# The direct children of the root are the test cases, with the tag being the name.
				for test_case_element in root:
					name = test_case_element.tag
					if name: # Ensure the tag is not empty
						self.xml_test_cases[name] = test_case_element

				# Extract all unique testbeds
				unique_testbeds = set()
				for element in self.xml_test_cases.values():
					tb_list_elem = element.find('TB_LIST')
					if tb_list_elem is not None and tb_list_elem.text:
						# Assuming comma-separated
						tbs = [tb.strip() for tb in tb_list_elem.text.split(',')]
						unique_testbeds.update(tbs)
				self.all_testbeds = sorted(list(unique_testbeds))

				self.xml_test_case_names = sorted(self.xml_test_cases.keys())

				# Refresh displays with loaded data and current filters
				self._update_test_case_listbox(self.xml_test_case_names)
				self._update_viewer_display()
				self._update_test_execution_display()

				self.session_settings['xml_path'] = filepath
				self._save_session()

		except (ET.ParseError, IOError) as e:
			messagebox.showerror("XML Parse Error", f"Could not parse XML file: {e}")

	def _update_test_case_listbox(self, names):
		self.test_case_listbox.delete(0, tk.END)
		for name in names:
			self.test_case_listbox.insert(tk.END, name)

	def _populate_test_execution_list(self, test_names):
		# Clear old checkbuttons
		for widget in self.test_checkbutton_frame.winfo_children():
			widget.destroy()
		self.test_checkbuttons.clear()

		# Create new checkbuttons
		for name in test_names:
			var = tk.BooleanVar(value=False)
			cb = ttk.Checkbutton(self.test_checkbutton_frame, text=name, variable=var, command=self._update_selection_count)
			cb.pack(anchor=tk.W, fill=tk.X)
			self.test_checkbuttons[name] = var

		self._update_selection_count()

	def _on_test_case_select(self, event):
		# Clear previous details
		for item in self.xml_tree.get_children():
			self.xml_tree.delete(item)

		selection_indices = self.test_case_listbox.curselection()
		if not selection_indices:
			return

		selected_name = self.test_case_listbox.get(selection_indices[0])
		test_case_element = self.xml_test_cases.get(selected_name)

		if test_case_element is not None:
			# Populate the tree with the children of the selected test case element
			self._populate_detail_as_table(test_case_element)

	def _populate_detail_as_table(self, element):
		"""Recursively populates the xml_tree with key-value pairs."""
		def recurse(el, prefix=""):
			# If the element has children, recurse
			if len(list(el)) > 0:
				for child in el:
					new_prefix = f"{prefix}{el.tag}." if prefix else f"{el.tag}."
					recurse(child, new_prefix)
			# If the element has text, it's a leaf node
			elif el.text and el.text.strip():
				key = f"{prefix}{el.tag}"
				self.xml_tree.insert("", "end", values=(key, el.text.strip()))

		for child_element in element:
			recurse(child_element)

	def _toggle_expand_all(self, expand=True):
		for item in self.xml_tree.get_children():
			self._toggle_item_expand(item, expand)

	def _toggle_item_expand(self, item, expand=True):
		self.xml_tree.item(item, open=expand)
		for child in self.xml_tree.get_children(item):
			self._toggle_item_expand(child, expand)

	def _check_environment(self):
		"""Checks if the script is running in the correct WTS directory structure."""
		try:
			# Determine the base directory differently if running as a bundled executable
			if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
				# Running in a PyInstaller bundle
				bin_dir = os.path.dirname(sys.executable)
			else:
				# Running as a normal .py script
				bin_dir = os.path.dirname(os.path.abspath(__file__))

			return os.path.basename(bin_dir) == 'bin' and os.path.exists(self.wts_executable_path)
		except Exception as e:
			print(f"Environment check failed: {e}")
			return False

	def _select_all_tests(self):
		# This should only select all VISIBLE tests
		for name, var in self.test_checkbuttons.items():
			var.set(True)
		self._update_selection_count()

	def _deselect_all_tests(self):
		for var in self.test_checkbuttons.values():
			var.set(False)
		self._update_selection_count()

	def _reset_and_populate_execution_list(self):
		self.test_role_filter.set("All")
		self.test_execution_search_term.set("")
		self._populate_test_execution_list(self.xml_test_case_names)

	def _update_test_execution_display(self, *args):
		# Save current role filter
		self.session_settings['test_execution_role'] = self.test_role_filter.get()
		# Also save the new filter_not_pass_only state
		self.session_settings['filter_not_pass_only'] = self.filter_not_pass_only.get()

		# Get currently ignored testbeds from UI (Advanced Options)
		user_ignored_testbeds = [tb for tb, var in self.ignore_testbeds_vars.items() if var.get()]

		# Get currently included testbeds from UI
		user_included_testbeds = [tb for tb, var in self.include_testbeds_vars.items() if var.get()]

		# Add testbeds that are disabled in Config
		disabled_testbeds = []
		if self.all_testbeds:
			for tb in self.all_testbeds:
				if not self._is_testbed_enabled(tb):
					disabled_testbeds.append(tb)

		# Combine lists (set for uniqueness)
		effective_ignored_testbeds = list(set(user_ignored_testbeds + disabled_testbeds))

		# Save ONLY the user's explicit choices to session
		self.session_settings['ignored_testbeds'] = user_ignored_testbeds
		self.session_settings['included_testbeds'] = user_included_testbeds

		self._save_session()

		role = self.test_role_filter.get()
		search_term = self.test_execution_search_term.get().lower()

		filtered_names = self.xml_test_case_names

		if role == "AP":
			filtered_names = [name for name in filtered_names if name.split('-', 1)[-1].startswith('4.')]
		elif role == "STA":
			filtered_names = [name for name in filtered_names if name.split('-', 1)[-1].startswith('5.')]

		# Filter out Not Support items
		if self.not_support_list:
			filtered_names = [name for name in filtered_names if name not in self.not_support_list]

		if search_term:
			filtered_names = [name for name in filtered_names if search_term in name.lower()]
		# Apply "Show Cases include testbeds" Filter (Include Logic)
		if user_included_testbeds:
			temp_filtered = []
			for name in filtered_names:
				element = self.xml_test_cases.get(name)
				should_include = False
				if element is not None:
					tb_list_elem = element.find('TB_LIST')
					if tb_list_elem is not None and tb_list_elem.text:
						case_tbs = [tb.strip() for tb in tb_list_elem.text.split(',')]
						# If ANY of the case's testbeds are in the included list, include it
						for tb in case_tbs:
							if tb in user_included_testbeds:
								should_include = True
								break
				if should_include:
					temp_filtered.append(name)
			filtered_names = temp_filtered

		# Apply Ignored Testbeds Filter (Exclude Logic)
		if effective_ignored_testbeds:
			temp_filtered = []
			for name in filtered_names:
				element = self.xml_test_cases.get(name)
				should_exclude = False
				if element is not None:
					tb_list_elem = element.find('TB_LIST')
					if tb_list_elem is not None and tb_list_elem.text:
						case_tbs = [tb.strip() for tb in tb_list_elem.text.split(',')]
						# If ANY of the case's testbeds are in the ignored list, exclude it
						for tb in case_tbs:
							if tb in effective_ignored_testbeds:
								should_exclude = True
								break
				if not should_exclude:
					temp_filtered.append(name)
			filtered_names = temp_filtered

		# Apply "Not Pass (FAIL/NT) Cases Only" filter
		if self.filter_not_pass_only.get():
			if not hasattr(self, 'test_history_map') or not self.test_history_map:
				messagebox.showinfo("Info", "Cannot apply 'Not Pass' filter: No analysis results found. Please go to 'Test Result' tab and click 'Analyze Result'.")
				self.filter_not_pass_only.set(False) # Turn off filter if no data
			else:
				# Filter to include only "Not Pass" cases
				not_pass_filtered_names = []
				for name in filtered_names: # Iterate over already role/search filtered names
					history = self.test_history_map.get(name, [])

					is_not_pass = False
					if not history: # NT case
						is_not_pass = True
					else:
						latest_result = history[-1]['result']
						if latest_result != "PASS": # FAIL or ERROR
							is_not_pass = True

					if is_not_pass:
						not_pass_filtered_names.append(name)
				filtered_names = not_pass_filtered_names

		self._populate_test_execution_list(filtered_names)

	def _update_viewer_display(self, *args):
		self.session_settings['viewer_role'] = self.viewer_role_filter.get()
		self._save_session()

		role = self.viewer_role_filter.get()
		search_term = self.xml_search_term.get().lower()

		filtered_names = self.xml_test_case_names

		if role == "AP":
			filtered_names = [name for name in filtered_names if name.split('-', 1)[-1].startswith('4.')]
		elif role == "STA":
			filtered_names = [name for name in filtered_names if name.split('-', 1)[-1].startswith('5.')]

		if search_term:
			filtered_names = [name for name in filtered_names if search_term in name.lower()]

		self._update_test_case_listbox(filtered_names)

	def _select_all_tests(self):
		for var in self.test_checkbuttons.values():
			var.set(True)

	def _deselect_all_tests(self):
		for var in self.test_checkbuttons.values():
			var.set(False)

	def _show_advanced_options_popup(self):
		top = tk.Toplevel(self)
		top.title("Advanced Options")
		top.geometry("600x500")

		# Make it modal
		top.transient(self)
		top.grab_set()

		main_frame = ttk.Frame(top, padding="10")
		main_frame.pack(fill=tk.BOTH, expand=True)

		# --- Filter Options ---
		filter_frame = ttk.LabelFrame(main_frame, text="Filter Options", padding="10")
		filter_frame.pack(fill=tk.X, pady=(0, 10))

		# New Checkbutton for "Not Pass (FAIL/NT) Cases Only"
		# Command will be _update_test_execution_display
		ttk.Checkbutton(filter_frame, text="Not Pass (FAIL/NT) Cases Only", variable=self.filter_not_pass_only, command=self._update_test_execution_display).pack(fill=tk.X, pady=5)

		# --- Testbed Filters (Split View) ---
		paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
		paned_window.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

		# Left: Include Testbeds
		include_frame = ttk.LabelFrame(paned_window, text="Show Cases include testbeds", padding="10")
		paned_window.add(include_frame, weight=1)

		# Right: Ignore Testbeds
		ignore_frame = ttk.LabelFrame(paned_window, text="Ignore Cases with selected testbeds", padding="10")
		paned_window.add(ignore_frame, weight=1)

		if not self.all_testbeds:
			ttk.Label(include_frame, text="No testbeds found (Load XML first)").pack()
			ttk.Label(ignore_frame, text="No testbeds found (Load XML first)").pack()
		else:
			# --- Include List ---
			canvas_inc = tk.Canvas(include_frame)
			scrollbar_inc = ttk.Scrollbar(include_frame, orient="vertical", command=canvas_inc.yview)
			scrollable_frame_inc = ttk.Frame(canvas_inc)

			scrollable_frame_inc.bind(
				"<Configure>",
				lambda e: canvas_inc.configure(scrollregion=canvas_inc.bbox("all"))
			)
			canvas_inc.create_window((0, 0), window=scrollable_frame_inc, anchor="nw")
			canvas_inc.configure(yscrollcommand=scrollbar_inc.set)

			canvas_inc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
			scrollbar_inc.pack(side=tk.RIGHT, fill="y")

			for tb in self.all_testbeds:
				if tb not in self.include_testbeds_vars:
					self.include_testbeds_vars[tb] = tk.BooleanVar(value=False)

				cb = ttk.Checkbutton(scrollable_frame_inc, text=tb, variable=self.include_testbeds_vars[tb], command=self._update_test_execution_display)
				cb.pack(anchor="w", fill=tk.X)

			# --- Ignore List ---
			canvas_ign = tk.Canvas(ignore_frame)
			scrollbar_ign = ttk.Scrollbar(ignore_frame, orient="vertical", command=canvas_ign.yview)
			scrollable_frame_ign = ttk.Frame(canvas_ign)

			scrollable_frame_ign.bind(
				"<Configure>",
				lambda e: canvas_ign.configure(scrollregion=canvas_ign.bbox("all"))
			)
			canvas_ign.create_window((0, 0), window=scrollable_frame_ign, anchor="nw")
			canvas_ign.configure(yscrollcommand=scrollbar_ign.set)

			canvas_ign.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
			scrollbar_ign.pack(side=tk.RIGHT, fill="y")

			for tb in self.all_testbeds:
				if tb not in self.ignore_testbeds_vars:
					self.ignore_testbeds_vars[tb] = tk.BooleanVar(value=False)

				is_enabled = self._is_testbed_enabled(tb)
				text_label = tb
				state = "normal"

				if not is_enabled:
					self.ignore_testbeds_vars[tb].set(True)
					text_label += " (Testbed not enabled)"
					state = "disabled"

				cb = ttk.Checkbutton(scrollable_frame_ign, text=text_label, variable=self.ignore_testbeds_vars[tb], command=self._update_test_execution_display, state=state)
				cb.pack(anchor="w", fill=tk.X)

		ttk.Button(main_frame, text="Close", command=top.destroy).pack(side=tk.BOTTOM, pady=5)

	def _check_not_support_file(self):
		# Check saved path first, then default
		path_to_check = self.session_settings.get('not_support_path', self.not_support_default_path)

		if os.path.exists(path_to_check):
			if messagebox.askyesno("Import Not Support Config", f"Found 'Not Support' configuration file:\n{path_to_check}\n\nDo you want to import it?"):
				self._load_not_support_data(path_to_check)

	def _load_not_support_data(self, filepath):
		try:
			with open(filepath, 'r', encoding='utf-8') as f:
				data = json.load(f)
				if isinstance(data, list):
					self.not_support_list = set(data)
					messagebox.showinfo("Success", f"Imported {len(self.not_support_list)} items from:\n{filepath}")
					self._update_test_execution_display()

					# Save path to session
					self.session_settings['not_support_path'] = filepath
					self._save_session()
				else:
					messagebox.showerror("Error", "Invalid file format. Expected a JSON list.")
		except Exception as e:
			messagebox.showerror("Error", f"Failed to load file: {e}")

	def _save_not_support_data(self, filepath, data_list):
		try:
			with open(filepath, 'w', encoding='utf-8') as f:
				json.dump(data_list, f, indent=4)
			messagebox.showinfo("Success", f"Saved {len(data_list)} items to:\n{filepath}")

			# Save path to session
			self.session_settings['not_support_path'] = filepath
			self._save_session()
		except Exception as e:
			messagebox.showerror("Error", f"Failed to save file: {e}")

	def _show_not_support_config_window(self):
		top = tk.Toplevel(self)
		top.title("Not Support Configuration")
		top.geometry("800x600")
		top.transient(self)
		top.grab_set()

		# --- Top Frame: Actions ---
		action_frame = ttk.Frame(top, padding="10")
		action_frame.pack(fill=tk.X)

		def import_file():
			filepath = filedialog.askopenfilename(title="Import Not Support Config", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
			if filepath:
				self._load_not_support_data(filepath)
				refresh_list()

		def save_file():
			# Gather checked items
			current_not_support = []
			for name, var in self.ns_vars.items():
				if var.get():
					current_not_support.append(name)

			filepath = filedialog.asksaveasfilename(title="Save Not Support Config", initialfile=self.not_support_file_name, defaultextension=".json", filetypes=[("JSON files", "*.json")])
			if filepath:
				self._save_not_support_data(filepath, current_not_support)
				# Update internal list
				self.not_support_list = set(current_not_support)
				self._update_test_execution_display()

		ttk.Button(action_frame, text="Import...", command=import_file).pack(side=tk.LEFT, padx=(0, 5))
		ttk.Button(action_frame, text="Save...", command=save_file).pack(side=tk.LEFT)

		# --- Middle Frame: List ---
		list_frame = ttk.LabelFrame(top, text="Select Test Cases to Mark as 'Not Support'", padding="10")
		list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

		# Scrollable canvas
		canvas = tk.Canvas(list_frame)
		scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
		scrollable_frame = ttk.Frame(canvas)

		scrollable_frame.bind(
			"<Configure>",
			lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
		)
		canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
		canvas.configure(yscrollcommand=scrollbar.set)

		canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		scrollbar.pack(side=tk.RIGHT, fill="y")

		# Mousewheel support for this specific window
		def _on_mousewheel(event):
			canvas.yview_scroll(int(-1*(event.delta/120)), "units")

		if os.name == 'nt':
			canvas.bind_all("<MouseWheel>", _on_mousewheel)
			top.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>")) # Clean up? Actually bind_all is global... might interfere.
			# Better: bind to the canvas or frame and focus

		self.ns_vars = {}

		def refresh_list():
			for widget in scrollable_frame.winfo_children():
				widget.destroy()
			self.ns_vars.clear()

			# Load ALL test cases from XML
			all_tests = self.xml_test_case_names
			if not all_tests:
				ttk.Label(scrollable_frame, text="No test cases loaded.").pack()
				return

			for name in all_tests:
				var = tk.BooleanVar(value=(name in self.not_support_list))
				cb = ttk.Checkbutton(scrollable_frame, text=name, variable=var)
				cb.pack(anchor="w", fill=tk.X)
				self.ns_vars[name] = var

		refresh_list()

		# --- Bottom Frame: Selection Control ---
		bottom_frame = ttk.Frame(top, padding="10")
		bottom_frame.pack(fill=tk.X)

		def select_all():
			for var in self.ns_vars.values(): var.set(True)

		def deselect_all():
			for var in self.ns_vars.values(): var.set(False)

		def apply_changes():
			# Update internal list without saving to file
			current_not_support = []
			for name, var in self.ns_vars.items():
				if var.get():
					current_not_support.append(name)
			self.not_support_list = set(current_not_support)
			self._update_test_execution_display()
			top.destroy()

		ttk.Button(bottom_frame, text="Select All", command=select_all).pack(side=tk.LEFT, padx=(0, 5))
		ttk.Button(bottom_frame, text="Deselect All", command=deselect_all).pack(side=tk.LEFT)
		ttk.Button(bottom_frame, text="Apply & Close", command=apply_changes).pack(side=tk.RIGHT)


	def _write_to_terminal(self, message):
		self.terminal_output.config(state=tk.NORMAL)

		tag_to_apply = None
		if "PASS" in message:
			tag_to_apply = "pass"
		elif "FAIL" in message:
			tag_to_apply = "fail"
		elif "--- Execution" in message: # Color the start/finish/cancel messages
			tag_to_apply = "info"

		self.terminal_output.insert(tk.END, message, tag_to_apply)
		self.terminal_output.see(tk.END)
		self.terminal_output.config(state=tk.DISABLED)

	def _run_command_thread(self, command):
		# If on Windows and using WSL, prepend 'wsl.exe'
		if os.name == 'nt' and self.use_wsl:
			command = ["wsl.exe"] + command
		try:
			self.current_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
			for line in iter(self.current_process.stdout.readline, ''):
				self.after(0, self._write_to_terminal, line)
			self.current_process.stdout.close()
			self.current_process.wait()
		except FileNotFoundError:
			self.after(0, self._write_to_terminal, f"Error: Command '{command[0]}' not found. Make sure 'wts' is in your system's PATH.\n")
		except Exception as e:
			# Avoid error messages if the process was intentionally killed (which might close the pipe)
			if self.current_process:
				self.after(0, self._write_to_terminal, f"An error occurred: {e}\n")
		finally:
			self.current_process = None
			self.after(0, self._write_to_terminal, "\n--- Execution Finished ---\n")

	def _stop_tests(self):
		if self.current_process:
			try:
				self.current_process.terminate()
				self._write_to_terminal("\n\n!!! Stopping Process Requested !!!\n")
				# wait a bit and kill if necessary? For now terminate is usually enough.
			except Exception as e:
				print(f"Error stopping process: {e}")
		else:
			self._write_to_terminal("\nNo active process to stop.\n")

	def _on_closing(self):
		if self.current_process:
			if messagebox.askokcancel("Quit", "A test is currently running. Do you want to stop it and exit?"):
				self._stop_tests()
				self.destroy()
		else:
			self.destroy()

	def _run_tests(self):
		selected_tests = [name for name, var in self.test_checkbuttons.items() if var.get()]

		if not selected_tests:
			messagebox.showwarning("No Tests Selected", "Please select at least one test case to run.")
			return

		# Clear terminal
		self.terminal_output.config(state=tk.NORMAL)
		self.terminal_output.delete(1.0, tk.END)
		self.terminal_output.config(state=tk.DISABLED)

		# Determine program from XML path
		xml_path = self.xml_file_path.get()
		if not xml_path:
			messagebox.showerror("Error", "MasterTestInfo.xml path is not set.")
			return

		program = "EHT" # Default
		try:
			# e.g., d:\code\...\cmds\WTS-EHT\MasterTestInfo.xml -> WTS-EHT
			program_part = os.path.basename(os.path.dirname(xml_path))
			if program_part.startswith("WTS-"):
				program = program_part.split('-', 1)[1]
		except Exception as e:
			self._write_to_terminal(f"Could not determine program from path, using default '{program}'. Error: {e}\n")

		command = []
		command_preview_str = ""
		group_file_path = "wts_group_test.txt"

		if len(selected_tests) == 1:
			# Single test
			test_case = selected_tests[0]
			command = [self.wts_executable_path, program, test_case]
			command_preview_str = f"Running single test: {' '.join(command)}"
		else:
			# Group test
			try:
				with open(group_file_path, 'w') as f:
					for test_case in selected_tests:
						f.write(f"{test_case}\n")
				command = [self.wts_executable_path, "-p", program, "-g", group_file_path]
				command_preview_str = f"Running group test with {len(selected_tests)} cases: {' '.join(command)}"
			except Exception as e:
				messagebox.showerror("File Error", f"Could not create group test file: {e}")
				return

		# Show confirmation dialog before running
		if command:
			confirm_message = f"The following command will be executed:\n\n{command_preview_str}\n\nDo you want to proceed?"
			if messagebox.askokcancel("Confirm Execution", confirm_message):
				self._write_to_terminal(command_preview_str + "\n\n")
				threading.Thread(target=self._run_command_thread, args=(command,), daemon=True).start()
			else:
				self._write_to_terminal("--- Execution Canceled by User ---\n")

	def _load_tms_data(self):
		"""Loads and parses the TmsClient.conf file."""
		# Clear old data
		for item in self.tms_tree.get_children():
			self.tms_tree.delete(item)
		self.tms_data.clear()

		if not os.path.exists(self.tms_client_conf_path):
			messagebox.showerror("File Not Found", f"TmsClient.conf not found at:\n{self.tms_client_conf_path}")
			return

		try:
			with open(self.tms_client_conf_path, 'r', encoding='utf-8') as f:
				for i, line in enumerate(f):
					stripped_line = line.strip()
					key, value = "", ""
					line_type = "comment"
					tags = ('comment',)

					if stripped_line and not stripped_line.startswith('#'):
						if '=' in stripped_line:
							parts = stripped_line.split('=', 1)
							key = parts[0].strip()
							value = parts[1].strip()
							line_type = "kv_pair"
							tags = ('editable',)
						else:
							key = stripped_line
							line_type = "other"
					else:
						key = stripped_line

					self.tms_data.append({'original': line, 'key': key, 'value': value, 'type': line_type})
					self.tms_tree.insert("", "end", iid=i, values=(key, value), tags=tags)
		except Exception as e:
			messagebox.showerror("Error", f"Failed to load TmsClient.conf: {e}")
		# Sync checkbox state after loading
		self._sync_tms_checkbox()

	def _sync_tms_checkbox(self):
		try:
			for item_data in self.tms_data:
				if item_data['key'] == 'TMS_feature':
					is_enabled = item_data['value'].lower() == 'enabled'
					self.upload_to_tms_var.set(is_enabled)
					return
		except Exception as e:
			print(f"Could not sync TMS checkbox: {e}")


	def _on_tms_tree_double_click(self, event):

		region = self.tms_tree.identify("region", event.x, event.y)
		if region != "cell":
			return

		column = self.tms_tree.identify_column(event.x)
		if column != "#2": # Only edit "Value" column
			return

		item_id = self.tms_tree.identify_row(event.y)
		line_idx = int(item_id)

		item_data = self.tms_data[line_idx]

		# Prevent editing for items controlled by the checkbox
		if item_data['type'] != "kv_pair" or item_data['key'] in ['TMS_feature', 'FTP_feature']:
			return

		current_value = item_data['value']

		# Get the bounding box of the cell
		x, y, width, height = self.tms_tree.bbox(item_id, column)

		# Use Combobox for Enabled/Disabled, otherwise use Entry
		if current_value.lower() in ["enabled", "disabled"]:
			editor = ttk.Combobox(self.tms_tree, values=["Enabled", "Disabled"], state="readonly")
			editor.set(current_value)
		else:
			editor = ttk.Entry(self.tms_tree, width=width)
			editor.insert(0, current_value)

		editor.place(x=x, y=y, width=width, height=height)
		editor.focus_force()

		editor.bind("<Return>", lambda e: self._save_tms_cell_edit(editor, item_id, column))
		editor.bind("<FocusOut>", lambda e: self._save_tms_cell_edit(editor, item_id, column))
		editor.bind("<Escape>", lambda e: editor.destroy())

	def _save_tms_cell_edit(self, editor, item_id, column):
		new_value = editor.get()
		line_idx = int(item_id)

		# Update data model
		self.tms_data[line_idx]['value'] = new_value
		# Update Treeview
		self.tms_tree.set(item_id, column, new_value)

		editor.destroy()

	def _save_tms_file(self):
		if not os.path.exists(self.tms_client_conf_path):
			messagebox.showerror("Error", "File path for TmsClient.conf is not valid.")
			return

		try:
			with open(self.tms_client_conf_path, 'w', encoding='utf-8', newline='\n') as f:
				for item_data in self.tms_data:
					if item_data['type'] == 'kv_pair':
						# Reconstruct the line from the potentially modified value
						f.write(f"{item_data['key']}={item_data['value']}\n")
					else:
						# Write back the original line for comments, blank lines, etc.
						f.write(item_data['original'])

			messagebox.showinfo("Success", f"File saved successfully to:\n{self.tms_client_conf_path}")
			# Reload data to reflect saved state
			self._load_tms_data()
		except Exception as e:
			messagebox.showerror("Save Failed", f"An error occurred while saving the file: {e}")

	def _on_tms_upload_toggle(self):
		"""Handles the 'Upload To TMS' checkbox toggle."""
		is_enabled = self.upload_to_tms_var.get()
		new_value = "Enabled" if is_enabled else "Disabled"
		keys_to_update = ['TMS_feature', 'FTP_feature']

		for i, item_data in enumerate(self.tms_data):
			if item_data['key'] in keys_to_update:
				# Update data model
				self.tms_data[i]['value'] = new_value
				# Update Treeview
				self.tms_tree.set(str(i), "Value", new_value)

	def _load_log_folders(self, *args):
		"""Scans and displays log folders, applying date filter if specified."""
		# Save current filter date
		self.session_settings['log_filter_date'] = self.log_filter_date.get()
		self._save_session()

		for item in self.log_folder_tree.get_children():
			self.log_folder_tree.delete(item)

		if not os.path.isdir(self.log_dir_path):
			# Create log dir if it doesn't exist
			try:
				os.makedirs(self.log_dir_path)
			except OSError as e:
				print(f"Could not create log directory: {e}")
				return

		filter_date = None
		try:
			if self.log_filter_date.get():
				filter_date = datetime.strptime(self.log_filter_date.get(), "%Y-%m-%d").date()
		except ValueError:
			messagebox.showwarning("Invalid Date", "Please use YYYY-MM-DD format for the date filter.")
			return

		try:
			# Get all directories and sort them by modification time, newest first
			all_dirs = [d for d in os.listdir(self.log_dir_path) if os.path.isdir(os.path.join(self.log_dir_path, d))]
			all_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(self.log_dir_path, d)), reverse=True)

			for folder_name in all_dirs:
				try:
					# Use regex to reliably find the date string (e.g., Dec-04-2025)
					date_match = re.search(r'([A-Za-z]{3}-\d{2}-\d{4})', folder_name)
					if not date_match:
						raise ValueError("Date not found in folder name")
					folder_date = datetime.strptime(date_match.group(1), "%b-%d-%Y").date()

					if filter_date and folder_date < filter_date:
						continue # Skip folders that are older than the filter date

					self.log_folder_tree.insert("", "end", text=folder_name)
				except (IndexError, ValueError):
					# If folder name doesn't match the expected format, still show it but don't filter
					if not filter_date:
						self.log_folder_tree.insert("", "end", text=folder_name)
		except Exception as e:
			messagebox.showerror("Error", f"Failed to read log directory: {e}")

	def _on_log_folder_right_click(self, event):
		item_id = self.log_folder_tree.identify_row(event.y)
		if not item_id:
			return

		# Check if the right-clicked item is already in the selection.
		# If it is, we keep the current selection (allowing multi-select actions).
		# If it's not, we select it (standard behavior).
		selection = self.log_folder_tree.selection()
		if item_id not in selection:
			self.log_folder_tree.selection_set(item_id)
			selection = (item_id,)

		folder_names = [self.log_folder_tree.item(sid, "text") for sid in selection]

		menu = tk.Menu(self.log_folder_tree, tearoff=0)
		if len(folder_names) > 1:
			menu.add_command(label=f"Zip and Save {len(folder_names)} Folders...", command=lambda: self._zip_multiple_logs(folder_names))
		else:
			menu.add_command(label="Zip and Save As...", command=lambda: self._zip_and_save_log(folder_names[0]))

		menu.post(event.x_root, event.y_root)

	def _zip_multiple_logs(self, folder_names):
		target_dir = filedialog.askdirectory(title="Select Destination Directory")
		if not target_dir:
			return

		success_count = 0
		errors = []

		for folder_name in folder_names:
			source_path = os.path.join(self.log_dir_path, folder_name)
			if not os.path.exists(source_path):
				errors.append(f"{folder_name}: Not found")
				continue

			try:
				# Output file: target_dir/folder_name.zip
				# make_archive base_name should not include extension if format is specified
				base_name = os.path.join(target_dir, folder_name)
				shutil.make_archive(base_name, 'zip', root_dir=self.log_dir_path, base_dir=folder_name)
				success_count += 1
			except Exception as e:
				errors.append(f"{folder_name}: {e}")

		msg = f"Successfully zipped {success_count} logs to:\n{target_dir}"
		if errors:
			msg += "\n\nErrors:\n" + "\n".join(errors)
			if success_count == 0:
				messagebox.showerror("Error", msg)
			else:
				messagebox.showwarning("Partial Success", msg)
		else:
			messagebox.showinfo("Success", msg)

	def _on_log_folder_select(self, event):
		for item in self.log_file_tree.get_children():
			self.log_file_tree.delete(item)

		selected_item = self.log_folder_tree.focus()
		if not selected_item:
			return

		folder_name = self.log_folder_tree.item(selected_item, "text")
		folder_path = os.path.join(self.log_dir_path, folder_name)

		for filename in sorted(os.listdir(folder_path)):
			if filename.endswith(".log") or filename.endswith(".pcapng.gz"):
				file_path = os.path.join(folder_path, filename)
				size_bytes = os.path.getsize(file_path)
				size_kb = f"{size_bytes / 1024:.1f} KB"
				self.log_file_tree.insert("", "end", values=(filename, size_kb))

	def _open_log_file(self, event):
		selected_item = self.log_file_tree.focus()
		if not selected_item:
			return

		filename = self.log_file_tree.item(selected_item, "values")[0]
		selected_folder = self.log_folder_tree.item(self.log_folder_tree.focus(), "text")
		file_path = os.path.join(self.log_dir_path, selected_folder, filename)

		try:
			if filename.endswith(".pcapng.gz"):
				subprocess.Popen(['wireshark', file_path]) #NOSONAR
			elif os.name == 'nt': # For any file on Windows
				os.startfile(file_path)
			elif filename.endswith(".log"): # For macOS and Linux .log files. Use cached editor.
				if self.linux_editor_command:
					subprocess.Popen(self.linux_editor_command + [file_path]) #NOSONAR
				else:
					# This is a fallback in case the editor was not found at startup.
					messagebox.showerror("Program Not Found", "Could not find a default text editor. Please check your system's configuration (e.g., xdg-open, $EDITOR) or install a common editor like gedit, kate, or mousepad.")
		except FileNotFoundError:
			messagebox.showerror("Program Not Found", f"Could not find the required program (e.g., Wireshark or default editor) in your system's PATH.")
		except Exception as e:
			messagebox.showerror("Error", f"Could not open file: {e}")

	def _find_and_cache_text_editor(self):
		"""On first run on Linux/macOS, find a suitable text editor and cache it."""
		if os.name == 'nt' or self.linux_editor_command:
			# Do nothing on Windows or if editor is already loaded from cache
			return

		# Priority list of editors to search for
		editors_to_check = [
			'gedit', # Common GNOME editor
			'editor', # Often managed by update-alternatives, user's preference
			'xdg-open', # Preferred for modern desktop environments
			os.environ.get('VISUAL'), # Standard env variable
			os.environ.get('EDITOR'), # Fallback env variable
			'kate', # Common KDE editor
			'mousepad', # Common XFCE editor
		]

		for editor in editors_to_check:
			if editor and shutil.which(editor):
				self.linux_editor_command = [editor]
				self.session_settings['linux_editor_cmd'] = editor
				self._save_session()
				print(f"Found and cached text editor: {editor}")
				return

	def _on_global_mousewheel(self, event):
		if not self.selection_canvas:
			return
		try:
			widget = self.winfo_containing(event.x_root, event.y_root)
			if widget and str(widget).startswith(str(self.selection_canvas)):
				if os.name == 'nt':
					self.selection_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
				elif event.num == 4:
					self.selection_canvas.yview_scroll(-1, "units")
				elif event.num == 5:
					self.selection_canvas.yview_scroll(1, "units")
		except Exception:
			pass

if __name__ == "__main__":
	app = WtsGuiApp()
	app.mainloop()
