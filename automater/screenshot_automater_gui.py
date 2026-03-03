"""
Screenshot Automater GUI - Visual interface for recording and replaying screenshots
"""

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable

# Import the core functionality
try:
    from screenshot_automater import ScreenshotAutomater
    from pynput import mouse
    from pynput.mouse import Button, Controller as MouseController
    import pyautogui
    from screeninfo import get_monitors
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
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


class MonitorDisplay(ttk.LabelFrame):
    """Display connected monitors information."""
    
    def __init__(self, parent):
        super().__init__(parent, text="Connected Monitors", padding=10)
        
        self.monitor_text = tk.Text(self, height=4, width=50, state=tk.DISABLED,
                                     font=('Consolas', 9))
        self.monitor_text.pack(fill=tk.BOTH, expand=True)
        
        self.refresh_btn = ttk.Button(self, text="Refresh", command=self.refresh_monitors)
        self.refresh_btn.pack(pady=(5, 0))
        
        self.refresh_monitors()
        
    def refresh_monitors(self):
        """Refresh the monitor list."""
        self.monitor_text.config(state=tk.NORMAL)
        self.monitor_text.delete("1.0", tk.END)
        
        try:
            monitors = get_monitors()
            for i, monitor in enumerate(monitors, 1):
                name = monitor.name or f"Display {i}"
                primary = " (primary)" if monitor.is_primary else ""
                info = f"{i}. {name}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y}){primary}\n"
                self.monitor_text.insert(tk.END, info)
        except Exception as e:
            self.monitor_text.insert(tk.END, f"Error detecting monitors: {e}")
            
        self.monitor_text.config(state=tk.DISABLED)


