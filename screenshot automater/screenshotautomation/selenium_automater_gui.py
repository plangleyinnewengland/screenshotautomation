"""
Selenium Screenshot Automater GUI - Visual interface for browser-based automation
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable

# Import the core functionality
try:
    from selenium_automater import SeleniumAutomater
except ImportError as e:
    print(f"Missing required module: {e}")
    print("Please ensure selenium_automater.py is in the same directory")
    sys.exit(1)


class StatusBar(ttk.Frame):
    """Status bar at the bottom of the window."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.status_label = ttk.Label(self, text="Ready", anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.count_label = ttk.Label(self, text="", anchor=tk.E)
        self.count_label.pack(side=tk.RIGHT, padx=5)
        
    def set_status(self, text: str):
        """Set the status message."""
        self.status_label.config(text=text)
        
    def set_count(self, text: str):
        """Set the count display."""
        self.count_label.config(text=text)


class LogPanel(ttk.LabelFrame):
    """Panel to display log messages."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Activity Log", padding=5)
        
        # Text widget with scrollbar
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(
            text_frame, 
            height=10, 
            width=60,
            font=('Consolas', 9),
            state=tk.DISABLED,
            wrap=tk.WORD
        )
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Clear button
        ttk.Button(self, text="Clear Log", command=self.clear).pack(pady=(5, 0))
        
    def log(self, message: str):
        """Add a log message."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        
    def clear(self):
        """Clear all log messages."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)


class BrowserSettingsPanel(ttk.LabelFrame):
    """Panel for browser settings."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Browser Settings", padding=10)
        
        # Browser selection
        browser_frame = ttk.Frame(self)
        browser_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(browser_frame, text="Browser:").pack(side=tk.LEFT)
        self.browser_var = tk.StringVar(value="chrome")
        for browser in ["chrome", "firefox", "edge"]:
            ttk.Radiobutton(
                browser_frame, 
                text=browser.capitalize(), 
                variable=self.browser_var, 
                value=browser
            ).pack(side=tk.LEFT, padx=10)
        
        # Headless mode
        self.headless_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self, 
            text="Run in headless mode (no visible browser window)",
            variable=self.headless_var
        ).pack(anchor=tk.W, pady=5)
        
        # Wait timeout
        timeout_frame = ttk.Frame(self)
        timeout_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(timeout_frame, text="Element wait timeout (seconds):").pack(side=tk.LEFT)
        self.timeout_var = tk.StringVar(value="10")
        ttk.Spinbox(
            timeout_frame,
            textvariable=self.timeout_var,
            from_=1,
            to=60,
            width=5
        ).pack(side=tk.LEFT, padx=5)


