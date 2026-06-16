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

try:
    from storyboard_generator import StoryboardGenerator, DEFAULT_TEMPLATE
    HAS_STORYBOARD = True
except ImportError:
    HAS_STORYBOARD = False


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
                 filter_images: bool = False, show_count: bool = True, 
                 on_file_selected: Callable = None, selectable: bool = False):
        super().__init__(parent, text=title, padding=5)
        self.filter_images = filter_images
        self.show_count = show_count
        self.current_path = None
        self.on_file_selected = on_file_selected
        self.selectable = selectable
        
        # Header with count
        if show_count:
            self.count_label = ttk.Label(self, text="No folder selected", foreground='gray')
            self.count_label.pack(anchor=tk.W)
        
        # File listbox with scrollbar
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(3, 0))
        
        selectmode = tk.SINGLE if selectable else tk.EXTENDED
        self.file_listbox = tk.Listbox(
            list_frame, 
            height=height,
            font=('Consolas', 9),
            selectmode=selectmode,
            activestyle='none'
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        self.file_listbox.config(yscrollcommand=scrollbar.set)
        
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to select file
        if selectable:
            self.file_listbox.bind('<Double-Button-1>', self._on_file_double_click)
        
        # Store file mapping for retrieval
        self._file_map = {}
        
    def set_folder(self, folder_path: str):
        """Update the file list for the given folder."""
        self.current_path = folder_path
        self.file_listbox.delete(0, tk.END)
        self._file_map.clear()
        
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
            
            for idx, f in enumerate(files):
                # Format: filename (size)
                size = f.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                
                display_text = f"{f.name}  ({size_str})"
                self.file_listbox.insert(tk.END, display_text)
                self._file_map[idx] = str(f)
            
            if self.show_count:
                if self.filter_images:
                    self.count_label.config(text=f"{len(files)} image(s) found")
                else:
                    self.count_label.config(text=f"{len(files)} file(s) found")
                    
        except Exception as e:
            if self.show_count:
                self.count_label.config(text=f"Error: {e}")
    
    def _on_file_double_click(self, event):
        """Handle double-click on a file."""
        selection = self.file_listbox.curselection()
        if selection and self.on_file_selected:
            idx = selection[0]
            file_path = self._file_map.get(idx)
            if file_path:
                self.on_file_selected(file_path)
    
    def get_selected_file(self) -> Optional[str]:
        """Get the currently selected file path."""
        selection = self.file_listbox.curselection()
        if selection:
            return self._file_map.get(selection[0])
        return None
    
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
            title="Select Output Directory",
            initialdir="."
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


class StoryboardPanel(ttk.LabelFrame):
    """Panel for generating PowerPoint storyboards from captured screenshots."""

    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Storyboard Generator", padding=10)
        self.on_status_change = on_status_change
        self.is_generating = False
        self._setup_ui()

    def _setup_ui(self):
        """Build the storyboard panel UI."""
        # ── Screenshots folder ─────────────────────────────────────────
        folder_frame = ttk.Frame(self)
        folder_frame.pack(fill=tk.X, pady=4)
        ttk.Label(folder_frame, text="Screenshots Folder:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.folder_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.folder_var).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Button(folder_frame, text="Browse…", command=self._browse_folder).pack(side=tk.LEFT)

        # Image preview list
        self.images_preview = FolderFilesPreview(
            self, title="Images to Include", height=6, filter_images=True
        )
        self.images_preview.pack(fill=tk.X, pady=(0, 6))
        self.folder_var.trace_add("write", lambda *_: self.images_preview.set_folder(self.folder_var.get()))

        # ── Video title ────────────────────────────────────────────────
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, pady=4)
        ttk.Label(title_frame, text="Video Title:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.title_var = tk.StringVar(value="Video Title")
        ttk.Entry(title_frame, textvariable=self.title_var).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )

        # ── Narration template (speaker notes) ───────────────────────
        narration_frame = ttk.Frame(self)
        narration_frame.pack(fill=tk.X, pady=4)
        ttk.Label(narration_frame, text="Narration Template:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.narration_var = tk.StringVar(
            value="Step {step}: [Add narration for this step]\\nImage path: {file_path}"
        )
        ttk.Entry(narration_frame, textvariable=self.narration_var).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Label(
            self,
            text=(
                "Speaker notes become narration. Tokens: {step}, {file_name}, "
                "{file_stem}, {file_path}, {folder_path}"
            ),
            font=("Segoe UI", 8), foreground="gray"
        ).pack(anchor=tk.W)

        # ── Template path ──────────────────────────────────────────────
        tpl_frame = ttk.Frame(self)
        tpl_frame.pack(fill=tk.X, pady=4)
        ttk.Label(tpl_frame, text="Template (optional):", width=18, anchor=tk.W).pack(side=tk.LEFT)
        default_tpl = DEFAULT_TEMPLATE if HAS_STORYBOARD else ""
        self.template_var = tk.StringVar(value=default_tpl if Path(default_tpl).exists() else "")
        ttk.Entry(tpl_frame, textvariable=self.template_var).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Button(tpl_frame, text="Browse…", command=self._browse_template_show).pack(side=tk.LEFT)
        ttk.Label(
            self, text="Leave blank to use the default Progress Software template (if available).",
            font=("Segoe UI", 8), foreground="gray"
        ).pack(anchor=tk.W)
        
        # Template file browser
        self.template_preview = FolderFilesPreview(
            self, title="Template Files", height=3, 
            on_file_selected=self._select_template_file,
            selectable=True
        )
        self.template_preview.pack(fill=tk.X, pady=(0, 4))

        # ── Output PPTX path ───────────────────────────────────────────
        out_frame = ttk.Frame(self)
        out_frame.pack(fill=tk.X, pady=4)
        ttk.Label(out_frame, text="Output File (.pptx):", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.output_var).pack(
            side=tk.LEFT, padx=5, fill=tk.X, expand=True
        )
        ttk.Button(out_frame, text="Browse…", command=self._browse_output_show).pack(side=tk.LEFT)
        
        # Output file browser
        self.output_preview = FolderFilesPreview(
            self, title="Output Files in Folder", height=3, 
            on_file_selected=self._select_output_file,
            selectable=True
        )
        self.output_preview.pack(fill=tk.X, pady=(0, 4))
        self.output_var.trace_add("write", self._update_output_preview)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # ── Progress bar & status ──────────────────────────────────────
        self.progress_label = ttk.Label(self, text="Ready")
        self.progress_label.pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(self, mode="determinate", length=400)
        self.progress_bar.pack(fill=tk.X, pady=(2, 8))

        # ── Log output ─────────────────────────────────────────────────
        log_frame = ttk.Frame(self)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self.log_text = tk.Text(log_frame, height=6, state=tk.DISABLED,
                                font=("Consolas", 9), wrap=tk.WORD)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Buttons ────────────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=4)
        self.generate_btn = ttk.Button(
            btn_frame, text="Generate Storyboard",
            command=self._generate, style="Accent.TButton"
        )
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Output Folder",
                   command=self._open_output_folder).pack(side=tk.LEFT, padx=5)

    # ── Browse helpers ─────────────────────────────────────────────────

    def _browse_folder(self):
        path = filedialog.askdirectory(
            title="Select Screenshots Folder",
            initialdir=self.folder_var.get() or "."
        )
        if path:
            self.folder_var.set(path)
            # Explicitly update the preview
            self.images_preview.set_folder(path)
            # Auto-suggest output path from folder name
            if not self.output_var.get():
                suggested = Path(path) / f"{Path(path).name}_storyboard.pptx"
                self.output_var.set(str(suggested))

    def _browse_template_show(self):
        """Show template file browser."""
        current_path = self.template_var.get()
        start_dir = str(Path(current_path).parent) if current_path and Path(current_path).exists() else "."
        
        path = filedialog.askopenfilename(
            title="Select Storyboard Template",
            filetypes=[("PowerPoint files", "*.pptx *.ppt"), ("All files", "*.*")],
            initialdir=start_dir,
        )
        if path:
            self.template_var.set(path)
            # Update the preview to show files in that directory
            self.template_preview.set_folder(str(Path(path).parent))
    
    def _select_template_file(self, file_path: str):
        """Called when a template file is double-clicked in the preview."""
        self.template_var.set(file_path)
    
    def _browse_output_show(self):
        """Show output file browser."""
        initial = self.output_var.get()
        start_dir = str(Path(initial).parent) if initial and Path(initial).parent.exists() else "."
        
        path = filedialog.asksaveasfilename(
            title="Save Storyboard As",
            defaultextension=".pptx",
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")],
            initialdir=start_dir,
            initialfile=Path(initial).name if initial else "storyboard.pptx",
        )
        if path:
            self.output_var.set(path)
            # Update the preview to show files in that directory
            self.output_preview.set_folder(str(Path(path).parent))
    
    def _select_output_file(self, file_path: str):
        """Called when an output file is double-clicked in the preview."""
        self.output_var.set(file_path)
    
    def _update_output_preview(self, *args):
        """Update the output file preview when the path changes."""
        path = self.output_var.get()
        if path:
            parent = Path(path).parent
            if parent.exists():
                self.output_preview.set_folder(str(parent))
    
    def _update_output_preview(self, *args):
        """Update the output file preview when the path changes."""
        path = self.output_var.get()
        if path:
            parent = Path(path).parent
            if parent.exists():
                self.output_preview.set_folder(str(parent))

    # ── Log helper ─────────────────────────────────────────────────────

    def _log(self, text: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    # ── Generation ─────────────────────────────────────────────────────

    def _generate(self):
        if self.is_generating:
            return

        if not HAS_STORYBOARD:
            messagebox.showerror(
                "Missing Dependency",
                "python-pptx is not installed.\n\nRun: pip install python-pptx"
            )
            return

        folder = self.folder_var.get().strip()
        if not folder or not Path(folder).is_dir():
            messagebox.showwarning("No Folder", "Please select a valid screenshots folder.")
            return

        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning("No Output", "Please specify an output .pptx file path.")
            return

        self.is_generating = True
        self.generate_btn.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self._clear_log()

        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()

    def _run_generation(self):
        """Run storyboard generation in a background thread."""
        try:
            tpl = self.template_var.get().strip() or None
            generator = StoryboardGenerator(
                template_path=tpl,
                progress_callback=self._on_progress,
            )
            count = generator.generate(
                screenshots_folder=self.folder_var.get(),
                output_path=self.output_var.get(),
                video_title=self.title_var.get().strip() or "Video Title",
                narration_template=self.narration_var.get().strip()
                or "Step {step}: [Add narration for this step]\\nImage path: {file_path}",
            )
            self.after(10, lambda: self._generation_complete(count))
        except Exception as exc:
            self.after(10, lambda: self._generation_error(str(exc)))

    def _on_progress(self, msg: str, current: int, total: int):
        """Called from the background thread — update UI via after()."""
        pct = int(current / total * 100) if total else 0
        self.after(10, lambda m=msg, p=pct: self._update_progress(m, p))

    def _update_progress(self, msg: str, pct: int):
        self.progress_label.config(text=msg)
        self.progress_bar["value"] = pct
        self._log(msg)
        if self.on_status_change:
            self.on_status_change(msg)

    def _generation_complete(self, count: int):
        self.is_generating = False
        self.generate_btn.config(state=tk.NORMAL)
        self.progress_bar["value"] = 100
        msg = f"Done — {count} screenshot slide(s) created."
        self.progress_label.config(text=msg)
        self._log(msg)
        if self.on_status_change:
            self.on_status_change(msg)
        messagebox.showinfo(
            "Storyboard Generated",
            f"Created {count} screenshot slides.\n\nSaved to:\n{self.output_var.get()}"
        )

    def _generation_error(self, error: str):
        self.is_generating = False
        self.generate_btn.config(state=tk.NORMAL)
        self.progress_label.config(text=f"Error: {error}")
        self._log(f"ERROR: {error}")
        if self.on_status_change:
            self.on_status_change(f"Storyboard error: {error}")
        messagebox.showerror("Generation Failed", f"Storyboard generation failed:\n\n{error}")

    def _open_output_folder(self):
        """Open the folder containing the output file."""
        output = self.output_var.get().strip()
        folder = Path(output).parent if output else Path(".")
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(folder)], check=True)
            else:
                import subprocess
                subprocess.run(["xdg-open", str(folder)], check=True)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open folder: {exc}")


class ScreenshotAutomaterGUI:
    
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

        # Storyboard tab
        storyboard_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(storyboard_frame, text="  Storyboard  ")

        self.storyboard_panel = StoryboardPanel(
            storyboard_frame, on_status_change=self._update_status
        )
        self.storyboard_panel.pack(fill=tk.BOTH, expand=True)

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