class FolderFilesPreview(ttk.LabelFrame):
    """Widget to show files in a selected folder."""
    
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
    
    def __init__(self, parent, title: str = "Folder Contents", height: int = 6, 
                 filter_images: bool = False, show_count: bool = True):
        super().__init__(parent, text=title, padding=5)
        self.filter_images = filter_images
        self.show_count = show_count
        self.current_path = None
        
        # Header with count
        if show_count:
            self.count_label = ttk.Label(self, text="No folder selected", foreground='gray')
            self.count_label.pack(anchor=tk.W)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(3, 0))
        
        self.file_listbox = tk.Listbox(
            list_frame, 
            height=height,
            font=('Consolas', 9),
            selectmode=tk.EXTENDED,
            activestyle='none'
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def set_folder(self, folder_path: str):
        """Update the file list for the given folder."""
        self.current_path = folder_path
        self.file_listbox.delete(0, tk.END)
        
        if not folder_path:
            if self.show_count:
                self.count_label.config(text="No folder selected")
            return
            
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            if self.show_count:
                self.count_label.config(text="Folder does not exist")
            return
        
        try:
            files = []
            for item in sorted(folder.iterdir()):
                if item.is_file():
                    if self.filter_images:
                        if item.suffix.lower() in self.IMAGE_EXTENSIONS:
                            files.append(item)
                    else:
                        files.append(item)
            
            for f in files:
                # Format: filename (size)
                size = f.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                    
                self.file_listbox.insert(tk.END, f"{f.name}  ({size_str})")
            
            if self.show_count:
                if self.filter_images:
                    self.count_label.config(text=f"{len(files)} image(s) found")
                else:
                    self.count_label.config(text=f"{len(files)} file(s) found")
                    
        except Exception as e:
            if self.show_count:
                self.count_label.config(text=f"Error: {e}")
    
    def get_file_count(self) -> int:
        """Return the number of files currently displayed."""
        return self.file_listbox.size()
    
    def refresh(self):
        """Refresh the current folder contents."""
        if self.current_path:
            self.set_folder(self.current_path)


class RecordPanel(ttk.LabelFrame):
    """Panel for recording settings and controls."""
    
    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Recording", padding=10)
        self.on_status_change = on_status_change
        self.automater: Optional[ScreenshotAutomater] = None
        self.is_recording = False
        self.listener = None
        self.click_count = 0
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the recording panel UI."""
        # Output directory
        dir_frame = ttk.Frame(self)
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar(value="screenshots")
        self.output_dir_entry = ttk.Entry(dir_frame, textvariable=self.output_dir_var, width=30)
        self.output_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="Browse...", command=self._browse_output_dir).pack(side=tk.LEFT)
        
        # Folder contents preview
        self.folder_preview = FolderFilesPreview(self, title="Existing Files", height=4, filter_images=True)
        self.folder_preview.pack(fill=tk.X, pady=5)
        self.folder_preview.set_folder(self.output_dir_var.get())
        
        # Update preview when path changes (typing, pasting, etc.)
        self.output_dir_var.trace_add("write", lambda *args: self.folder_preview.set_folder(self.output_dir_var.get()))
        
        # Naming pattern
        naming_frame = ttk.Frame(self)
        naming_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(naming_frame, text="Naming Pattern:").pack(side=tk.LEFT)
        self.naming_var = tk.StringVar(value="{timestamp}_{count}")
        naming_combo = ttk.Combobox(
            naming_frame,
            textvariable=self.naming_var,
            values=[
                "{timestamp}_{count}",
                "screenshot_{count}",
                "step_{count}",
                "{date}_{count}",
                "click_{x}_{y}_{count}"
            ],
            width=25
        )
        naming_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Pattern help
        help_frame = ttk.Frame(self)
        help_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(
            help_frame, 
            text="Variables: {timestamp}, {count}, {x}, {y}, {date}, {time}",
            font=('Segoe UI', 8),
            foreground='gray'
        ).pack(side=tk.LEFT)
        
        # Image format
        format_frame = ttk.Frame(self)
        format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(format_frame, text="Image Format:").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value="png")
        for fmt in ["png", "jpg", "bmp"]:
            ttk.Radiobutton(
                format_frame, 
                text=fmt.upper(), 
                variable=self.format_var, 
                value=fmt
            ).pack(side=tk.LEFT, padx=10)
        
        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Recording stats
        stats_frame = ttk.Frame(self)
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_label = ttk.Label(
            stats_frame, 
            text="Clicks captured: 0",
            font=('Segoe UI', 11, 'bold')
        )
        self.stats_label.pack()
        
        # Last capture info
        self.last_capture_label = ttk.Label(
            stats_frame,
            text="",
            font=('Segoe UI', 9),
            foreground='gray'
        )
        self.last_capture_label.pack()
        
        # Recording indicator
        self.indicator_frame = ttk.Frame(self)
        self.indicator_frame.pack(pady=10)
        
        self.indicator_canvas = tk.Canvas(self.indicator_frame, width=20, height=20, highlightthickness=0)
        self.indicator_canvas.pack(side=tk.LEFT, padx=5)
        self.indicator_circle = self.indicator_canvas.create_oval(2, 2, 18, 18, fill='gray', outline='darkgray')
        
        self.indicator_label = ttk.Label(self.indicator_frame, text="Not Recording")
        self.indicator_label.pack(side=tk.LEFT)
        
        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(
            btn_frame, 
            text="Start Recording", 
            command=self._start_recording,
            style='Accent.TButton'
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame, 
            text="Stop Recording", 
            command=self._stop_recording,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
    def _browse_output_dir(self):
        """Browse for output directory."""
        dir_path = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.output_dir_var.get()
        )
        if dir_path:
            self.output_dir_var.set(dir_path)
            self.folder_preview.set_folder(dir_path)
            
    def _start_recording(self):
        """Start recording screenshots on click."""
        if self.is_recording:
            return
            
        # Create automater instance
        self.automater = ScreenshotAutomater(
            output_dir=self.output_dir_var.get(),
            naming_pattern=self.naming_var.get(),
            image_format=self.format_var.get()
        )
        
        self.is_recording = True
        self.click_count = 0
        self.automater.session_start_time = datetime.now().timestamp()
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.output_dir_entry.config(state=tk.DISABLED)
        
        # Update indicator
        self.indicator_canvas.itemconfig(self.indicator_circle, fill='red')
        self.indicator_label.config(text="Recording...")
        
        if self.on_status_change:
            self.on_status_change("Recording in progress - Click anywhere to capture")
        
        # Start mouse listener in background thread
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()
        
        self._update_stats()
        
    def _stop_recording(self):
        """Stop recording."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        if self.listener:
            self.listener.stop()
            self.listener = None
        
        # Save workflow
        if self.automater:
            self.automater._save_workflow()
            
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.output_dir_entry.config(state=tk.NORMAL)
        
        # Update indicator
        self.indicator_canvas.itemconfig(self.indicator_circle, fill='gray')
        self.indicator_label.config(text="Not Recording")
        
        if self.on_status_change:
            self.on_status_change(f"Recording stopped - {self.click_count} screenshots captured")
            
        # Show completion message
        output_dir = self.automater.output_dir.absolute() if self.automater else self.output_dir_var.get()
        result = messagebox.askquestion(
            "Recording Complete",
            f"Captured {self.click_count} screenshots.\n\nOpen the output folder?",
            icon='info'
        )
        if result == 'yes':
            self._open_folder(output_dir)
            
    def _on_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click events."""
        if not pressed or button != Button.left:
            return
            
        if not self.is_recording or not self.automater:
            return
            
        # Record click and capture screenshot
        self.automater._on_click(x, y, button, pressed)
        self.click_count = self.automater.click_count
        
        # Update UI from main thread
        self.after(10, self._update_stats)
        self.after(10, lambda: self.last_capture_label.config(
            text=f"Last: ({x}, {y}) at {datetime.now().strftime('%H:%M:%S')}"
        ))
        
    def _update_stats(self):
        """Update the stats display."""
        self.stats_label.config(text=f"Clicks captured: {self.click_count}")
        
    def _open_folder(self, folder_path):
        """Open folder in file explorer."""
        try:
            if sys.platform == "win32":
                os.startfile(str(folder_path))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(folder_path)], check=True)
            else:
                import subprocess
                subprocess.run(["xdg-open", str(folder_path)], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")


class ReplayPanel(ttk.LabelFrame):
    """Panel for replay settings and controls."""
    
    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Replay", padding=10)
        self.on_status_change = on_status_change
        self.is_replaying = False
        self.workflow_data = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the replay panel UI."""
        # Workflow file selection
        workflow_frame = ttk.Frame(self)
        workflow_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(workflow_frame, text="Workflow File:").pack(side=tk.LEFT)
        self.workflow_var = tk.StringVar()
        self.workflow_entry = ttk.Entry(workflow_frame, textvariable=self.workflow_var, width=30)
        self.workflow_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(workflow_frame, text="Browse...", command=self._browse_workflow).pack(side=tk.LEFT)
        
        # Workflow info
        self.workflow_info_label = ttk.Label(
            self,
            text="No workflow loaded",
            font=('Segoe UI', 9),
            foreground='gray'
        )
        self.workflow_info_label.pack(pady=(0, 5))
        
        # Workflow folder files preview
        self.workflow_preview = FolderFilesPreview(self, title="Workflow Folder Contents", height=4, filter_images=True)
        self.workflow_preview.pack(fill=tk.X, pady=(0, 10))
        
        # Update preview when workflow path changes
        def update_workflow_preview(*args):
            path = self.workflow_var.get()
            if path and Path(path).exists():
                self.workflow_preview.set_folder(str(Path(path).parent))
        self.workflow_var.trace_add("write", update_workflow_preview)
        
        # Output directory
        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(output_frame, text="Output Directory:").pack(side=tk.LEFT)
        self.output_dir_var = tk.StringVar()
        self.output_dir_entry = ttk.Entry(output_frame, textvariable=self.output_dir_var, width=30)
        self.output_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse...", command=self._browse_output_dir).pack(side=tk.LEFT)
        
        ttk.Label(
            self,
            text="Leave empty for auto-generated folder (replay_YYYYMMDD_HHMMSS)",
            font=('Segoe UI', 8),
            foreground='gray'
        ).pack(anchor=tk.W)
        
        # Delay settings
        delay_frame = ttk.Frame(self)
        delay_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(delay_frame, text="Delay Multiplier:").pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value="1.0")
        delay_spin = ttk.Spinbox(
            delay_frame,
            textvariable=self.delay_var,
            from_=0.1,
            to=10.0,
            increment=0.1,
            width=8
        )
        delay_spin.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(delay_frame, text="Min Delay (sec):").pack(side=tk.LEFT, padx=(20, 0))
        self.min_delay_var = tk.StringVar(value="0.5")
        min_delay_spin = ttk.Spinbox(
            delay_frame,
            textvariable=self.min_delay_var,
            from_=0.1,
            to=5.0,
            increment=0.1,
            width=8
        )
        min_delay_spin.pack(side=tk.LEFT, padx=5)
        
        # Capture option
        self.capture_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self,
            text="Capture screenshots during replay",
            variable=self.capture_var
        ).pack(anchor=tk.W, pady=5)
        
        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Progress
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready to replay")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate', length=300)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(
            btn_frame,
            text="Start Replay",
            command=self._start_replay,
            style='Accent.TButton'
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame,
            text="Stop Replay",
            command=self._stop_replay,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
    def _browse_workflow(self):
        """Browse for workflow file."""
        file_path = filedialog.askopenfilename(
            title="Select Workflow File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.workflow_var.set(file_path)
            self._load_workflow_info(file_path)
            # Show files in the workflow folder
            self.workflow_preview.set_folder(str(Path(file_path).parent))
            
    def _browse_output_dir(self):
        """Browse for output directory."""
        dir_path = filedialog.askdirectory(
            title="Select Output Directory"
        )
        if dir_path:
            self.output_dir_var.set(dir_path)
            
    def _load_workflow_info(self, file_path: str):
        """Load and display workflow information."""
        try:
            with open(file_path, 'r') as f:
                self.workflow_data = json.load(f)
                
            clicks = self.workflow_data.get("clicks", [])
            session_info = self.workflow_data.get("session_info", {})
            
            info_text = f"{len(clicks)} clicks | Recorded: {session_info.get('start_time', 'Unknown')}"
            self.workflow_info_label.config(text=info_text, foreground='black')
            
        except Exception as e:
            self.workflow_info_label.config(text=f"Error loading workflow: {e}", foreground='red')
            self.workflow_data = None
            
    def _start_replay(self):
        """Start the replay in a background thread."""
        if not self.workflow_var.get():
            messagebox.showwarning("Warning", "Please select a workflow file first.")
            return
            
        if self.is_replaying:
            return
            
        self.is_replaying = True
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress_label.config(text="Starting replay...")
        
        if self.on_status_change:
            self.on_status_change("Replay in progress - Move mouse to corner to abort")
        
        # Start replay in background thread
        thread = threading.Thread(target=self._run_replay, daemon=True)
        thread.start()
        
    def _run_replay(self):
        """Run the replay (in background thread)."""
        try:
            automater = ScreenshotAutomater()
            automater.replay_workflow(
                workflow_path=self.workflow_var.get(),
                output_dir=self.output_dir_var.get() or None,
                delay_multiplier=float(self.delay_var.get()),
                min_delay=float(self.min_delay_var.get()),
                capture_screenshots=self.capture_var.get()
            )
            
            # Update UI from main thread
            self.after(10, lambda: self._replay_complete(automater.click_count))
            
        except Exception as e:
            self.after(10, lambda: self._replay_error(str(e)))
            
    def _replay_complete(self, count: int):
        """Called when replay completes."""
        self.is_replaying = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_label.config(text=f"Replay complete - {count} screenshots captured")
        self.progress_bar['value'] = 100
        
        if self.on_status_change:
            self.on_status_change(f"Replay complete - {count} screenshots captured")
            
        messagebox.showinfo("Complete", f"Replay finished!\nScreenshots captured: {count}")
        
    def _replay_error(self, error: str):
        """Called when replay has an error."""
        self.is_replaying = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress_label.config(text=f"Error: {error}")
        
        if self.on_status_change:
            self.on_status_change(f"Replay error: {error}")
            
        messagebox.showerror("Error", f"Replay failed:\n{error}")
        
    def _stop_replay(self):
        """Stop the replay (moves mouse to corner)."""
        # PyAutoGUI failsafe - notify user to move mouse to corner
        messagebox.showinfo(
            "Stop Replay",
            "Move your mouse to any corner of the screen to abort the replay.\n\n"
            "(This is the PyAutoGUI failsafe mechanism)"
        )


class QuickVideoDialog(tk.Toplevel):
    """Dialog for creating a quick video without narration."""
    
    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent)
        self.on_status_change = on_status_change
        self.title("Quick Video (No Narration)")
        self.geometry("500x650")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._setup_ui()
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
    def _setup_ui(self):
        """Set up the dialog UI."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(
            main_frame,
            text="Create MP4 Video (No Narration)",
            font=('Segoe UI', 12, 'bold')
        ).pack(pady=(0, 15))
        
        # Input folder
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding=10)
        input_frame.pack(fill=tk.X, pady=5)
        
        folder_frame = ttk.Frame(input_frame)
        folder_frame.pack(fill=tk.X)
        
        ttk.Label(folder_frame, text="Screenshots Folder:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=30)
        self.folder_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(folder_frame, text="Browse...", command=self._browse_folder).pack(side=tk.LEFT)
        
        # Folder files preview
        self.folder_preview = FolderFilesPreview(input_frame, title="Images in Folder", height=5, filter_images=True)
        self.folder_preview.pack(fill=tk.X, pady=(5, 0))
        
        # Update preview when path changes
        self.folder_var.trace_add("write", lambda *args: self.folder_preview.set_folder(self.folder_var.get()))
        
        # Settings
        settings_frame = ttk.LabelFrame(main_frame, text="Video Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Resolution
        res_frame = ttk.Frame(settings_frame)
        res_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(res_frame, text="Resolution:").pack(side=tk.LEFT)
        self.resolution_var = tk.StringVar(value="1920x1080")
        res_combo = ttk.Combobox(
            res_frame,
            textvariable=self.resolution_var,
            values=["1920x1080 (1080p)", "1280x720 (720p)", "3840x2160 (4K)", "1024x768"],
            width=20,
            state="readonly"
        )
        res_combo.pack(side=tk.LEFT, padx=10)
        
        # Duration per image
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(duration_frame, text="Duration per image:").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="3.0")
        duration_spin = ttk.Spinbox(
            duration_frame,
            textvariable=self.duration_var,
            from_=0.5,
            to=30.0,
            increment=0.5,
            width=8
        )
        duration_spin.pack(side=tk.LEFT, padx=10)
        ttk.Label(duration_frame, text="seconds").pack(side=tk.LEFT)
        
        # Transition
        trans_frame = ttk.Frame(settings_frame)
        trans_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(trans_frame, text="Transition:").pack(side=tk.LEFT)
        self.transition_var = tk.StringVar(value="fade")
        trans_combo = ttk.Combobox(
            trans_frame,
            textvariable=self.transition_var,
            values=["none", "fade", "crossfade", "slide_left", "slide_right", "slide_up", "slide_down"],
            width=15,
            state="readonly"
        )
        trans_combo.pack(side=tk.LEFT, padx=10)
        
        # Transition duration
        trans_dur_frame = ttk.Frame(settings_frame)
        trans_dur_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(trans_dur_frame, text="Transition duration:").pack(side=tk.LEFT)
        self.trans_duration_var = tk.StringVar(value="1.0")
        trans_dur_spin = ttk.Spinbox(
            trans_dur_frame,
            textvariable=self.trans_duration_var,
            from_=0.1,
            to=3.0,
            increment=0.1,
            width=8
        )
        trans_dur_spin.pack(side=tk.LEFT, padx=10)
        ttk.Label(trans_dur_frame, text="seconds").pack(side=tk.LEFT)
        
        # Output
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding=10)
        output_frame.pack(fill=tk.X, pady=5)
        
        out_file_frame = ttk.Frame(output_frame)
        out_file_frame.pack(fill=tk.X)
        
        ttk.Label(out_file_frame, text="Output File:").pack(side=tk.LEFT)
        self.output_var = tk.StringVar(value="output_video.mp4")
        self.output_entry = ttk.Entry(out_file_frame, textvariable=self.output_var, width=30)
        self.output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(out_file_frame, text="Browse...", command=self._browse_output).pack(side=tk.LEFT)
        
        # Progress
        self.progress_label = ttk.Label(main_frame, text="")
        self.progress_label.pack(pady=5)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='determinate', length=400, maximum=100)
        self.progress_bar.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        
        self.generate_btn = ttk.Button(
            btn_frame,
            text="Generate Video",
            command=self._generate_video,
            style='Accent.TButton'
        )
        self.generate_btn.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=10)
        
    def _browse_folder(self):
        """Browse for input folder."""
        dir_path = filedialog.askdirectory(title="Select Screenshots Folder")
        if dir_path:
            self.folder_var.set(dir_path)
            self.folder_preview.set_folder(dir_path)
            
            # Auto-set output file path to be inside the screenshots folder
            folder_name = Path(dir_path).name
            output_path = str(Path(dir_path) / f"{folder_name}_video.mp4")
            self.output_var.set(output_path)
            
    def _browse_output(self):
        """Browse for output file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Video As",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")],
            initialfile=self.output_var.get()
        )
        if file_path:
            self.output_var.set(file_path)
            
    def _generate_video(self):
        """Generate the video."""
        if not self.folder_var.get():
            messagebox.showwarning("Warning", "Please select a screenshots folder.")
            return
            
        if not self.output_var.get():
            messagebox.showwarning("Warning", "Please specify an output file.")
            return
            
        # Disable button and reset progress
        self.generate_btn.config(state=tk.DISABLED)
        self.progress_label.config(text="Starting video generation...")
        self.progress_bar['value'] = 0
        
        # Run in background thread
        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()
        
    def _update_progress(self, current, total, message):
        """Update progress bar from background thread."""
        # Schedule UI update on main thread
        self.after(10, lambda: self._do_update_progress(current, total, message))
        
    def _do_update_progress(self, current, total, message):
        """Actually update the UI (must be called on main thread)."""
        self.progress_bar['value'] = current
        # Extract a clean status message
        clean_msg = message.strip().lstrip('=').strip()
        if clean_msg and not clean_msg.startswith('\n'):
            self.progress_label.config(text=clean_msg[:60])  # Truncate long messages
        
    def _run_generation(self):
        """Run the video generation in background thread."""
        try:
            from video_generator import VideoGenerator
            
            # Parse resolution
            res_str = self.resolution_var.get().split()[0]  # Get "1920x1080" part
            width, height = map(int, res_str.split('x'))
            
            # Create generator
            generator = VideoGenerator(
                output_resolution=(width, height),
                default_image_duration=float(self.duration_var.get()),
                transition_duration=float(self.trans_duration_var.get())
            )
            
            # Get images
            images = generator.get_images_from_directory(self.folder_var.get())
            
            if not images:
                self.after(10, lambda: self._generation_error("No images found in folder."))
                return
            
            # Build config without narration
            config = {
                'images': [
                    {
                        'image_path': str(img),
                        'narration': '',  # No narration
                        'duration': float(self.duration_var.get()),
                        'transition': self.transition_var.get()
                    }
                    for img in images
                ],
                'output_path': self.output_var.get(),
                'resolution': (width, height),
                'default_transition': self.transition_var.get(),
                'default_duration': float(self.duration_var.get()),
                'voice_id': None
            }
            
            # Generate video with progress callback
            generator.generate_video(config, progress_callback=self._update_progress)
            
            self.after(10, self._generation_complete)
            
        except Exception as e:
            self.after(10, lambda: self._generation_error(str(e)))
            
    def _generation_complete(self):
        """Called when generation is complete."""
        self.progress_bar['value'] = 100
        self.progress_label.config(text="Video generated successfully!")
        self.generate_btn.config(state=tk.NORMAL)
        
        if self.on_status_change:
            self.on_status_change(f"Video saved to: {self.output_var.get()}")
        
        result = messagebox.askquestion(
            "Success",
            f"Video generated successfully!\n\nOutput: {self.output_var.get()}\n\nOpen the video file?",
            icon='info'
        )
        if result == 'yes':
            self._open_video()
            
        self.destroy()
        
    def _generation_error(self, error: str):
        """Called when generation fails."""
        self.progress_bar['value'] = 0
        self.progress_label.config(text=f"Error: {error}")
        self.generate_btn.config(state=tk.NORMAL)
        
        if self.on_status_change:
            self.on_status_change(f"Video generation error: {error}")
            
        messagebox.showerror("Error", f"Video generation failed:\n{error}")
        
    def _open_video(self):
        """Open the generated video file."""
        try:
            import os
            if sys.platform == "win32":
                os.startfile(self.output_var.get())
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", self.output_var.get()], check=True)
            else:
                import subprocess
                subprocess.run(["xdg-open", self.output_var.get()], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video: {e}")


class CamtasiaExportDialog(tk.Toplevel):
    """Dialog for exporting images to Camtasia project."""
    
    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent)
        self.on_status_change = on_status_change
        self.title("Export to Camtasia")
        self.geometry("650x620")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._setup_ui()
        
        # Center the dialog
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
    def _setup_ui(self):
        """Set up the dialog UI."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(
            main_frame,
            text="Export Images to Camtasia",
            font=('Segoe UI', 12, 'bold')
        ).pack(pady=(0, 10))
        
        # Input folder
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding=10)
        input_frame.pack(fill=tk.X, pady=5)
        
        folder_frame = ttk.Frame(input_frame)
        folder_frame.pack(fill=tk.X)
        
        ttk.Label(folder_frame, text="Screenshots Folder:").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar()
        self.folder_entry = ttk.Entry(folder_frame, textvariable=self.folder_var, width=30)
        self.folder_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(folder_frame, text="Browse...", command=self._browse_folder).pack(side=tk.LEFT)
        
        # Folder files preview
        self.folder_preview = FolderFilesPreview(input_frame, title="Images in Folder", height=5, filter_images=True)
        self.folder_preview.pack(fill=tk.X, pady=(5, 0))
        
        # Update preview when path changes
        self.folder_var.trace_add("write", lambda *args: self.folder_preview.set_folder(self.folder_var.get()))
        
        # Settings
        settings_frame = ttk.LabelFrame(main_frame, text="Project Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=10)
        
        # Duration
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(duration_frame, text="Duration per image:").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="5.0")
        duration_spin = ttk.Spinbox(
            duration_frame,
            textvariable=self.duration_var,
            from_=1.0,
            to=60.0,
            increment=0.5,
            width=8
        )
        duration_spin.pack(side=tk.LEFT, padx=10)
        ttk.Label(duration_frame, text="seconds").pack(side=tk.LEFT)
        
        # Resolution
        res_frame = ttk.Frame(settings_frame)
        res_frame.pack(fill=tk.X, pady=3)
        
        ttk.Label(res_frame, text="Project resolution:").pack(side=tk.LEFT)
        self.resolution_var = tk.StringVar(value="1920x1080")
        res_combo = ttk.Combobox(
            res_frame,
            textvariable=self.resolution_var,
            values=["1920x1080", "1280x720", "3840x2160", "1024x768"],
            width=15,
            state="readonly"
        )
        res_combo.pack(side=tk.LEFT, padx=10)
        
        # Export options
        export_frame = ttk.LabelFrame(main_frame, text="Export Options", padding=10)
        export_frame.pack(fill=tk.X, pady=5)
        
        self.create_project_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            export_frame,
            text="Create Camtasia project file (.tscproj)",
            variable=self.create_project_var
        ).pack(anchor=tk.W)
        
        self.create_scripts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            export_frame,
            text="Create import helper scripts (for manual import)",
            variable=self.create_scripts_var
        ).pack(anchor=tk.W)
        
        # Info text
        info_text = ttk.Label(
            main_frame,
            text="Note: The .tscproj file is a basic project structure. For best results,\n"
                 "use the import helper scripts to drag images into Camtasia directly.",
            font=('Segoe UI', 8),
            foreground='gray'
        )
        info_text.pack(pady=10)
        
        # Status
        self.status_label = ttk.Label(main_frame, text="")
        self.status_label.pack(pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        self.export_btn = ttk.Button(
            btn_frame,
            text="Export",
            command=self._export,
            style='Accent.TButton'
        )
        self.export_btn.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            btn_frame,
            text="Open Folder & Camtasia",
            command=self._open_folder_and_camtasia
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Open Camtasia & Import",
            command=self._open_camtasia_new_project_import
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=10)
        
    def _browse_folder(self):
        """Browse for input folder."""
        dir_path = filedialog.askdirectory(title="Select Screenshots Folder")
        if dir_path:
            self.folder_var.set(dir_path)
            self.folder_preview.set_folder(dir_path)
            
    def _export(self):
        """Export to Camtasia."""
        if not self.folder_var.get():
            messagebox.showwarning("Warning", "Please select a screenshots folder.")
            return
            
        if not self.create_project_var.get() and not self.create_scripts_var.get():
            messagebox.showwarning("Warning", "Please select at least one export option.")
            return
        
        try:
            from camtasia_generator import create_camtasia_project, generate_camtasia_import_script
            
            folder = self.folder_var.get()
            res_str = self.resolution_var.get()
            width, height = map(int, res_str.split('x'))
            duration = float(self.duration_var.get())
            
            results = []
            
            if self.create_project_var.get():
                project_path = create_camtasia_project(
                    folder,
                    image_duration=duration,
                    project_width=width,
                    project_height=height
                )
                results.append(f"Project: {project_path}")
            
            if self.create_scripts_var.get():
                script_path = generate_camtasia_import_script(folder)
                results.append(f"Scripts: {script_path}")
            
            self.status_label.config(text="Export complete!")
            
            if self.on_status_change:
                self.on_status_change("Camtasia export complete")
            
            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported!\n\n" + "\n".join(results) + "\n\n"
                "You can now:\n"
                "1. Open the .tscproj file in Camtasia\n"
                "2. Or run the helper scripts to copy paths and import manually"
            )
            
        except Exception as e:
            self.status_label.config(text=f"Error: {e}")
            messagebox.showerror("Error", f"Export failed:\n{e}")
            
    def _open_folder_and_camtasia(self):
        """Open the folder in explorer and try to launch Camtasia."""
        if not self.folder_var.get():
            messagebox.showwarning("Warning", "Please select a screenshots folder first.")
            return
        
        folder = Path(self.folder_var.get())
        
        # Open folder in explorer
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")
        
        # Try to find and launch Camtasia
        camtasia_paths = [
            r"C:\Program Files\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2023\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2022\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
        ]
        
        for path in camtasia_paths:
            if Path(path).exists():
                try:
                    import subprocess
                    subprocess.Popen([path])
                    self.status_label.config(text="Opened folder and Camtasia")
                    return
                except:
                    pass
        
        self.status_label.config(text="Opened folder (Camtasia not found)")
        messagebox.showinfo(
            "Camtasia Not Found",
            "Could not locate Camtasia installation.\n\n"
            "The folder has been opened. Please:\n"
            "1. Open Camtasia manually\n"
            "2. Select all images in the folder\n"
            "3. Drag them into Camtasia's Media Bin"
        )
    
    def _open_camtasia_new_project_import(self):
        """Open Camtasia, start a new project, and open File > Import > Media dialog."""
        import subprocess
        import time
        
        # Find Camtasia executable
        camtasia_paths = [
            r"C:\Program Files\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2023\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2022\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
        ]
        
        camtasia_exe = None
        for path in camtasia_paths:
            if Path(path).exists():
                camtasia_exe = path
                break
        
        if not camtasia_exe:
            messagebox.showerror(
                "Camtasia Not Found",
                "Could not locate Camtasia installation.\n\n"
                "Please ensure Camtasia is installed in the default location."
            )
            return
        
        self.status_label.config(text="Starting Camtasia...")
        self.update()
        
        try:
            # Launch Camtasia
            subprocess.Popen([camtasia_exe])
            
            # Wait for Camtasia to start (give it time to load)
            self.status_label.config(text="Waiting for Camtasia to load...")
            self.update()
            
            # Wait for the Camtasia window to appear
            max_wait = 30  # Maximum seconds to wait
            start_time = time.time()
            camtasia_window = None
            
            while time.time() - start_time < max_wait:
                try:
                    # Look for Camtasia window
                    windows = pyautogui.getWindowsWithTitle('Camtasia')
                    if windows:
                        camtasia_window = windows[0]
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            
            if not camtasia_window:
                self.status_label.config(text="Camtasia window not detected")
                messagebox.showwarning(
                    "Window Not Found",
                    "Camtasia was launched but the window was not detected.\n\n"
                    "Please manually:\n"
                    "1. Click 'New Project' in Camtasia\n"
                    "2. Go to File > Import > Media"
                )
                return
            
            # Activate Camtasia window
            try:
                camtasia_window.activate()
            except Exception:
                # Some windows can't be activated programmatically
                pass
            
            time.sleep(2)  # Wait for window to be fully active
            
            self.status_label.config(text="Creating new project...")
            self.update()
            
            # Press Ctrl+N to create a new project
            pyautogui.hotkey('ctrl', 'n')
            
            # Wait for the new project dialog/window to appear
            time.sleep(3)
            
            # Press Enter to confirm any "New Project" dialog if present
            pyautogui.press('enter')
            
            # Wait for project to load
            time.sleep(2)
            
            self.status_label.config(text="Opening Import Media dialog...")
            self.update()
            
            # Open File > Import > Media using keyboard shortcuts
            # Alt+F opens File menu, then I for Import, then M for Media
            pyautogui.hotkey('ctrl', 'i')  # Ctrl+I is often the shortcut for Import Media
            
            time.sleep(1)
            
            # If Ctrl+I didn't work, try the menu path
            # Check if import dialog opened by looking for "Import Media" window
            import_windows = pyautogui.getWindowsWithTitle('Import Media')
            if not import_windows:
                import_windows = pyautogui.getWindowsWithTitle('Open')
            
            if not import_windows:
                # Try the menu path: File > Import > Media
                pyautogui.hotkey('alt', 'f')  # Open File menu
                time.sleep(0.5)
                pyautogui.press('i')  # Import submenu
                time.sleep(0.5)
                pyautogui.press('m')  # Media option
                time.sleep(1)
            
            self.status_label.config(text="Camtasia ready for import!")
            
            if self.on_status_change:
                self.on_status_change("Camtasia opened with Import Media dialog")
            
            messagebox.showinfo(
                "Camtasia Ready",
                "Camtasia has been opened with a new project.\n\n"
                "The Import Media dialog should now be open.\n"
                "Navigate to your screenshots folder and select your images."
            )
            
        except Exception as e:
            self.status_label.config(text=f"Error: {e}")
            messagebox.showerror(
                "Automation Error",
                f"An error occurred during automation:\n{e}\n\n"
                "Please manually:\n"
                "1. Open Camtasia\n"
                "2. Create a new project (Ctrl+N)\n"
                "3. Go to File > Import > Media"
            )


class VideoPanel(ttk.LabelFrame):
    """Panel for video generation options."""
    
    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Video Generation", padding=10)
        self.on_status_change = on_status_change
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the video panel UI."""
        info_label = ttk.Label(
            self,
            text="Create videos from your captured screenshots with narration and transitions.",
            wraplength=400
        )
        info_label.pack(pady=10)
        
        # Quick video (no narration)
        ttk.Button(
            self,
            text="Quick Video (No Narration)",
            command=self._create_quick_video,
            style='Accent.TButton'
        ).pack(pady=5, fill=tk.X)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Quick video from screenshots with editor
        ttk.Button(
            self,
            text="Create Video with Narration Editor",
            command=self._create_video_from_screenshots
        ).pack(pady=5, fill=tk.X)
        
        # Open visual editor
        ttk.Button(
            self,
            text="Open Visual Narration Editor",
            command=self._open_video_editor
        ).pack(pady=5, fill=tk.X)
        
        # Load project
        ttk.Button(
            self,
            text="Load Existing Project",
            command=self._load_project
        ).pack(pady=5, fill=tk.X)
        
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Camtasia export
        ttk.Label(self, text="Camtasia Integration:", font=('Segoe UI', 9, 'bold')).pack(anchor=tk.W)
        
        ttk.Button(
            self,
            text="Export to Camtasia Project",
            command=self._export_to_camtasia
        ).pack(pady=5, fill=tk.X)
        
    def _export_to_camtasia(self):
        """Export images to Camtasia project."""
        CamtasiaExportDialog(self.winfo_toplevel(), self.on_status_change)
        
    def _create_quick_video(self):
        """Create a quick video without narration using a dialog."""
        QuickVideoDialog(self.winfo_toplevel(), self.on_status_change)
        
    def _create_video_from_screenshots(self):
        """Create video from a screenshots folder."""
        dir_path = filedialog.askdirectory(
            title="Select Screenshots Folder"
        )
        if dir_path:
            self._launch_editor_with_path(dir_path)
            
    def _open_video_editor(self):
        """Open the video editor GUI."""
        import subprocess
        try:
            subprocess.Popen([sys.executable, "video_editor_gui.py"], cwd=str(Path(__file__).parent))
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video editor:\n{e}")
            
    def _load_project(self):
        """Load a saved video project."""
        file_path = filedialog.askopenfilename(
            title="Select Project File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self._launch_editor_with_project(file_path)
            
    def _launch_editor_with_path(self, path: str):
        """Launch editor with specific path."""
        import subprocess
        try:
            subprocess.Popen(
                [sys.executable, "video_editor_gui.py", "-i", path], 
                cwd=str(Path(__file__).parent)
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video editor:\n{e}")
            
    def _launch_editor_with_project(self, project_path: str):
        """Launch editor with a project file."""
        import subprocess
        try:
            subprocess.Popen(
                [sys.executable, "video_editor_gui.py", "-p", project_path], 
                cwd=str(Path(__file__).parent)
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video editor:\n{e}")


class ScreenshotAutomaterGUI:
    """Main GUI application for Screenshot Automater."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Screenshot Automater")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)
        
        # Set icon if available
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        
        # Configure styles
        self._setup_styles()
        
        # Set up UI
        self._setup_ui()
        self._setup_menu()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        
        # Try to use a modern theme
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'clam' in available_themes:
            style.theme_use('clam')
            
        # Custom accent button style
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'))
        
    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Screenshots Folder...", command=self._open_screenshots_folder)
        file_menu.add_command(label="Open Workflow...", command=self._open_workflow)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Video Editor", command=self._open_video_editor)
        tools_menu.add_separator()
        tools_menu.add_command(label="Refresh Monitors", command=self.monitor_display.refresh_monitors)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="User Guide", command=self._show_help)
        
    def _setup_ui(self):
        """Set up the main UI."""
        # Main container with notebook for tabs
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(
            title_frame,
            text="Screenshot Automater",
            font=('Segoe UI', 18, 'bold')
        ).pack(side=tk.LEFT)
        
        ttk.Label(
            title_frame,
            text="Capture screenshots on click & replay workflows",
            font=('Segoe UI', 10),
            foreground='gray'
        ).pack(side=tk.LEFT, padx=15)
        
        # Notebook with tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Record tab
        record_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(record_frame, text="  Record  ")
        
        self.record_panel = RecordPanel(record_frame, on_status_change=self._update_status)
        self.record_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Monitor display in record tab
        self.monitor_display = MonitorDisplay(record_frame)
        self.monitor_display.pack(fill=tk.X)
        
        # Replay tab
        replay_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(replay_frame, text="  Replay  ")
        
        self.replay_panel = ReplayPanel(replay_frame, on_status_change=self._update_status)
        self.replay_panel.pack(fill=tk.BOTH, expand=True)
        
        # Video tab
        video_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(video_frame, text="  Video  ")
        
        self.video_panel = VideoPanel(video_frame, on_status_change=self._update_status)
        self.video_panel.pack(fill=tk.X)
        
        # Video info in video tab
        video_info_frame = ttk.LabelFrame(video_frame, text="Video Features", padding=10)
        video_info_frame.pack(fill=tk.X, pady=10)
        
        features = [
            "• Multiple image formats: PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP",
            "• Custom resolutions: 1080p, 720p, 4K, or custom",
            "• Text-to-Speech narration with multiple voices",
            "• Transitions: None, Fade, Crossfade, Slide (left/right/up/down)",
            "• Per-image settings: Custom duration and transitions",
            "• Project saving: Save configurations for later editing"
        ]
        
        for feature in features:
            ttk.Label(video_info_frame, text=feature).pack(anchor=tk.W)
        
        # Status bar
        self.status_bar = StatusBar(main_frame)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))
        
    def _update_status(self, message: str):
        """Update the status bar."""
        self.status_bar.set_status(message)
        
    def _open_screenshots_folder(self):
        """Open a screenshots folder."""
        dir_path = filedialog.askdirectory(title="Select Screenshots Folder")
        if dir_path:
            # Check for workflow.json
            workflow_path = Path(dir_path) / "workflow.json"
            if workflow_path.exists():
                self.notebook.select(1)  # Switch to Replay tab
                self.replay_panel.workflow_var.set(str(workflow_path))
                self.replay_panel._load_workflow_info(str(workflow_path))
            else:
                messagebox.showinfo(
                    "Folder Selected",
                    f"Selected folder: {dir_path}\n\nNo workflow.json found in this folder."
                )
                
    def _open_workflow(self):
        """Open a workflow file."""
        file_path = filedialog.askopenfilename(
            title="Select Workflow File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            self.notebook.select(1)  # Switch to Replay tab
            self.replay_panel.workflow_var.set(file_path)
            self.replay_panel._load_workflow_info(file_path)
            
    def _open_video_editor(self):
        """Open the video editor."""
        try:
            from video_editor_gui import VideoEditorGUI
            editor = VideoEditorGUI()
            editor.run()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video editor:\n{e}")
            
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About Screenshot Automater",
            "Screenshot Automater\n\n"
            "A Python application that captures screenshots every time you click "
            "and can replay recorded workflows.\n\n"
            "Features:\n"
            "• Click-to-Capture screenshots\n"
            "• Workflow recording and replay\n"
            "• Video generation with narration\n"
            "• Custom naming patterns\n\n"
            "Version 1.0"
        )
        
    def _show_help(self):
        """Show help/user guide."""
        help_text = """Screenshot Automater - User Guide

RECORDING:
1. Select output directory and naming pattern
2. Choose image format (PNG recommended)
3. Click "Start Recording"
4. Click anywhere on screen to capture screenshots
5. Click "Stop Recording" when done

REPLAY:
1. Load a workflow.json file
2. Set output directory (optional)
3. Adjust delay settings if needed
4. Click "Start Replay"
5. Move mouse to corner to abort

VIDEO GENERATION:
1. Use the Video tab to create videos
2. Open Visual Narration Editor for advanced features
3. Add narration text for each image
4. Choose transitions and durations
5. Generate MP4 video

TIPS:
• Use {count} in naming pattern for unique filenames
• Create separate folders for different workflows
• Increase min-delay for slower systems
• Record and replay at same resolution for best results"""
        
        # Create help window
        help_window = tk.Toplevel(self.root)
        help_window.title("User Guide")
        help_window.geometry("500x500")
        
        text = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", help_text)
        text.config(state=tk.DISABLED)
        
        ttk.Button(help_window, text="Close", command=help_window.destroy).pack(pady=10)
        
    def _on_close(self):
        """Handle window close."""
        # Check if recording is in progress
        if self.record_panel.is_recording:
            result = messagebox.askyesno(
                "Recording in Progress",
                "Recording is still in progress. Stop recording and exit?"
            )
            if result:
                self.record_panel._stop_recording()
            else:
                return
                
        self.root.destroy()
        
    def run(self):
        """Start the GUI application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    app = ScreenshotAutomaterGUI()
    app.run()


if __name__ == "__main__":
    main()