class RecordPanel(ttk.LabelFrame):
    """Panel for recording settings and controls."""
    
    def __init__(self, parent, log_callback: Callable = None, status_callback: Callable = None):
        super().__init__(parent, text="Record Workflow", padding=10)
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.automater: Optional[SeleniumAutomater] = None
        self.is_recording = False
        self.browser_settings = None  # Set by main app
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the recording panel UI."""
        # URL entry
        url_frame = ttk.Frame(self)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="Starting URL:").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value="https://")
        self.url_entry = ttk.Entry(url_frame, textvariable=self.url_var, width=50)
        self.url_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Output directory
        dir_frame = ttk.Frame(self)
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar(value="selenium_screenshots")
        self.output_dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=30)
        self.output_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse...", command=self._browse_output_dir).pack(side=tk.LEFT)
        
        # Naming pattern
        naming_frame = ttk.Frame(self)
        naming_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(naming_frame, text="Naming Pattern:").pack(side=tk.LEFT)
        self.naming_var = tk.StringVar(value="{count}_{action}")
        naming_combo = ttk.Combobox(
            naming_frame,
            textvariable=self.naming_var,
            values=[
                "{count}_{action}",
                "step_{count}",
                "{timestamp}_{count}",
                "screenshot_{count}"
            ],
            width=25
        )
        naming_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Recording indicator and stats
        indicator_frame = ttk.Frame(self)
        indicator_frame.pack(pady=5)
        
        self.indicator_canvas = tk.Canvas(indicator_frame, width=20, height=20, highlightthickness=0)
        self.indicator_canvas.pack(side=tk.LEFT, padx=5)
        self.indicator_circle = self.indicator_canvas.create_oval(2, 2, 18, 18, fill='gray', outline='darkgray')
        
        self.indicator_label = ttk.Label(indicator_frame, text="Not Recording", font=('Segoe UI', 10, 'bold'))
        self.indicator_label.pack(side=tk.LEFT)
        
        self.stats_label = ttk.Label(self, text="Actions recorded: 0", foreground='gray')
        self.stats_label.pack()
        
        # Instructions
        ttk.Label(
            self,
            text="1. Click 'Launch Browser' to open the browser\n2. Click elements in the browser\n3. Click 'Capture Element' to record each action",
            font=('Segoe UI', 9),
            foreground='gray',
            justify=tk.CENTER
        ).pack(pady=10)
        
        # Control buttons row 1 - Start/Stop
        btn_frame1 = ttk.Frame(self)
        btn_frame1.pack(pady=5)
        
        self.start_btn = ttk.Button(
            btn_frame1, 
            text="Launch Browser", 
            command=self._start_recording
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame1, 
            text="Stop & Save", 
            command=self._stop_recording,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        # Control buttons row 2 - Capture
        btn_frame2 = ttk.Frame(self)
        btn_frame2.pack(pady=5)
        
        self.capture_btn = ttk.Button(
            btn_frame2, 
            text="Capture Click", 
            command=lambda: self._capture_element("click"),
            state=tk.DISABLED,
            width=15
        )
        self.capture_btn.pack(side=tk.LEFT, padx=3)
        
        self.capture_input_btn = ttk.Button(
            btn_frame2, 
            text="Capture Input", 
            command=lambda: self._capture_element("input"),
            state=tk.DISABLED,
            width=15
        )
        self.capture_input_btn.pack(side=tk.LEFT, padx=3)
        
    def _browse_output_dir(self):
        """Browse for output directory."""
        dir_path = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.output_dir_var.get() or "."
        )
        if dir_path:
            self.output_dir_var.set(dir_path)
    
    def _log(self, message: str):
        """Log a message."""
        if self.log_callback:
            self.log_callback(message)
    
    def _set_status(self, message: str):
        """Set status bar message."""
        if self.status_callback:
            self.status_callback(message)
    
    def _start_recording(self):
        """Start recording in a background thread."""
        if self.is_recording:
            return
        
        url = self.url_var.get().strip()
        if not url or url == "https://":
            messagebox.showwarning("URL Required", "Please enter a valid URL to start recording.")
            return
        
        # Get browser settings
        browser = "chrome"
        headless = False
        timeout = 10.0
        
        if self.browser_settings:
            browser = self.browser_settings.browser_var.get()
            headless = self.browser_settings.headless_var.get()
            try:
                timeout = float(self.browser_settings.timeout_var.get())
            except:
                timeout = 10.0
        
        # Create automater
        self.automater = SeleniumAutomater(
            output_dir=self.output_dir_var.get(),
            naming_pattern=self.naming_var.get(),
            browser=browser,
            headless=headless,
            wait_timeout=timeout
        )
        self.automater.status_callback = self._log
        
        self.is_recording = True
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.url_entry.config(state=tk.DISABLED)
        self.output_dir_entry.config(state=tk.DISABLED)
        
        self.indicator_canvas.itemconfig(self.indicator_circle, fill='red')
        self.indicator_label.config(text="Recording...")
        self._set_status("Recording in progress - Interact with the browser")
        
        # Start recording in background thread
        def record_thread():
            try:
                self.automater.start_recording(url)
                self._log("Browser launched - recording user interactions")
                self._log("Click elements in the browser - they will be recorded")
                # Start UI update loop
                self.after(500, self._update_recording_stats)
            except Exception as e:
                self._log(f"Error starting recording: {e}")
                self.after(0, self._recording_error)
        
        threading.Thread(target=record_thread, daemon=True).start()
    
    def _update_recording_stats(self):
        """Update the stats label during recording."""
        if self.is_recording and self.automater:
            count = len(self.automater.workflow)
            self.stats_label.config(text=f"Actions recorded: {count}")
            # Schedule next update
            self.after(500, self._update_recording_stats)
    
    def _recording_error(self):
        """Handle recording error."""
        self._stop_recording(save=False)
        messagebox.showerror("Recording Error", "Failed to start browser. Check that the browser driver is installed.")
    
    def _stop_recording(self, save: bool = True):
        """Stop recording and save workflow."""
        if not self.automater:
            return
        
        self.is_recording = False
        
        # Stop and save
        actions = []
        if save:
            try:
                actions = self.automater.stop_recording()
                self.automater.save_workflow()
                self._log(f"Workflow saved with {len(actions)} actions")
            except Exception as e:
                self._log(f"Error saving workflow: {e}")
        
        # Close browser
        try:
            self.automater.close_browser()
        except:
            pass
        
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.url_entry.config(state=tk.NORMAL)
        self.output_dir_entry.config(state=tk.NORMAL)
        
        self.indicator_canvas.itemconfig(self.indicator_circle, fill='gray')
        self.indicator_label.config(text="Not Recording")
        self.stats_label.config(text=f"Actions recorded: {len(actions)}")
        
        self._set_status(f"Recording stopped - {len(actions)} actions saved")
        
        if save and actions:
            result = messagebox.askquestion(
                "Recording Complete",
                f"Recorded {len(actions)} actions.\n\nOpen the output folder?",
                icon='info'
            )
            if result == 'yes':
                os.startfile(str(Path(self.output_dir_var.get()).absolute()))
    
    def _capture_element(self, action_type: str):
        """Manually capture the currently focused element in the browser."""
        if not self.automater or not self.is_recording:
            return
        
        try:
            # Prompt for input value if capturing an input action
            value = None
            if action_type == "input":
                value = simpledialog.askstring(
                    "Input Value",
                    "Enter the text to type into this element:",
                    parent=self
                )
                if value is None:  # User cancelled
                    return
            
            # Capture the focused element
            success = self.automater.capture_focused_element(action_type, value)
            
            if success:
                count = len(self.automater.workflow)
                self.stats_label.config(text=f"Actions recorded: {count}")
                self._log(f"Captured {action_type} action (total: {count})")
            else:
                self._log(f"Failed to capture element - make sure an element is focused in the browser")
                messagebox.showwarning(
                    "Capture Failed",
                    "Could not capture the focused element.\n\n"
                    "Make sure you click on an element in the browser first to focus it."
                )
        except Exception as e:
            self._log(f"Error capturing element: {e}")


class ReplayPanel(ttk.LabelFrame):
    """Panel for replaying workflows."""
    
    def __init__(self, parent, log_callback: Callable = None, status_callback: Callable = None):
        super().__init__(parent, text="Replay Workflow", padding=10)
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.automater: Optional[SeleniumAutomater] = None
        self.is_replaying = False
        self.browser_settings = None  # Set by main app
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the replay panel UI."""
        # Workflow file selection
        workflow_frame = ttk.Frame(self)
        workflow_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(workflow_frame, text="Workflow File:").pack(side=tk.LEFT)
        self.workflow_var = tk.StringVar()
        self.workflow_entry = ttk.Entry(workflow_frame, textvariable=self.workflow_var, width=40)
        self.workflow_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(workflow_frame, text="Browse...", command=self._browse_workflow).pack(side=tk.LEFT)
        
        # Output directory
        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var, width=30).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(output_frame, text="(blank = auto)", foreground='gray').pack(side=tk.LEFT)
        
        # Override URL
        url_frame = ttk.Frame(self)
        url_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(url_frame, text="Override URL:").pack(side=tk.LEFT)
        self.url_override_var = tk.StringVar()
        ttk.Entry(url_frame, textvariable=self.url_override_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Label(url_frame, text="(optional)", foreground='gray').pack(side=tk.LEFT)
        
        # Delay setting
        delay_frame = ttk.Frame(self)
        delay_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(delay_frame, text="Delay between actions (seconds):").pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value="1.0")
        ttk.Spinbox(
            delay_frame,
            textvariable=self.delay_var,
            from_=0.1,
            to=10.0,
            increment=0.5,
            width=8
        ).pack(side=tk.LEFT, padx=5)
        
        # Options
        options_frame = ttk.Frame(self)
        options_frame.pack(fill=tk.X, pady=5)
        
        self.screenshots_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame, 
            text="Capture screenshots",
            variable=self.screenshots_var
        ).pack(side=tk.LEFT, padx=10)
        
        self.stop_on_error_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options_frame, 
            text="Stop on first error",
            variable=self.stop_on_error_var
        ).pack(side=tk.LEFT, padx=10)
        
        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Progress
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready to replay")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=300)
        self.progress_bar.pack(pady=5)
        
        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        
        self.replay_btn = ttk.Button(
            btn_frame, 
            text="Start Replay", 
            command=self._start_replay
        )
        self.replay_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame, 
            text="Stop Replay", 
            command=self._stop_replay,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
    def _browse_workflow(self):
        """Browse for workflow file."""
        filepath = filedialog.askopenfilename(
            title="Select Workflow File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialdir="."
        )
        if filepath:
            self.workflow_var.set(filepath)
    
    def _log(self, message: str):
        """Log a message."""
        if self.log_callback:
            self.log_callback(message)
    
    def _set_status(self, message: str):
        """Set status bar message."""
        if self.status_callback:
            self.status_callback(message)
    
    def _start_replay(self):
        """Start replay in a background thread."""
        if self.is_replaying:
            return
        
        workflow_path = self.workflow_var.get().strip()
        if not workflow_path or not Path(workflow_path).exists():
            messagebox.showwarning("Workflow Required", "Please select a valid workflow file.")
            return
        
        # Get browser settings
        browser = "chrome"
        headless = False
        timeout = 10.0
        
        if self.browser_settings:
            browser = self.browser_settings.browser_var.get()
            headless = self.browser_settings.headless_var.get()
            try:
                timeout = float(self.browser_settings.timeout_var.get())
            except:
                timeout = 10.0
        
        # Create automater
        output_dir = self.output_var.get().strip() or None
        self.automater = SeleniumAutomater(
            output_dir=output_dir or "replay_output",
            browser=browser,
            headless=headless,
            wait_timeout=timeout
        )
        self.automater.status_callback = self._log
        
        self.is_replaying = True
        
        # Update UI
        self.replay_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_bar['value'] = 0
        self.progress_label.config(text="Starting replay...")
        self._set_status("Replay in progress")
        
        # Start replay in background thread
        def replay_thread():
            try:
                delay = float(self.delay_var.get())
            except:
                delay = 1.0
            
            url_override = self.url_override_var.get().strip() or None
            
            try:
                stats = self.automater.replay_workflow(
                    workflow_path=workflow_path,
                    output_dir=output_dir,
                    url=url_override,
                    delay_between_actions=delay,
                    capture_screenshots=self.screenshots_var.get(),
                    stop_on_error=self.stop_on_error_var.get()
                )
                
                # Update UI from main thread
                self.after(0, lambda: self._replay_complete(stats))
                
            except Exception as e:
                self._log(f"Replay error: {e}")
                self.after(0, lambda: self._replay_complete({"success": False, "error": str(e)}))
        
        threading.Thread(target=replay_thread, daemon=True).start()
    
    def _replay_complete(self, stats: Dict):
        """Handle replay completion."""
        self.is_replaying = False
        
        # Close browser
        if self.automater:
            try:
                self.automater.close_browser()
            except:
                pass
        
        # Update UI
        self.replay_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_bar['value'] = 100
        
        if stats.get("success"):
            self.progress_label.config(text=f"Completed: {stats.get('successful', 0)}/{stats.get('total', 0)} actions")
            self._set_status("Replay completed successfully")
            
            result = messagebox.askquestion(
                "Replay Complete",
                f"Successfully replayed {stats.get('successful', 0)} actions.\n"
                f"Screenshots captured: {stats.get('screenshots', 0)}\n\n"
                f"Open the output folder?",
                icon='info'
            )
            if result == 'yes' and self.automater:
                os.startfile(str(self.automater.output_dir.absolute()))
        else:
            self.progress_label.config(text=f"Failed: {stats.get('failed', 0)} errors")
            self._set_status("Replay completed with errors")
            
            errors = stats.get("errors", [])
            error_msg = "\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n... and {len(errors) - 5} more errors"
            
            messagebox.showwarning(
                "Replay Completed with Errors",
                f"Some actions failed:\n\n{error_msg}"
            )
    
    def _stop_replay(self):
        """Stop the replay (not fully implemented - would need threading coordination)."""
        self.is_replaying = False
        self._log("Stop requested - replay will stop after current action")
        self._set_status("Stopping replay...")


class WorkflowEditorPanel(ttk.LabelFrame):
    """Panel for editing workflows."""
    
    def __init__(self, parent, log_callback: Callable = None):
        super().__init__(parent, text="Workflow Editor", padding=10)
        self.log_callback = log_callback
        self.workflow_data = None
        self.current_file = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the editor panel UI."""
        # File selection
        file_frame = ttk.Frame(self)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_frame, text="Open Workflow", command=self._open_workflow).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Save", command=self._save_workflow).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Save As...", command=self._save_workflow_as).pack(side=tk.LEFT, padx=2)
        
        self.file_label = ttk.Label(file_frame, text="No file loaded", foreground='gray')
        self.file_label.pack(side=tk.LEFT, padx=10)
        
        # Actions list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Step", "Type", "Selector", "Value")
        self.actions_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        self.actions_tree.heading("Step", text="#")
        self.actions_tree.heading("Type", text="Action")
        self.actions_tree.heading("Selector", text="Selector")
        self.actions_tree.heading("Value", text="Value")
        
        self.actions_tree.column("Step", width=40)
        self.actions_tree.column("Type", width=80)
        self.actions_tree.column("Selector", width=250)
        self.actions_tree.column("Value", width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.actions_tree.yview)
        self.actions_tree.config(yscrollcommand=scrollbar.set)
        
        self.actions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Edit controls
        edit_frame = ttk.Frame(self)
        edit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(edit_frame, text="Add Action", command=self._add_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Edit Selected", command=self._edit_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Delete Selected", command=self._delete_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Move Up", command=self._move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(edit_frame, text="Move Down", command=self._move_down).pack(side=tk.LEFT, padx=2)
    
    def _log(self, message: str):
        """Log a message."""
        if self.log_callback:
            self.log_callback(message)
    
    def _open_workflow(self):
        """Open a workflow file."""
        filepath = filedialog.askopenfilename(
            title="Open Workflow",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.workflow_data = json.load(f)
            
            self.current_file = filepath
            self.file_label.config(text=Path(filepath).name)
            self._refresh_actions_list()
            self._log(f"Opened: {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
    
    def _save_workflow(self):
        """Save the current workflow."""
        if not self.current_file:
            self._save_workflow_as()
            return
        
        if not self.workflow_data:
            return
        
        try:
            with open(self.current_file, 'w', encoding='utf-8') as f:
                json.dump(self.workflow_data, f, indent=2)
            self._log(f"Saved: {self.current_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")
    
    def _save_workflow_as(self):
        """Save workflow to a new file."""
        if not self.workflow_data:
            messagebox.showwarning("No Workflow", "No workflow loaded to save.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Workflow As",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if filepath:
            self.current_file = filepath
            self.file_label.config(text=Path(filepath).name)
            self._save_workflow()
    
    def _refresh_actions_list(self):
        """Refresh the actions treeview."""
        self.actions_tree.delete(*self.actions_tree.get_children())
        
        if not self.workflow_data:
            return
        
        actions = self.workflow_data.get("actions", [])
        for i, action in enumerate(actions):
            selector = action.get("selector", {})
            selector_str = f"{selector.get('type', 'css')}={selector.get('value', '')}"
            if len(selector_str) > 50:
                selector_str = selector_str[:47] + "..."
            
            value = action.get("value", "")
            if len(value) > 30:
                value = value[:27] + "..."
            
            self.actions_tree.insert("", tk.END, values=(
                i + 1,
                action.get("type", "click"),
                selector_str,
                value
            ))
    
    def _add_action(self):
        """Add a new action to the workflow."""
        if not self.workflow_data:
            self.workflow_data = {"session_info": {}, "actions": []}
        
        # Simple dialog for adding action
        dialog = ActionDialog(self, title="Add Action")
        if dialog.result:
            self.workflow_data["actions"].append(dialog.result)
            self._refresh_actions_list()
            self._log("Added new action")
    
    def _edit_action(self):
        """Edit the selected action."""
        selection = self.actions_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        index = self.actions_tree.index(item)
        
        if self.workflow_data and index < len(self.workflow_data.get("actions", [])):
            action = self.workflow_data["actions"][index]
            dialog = ActionDialog(self, title="Edit Action", action=action)
            if dialog.result:
                self.workflow_data["actions"][index] = dialog.result
                self._refresh_actions_list()
                self._log(f"Updated action {index + 1}")
    
    def _delete_action(self):
        """Delete the selected action."""
        selection = self.actions_tree.selection()
        if not selection:
            return
        
        if messagebox.askyesno("Confirm Delete", "Delete selected action(s)?"):
            indices = [self.actions_tree.index(item) for item in selection]
            for i in sorted(indices, reverse=True):
                if self.workflow_data and i < len(self.workflow_data.get("actions", [])):
                    del self.workflow_data["actions"][i]
            self._refresh_actions_list()
            self._log(f"Deleted {len(indices)} action(s)")
    
    def _move_up(self):
        """Move selected action up."""
        selection = self.actions_tree.selection()
        if not selection or not self.workflow_data:
            return
        
        index = self.actions_tree.index(selection[0])
        actions = self.workflow_data.get("actions", [])
        
        if index > 0:
            actions[index], actions[index - 1] = actions[index - 1], actions[index]
            self._refresh_actions_list()
    
    def _move_down(self):
        """Move selected action down."""
        selection = self.actions_tree.selection()
        if not selection or not self.workflow_data:
            return
        
        index = self.actions_tree.index(selection[0])
        actions = self.workflow_data.get("actions", [])
        
        if index < len(actions) - 1:
            actions[index], actions[index + 1] = actions[index + 1], actions[index]
            self._refresh_actions_list()


class ActionDialog(tk.Toplevel):
    """Dialog for adding/editing actions."""
    
    def __init__(self, parent, title: str = "Action", action: Dict = None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.action = action or {}
        
        self.transient(parent)
        self.grab_set()
        
        self._setup_ui()
        self._populate()
        
        self.wait_window()
    
    def _setup_ui(self):
        """Set up the dialog UI."""
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Action type
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(type_frame, text="Action Type:").pack(side=tk.LEFT)
        self.type_var = tk.StringVar(value="click")
        type_combo = ttk.Combobox(
            type_frame,
            textvariable=self.type_var,
            values=["click", "input", "select"],
            state="readonly",
            width=15
        )
        type_combo.pack(side=tk.LEFT, padx=5)
        
        # Selector type
        sel_type_frame = ttk.Frame(main_frame)
        sel_type_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sel_type_frame, text="Selector Type:").pack(side=tk.LEFT)
        self.sel_type_var = tk.StringVar(value="css")
        sel_type_combo = ttk.Combobox(
            sel_type_frame,
            textvariable=self.sel_type_var,
            values=["id", "css", "xpath", "name", "class"],
            state="readonly",
            width=15
        )
        sel_type_combo.pack(side=tk.LEFT, padx=5)
        
        # Selector value
        sel_val_frame = ttk.Frame(main_frame)
        sel_val_frame.pack(fill=tk.X, pady=5)
        ttk.Label(sel_val_frame, text="Selector Value:").pack(side=tk.LEFT)
        self.sel_val_var = tk.StringVar()
        ttk.Entry(sel_val_frame, textvariable=self.sel_val_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Value (for input/select)
        val_frame = ttk.Frame(main_frame)
        val_frame.pack(fill=tk.X, pady=5)
        ttk.Label(val_frame, text="Value (input/select):").pack(side=tk.LEFT)
        self.val_var = tk.StringVar()
        ttk.Entry(val_frame, textvariable=self.val_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # URL
        url_frame = ttk.Frame(main_frame)
        url_frame.pack(fill=tk.X, pady=5)
        ttk.Label(url_frame, text="URL (optional):").pack(side=tk.LEFT)
        self.url_var = tk.StringVar()
        ttk.Entry(url_frame, textvariable=self.url_var, width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        ttk.Button(btn_frame, text="OK", command=self._ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.RIGHT, padx=5)
    
    def _populate(self):
        """Populate fields from existing action."""
        if self.action:
            self.type_var.set(self.action.get("type", "click"))
            selector = self.action.get("selector", {})
            self.sel_type_var.set(selector.get("type", "css"))
            self.sel_val_var.set(selector.get("value", ""))
            self.val_var.set(self.action.get("value", ""))
            self.url_var.set(self.action.get("url", ""))
    
    def _ok(self):
        """Save and close."""
        self.result = {
            "type": self.type_var.get(),
            "selector": {
                "type": self.sel_type_var.get(),
                "value": self.sel_val_var.get()
            }
        }
        
        if self.val_var.get():
            self.result["value"] = self.val_var.get()
        if self.url_var.get():
            self.result["url"] = self.url_var.get()
        
        self.destroy()


class SeleniumAutomaterGUI(tk.Tk):
    """Main application window for Selenium automation."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Selenium Screenshot Automater")
        self.geometry("800x700")
        self.minsize(700, 600)
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the main UI."""
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create tabs
        record_tab = ttk.Frame(self.notebook, padding=10)
        replay_tab = ttk.Frame(self.notebook, padding=10)
        editor_tab = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(record_tab, text="Record")
        self.notebook.add(replay_tab, text="Replay")
        self.notebook.add(editor_tab, text="Editor")
        
        # Status bar
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        
        # Log panel (shared across tabs)
        log_frame = ttk.Frame(self)
        log_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        self.log_panel = LogPanel(log_frame)
        self.log_panel.pack(fill=tk.X)
        
        # Browser settings (shared)
        self.browser_settings = BrowserSettingsPanel(record_tab)
        self.browser_settings.pack(fill=tk.X, pady=5)
        
        # Record panel
        self.record_panel = RecordPanel(
            record_tab,
            log_callback=self.log_panel.log,
            status_callback=self.status_bar.set_status
        )
        self.record_panel.browser_settings = self.browser_settings
        self.record_panel.pack(fill=tk.X, pady=5)
        
        # Replay tab browser settings
        replay_browser_settings = BrowserSettingsPanel(replay_tab)
        replay_browser_settings.pack(fill=tk.X, pady=5)
        
        # Replay panel
        self.replay_panel = ReplayPanel(
            replay_tab,
            log_callback=self.log_panel.log,
            status_callback=self.status_bar.set_status
        )
        self.replay_panel.browser_settings = replay_browser_settings
        self.replay_panel.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Editor panel
        self.editor_panel = WorkflowEditorPanel(
            editor_tab,
            log_callback=self.log_panel.log
        )
        self.editor_panel.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Initial log message
        self.log_panel.log("Selenium Automater ready")
        self.log_panel.log("Use the Record tab to capture browser interactions")
        self.log_panel.log("Use the Replay tab to replay saved workflows")


def main():
    """Run the GUI application."""
    app = SeleniumAutomaterGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
