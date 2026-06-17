"""
Screenshot Automater GUI - Visual interface for recording and replaying screenshots
"""

import os
import sys
import json
import threading
import shutil
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Callable

from PIL import Image, ImageTk

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

try:
    from camtasia_generator import (
        create_camtasia_project,
        create_audiate_script_from_pptx,
    )
    HAS_CAMTASIA = True
except ImportError:
    HAS_CAMTASIA = False

try:
    from ppt_to_video import PPTToVideoConverter
    HAS_PPT_TO_VIDEO = True
except ImportError:
    HAS_PPT_TO_VIDEO = False


def _open_path_with_system_app(path: Path):
    """Open a file or folder using the default OS handler."""
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        import subprocess
        subprocess.run(["open", str(path)], check=True)
    else:
        import subprocess
        subprocess.run(["xdg-open", str(path)], check=True)


def _open_output_file_or_folder(path_text: str):
    """Open output file if present; otherwise open its parent folder when available."""
    target = Path(path_text).expanduser()
    if target.exists():
        _open_path_with_system_app(target)
        return

    parent = target.parent
    if parent.exists():
        _open_path_with_system_app(parent)
        return

    raise FileNotFoundError(f"Output path not found: {target}")


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
        self.current_monitor_number = None
        
        self.monitor_text = tk.Text(self, height=4, width=50, state=tk.DISABLED,
                                     font=('Consolas', 9))
        self.monitor_text.pack(fill=tk.BOTH, expand=True)
        
        self.refresh_btn = ttk.Button(self, text="Refresh", command=self.refresh_monitors)
        self.refresh_btn.pack(pady=(5, 0))
        
        self.refresh_monitors()

    def highlight_monitor(self, monitor_number: Optional[int]):
        """Highlight the monitor currently being recorded."""
        self.current_monitor_number = monitor_number
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
                marker = "▶ " if i == self.current_monitor_number else "  "
                info = f"{marker}{i}. {name}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y}){primary}\n"
                self.monitor_text.insert(tk.END, info)
        except Exception as e:
            self.monitor_text.insert(tk.END, f"Error detecting monitors: {e}")
            
        self.monitor_text.config(state=tk.DISABLED)

    def get_default_monitor_number(self) -> Optional[int]:
        """Return the primary monitor number, or the first monitor if no primary is reported."""
        try:
            monitors = get_monitors()
            if not monitors:
                return None

            for i, monitor in enumerate(monitors, 1):
                if monitor.is_primary:
                    return i

            return 1
        except Exception:
            return None

    def get_monitor_by_number(self, monitor_number: Optional[int]):
        """Return the screeninfo monitor object for a given monitor number."""
        if not monitor_number:
            return None

        try:
            monitors = get_monitors()
            if 0 < monitor_number <= len(monitors):
                return monitors[monitor_number - 1]
        except Exception:
            return None

        return None


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
    
    def __init__(self, parent, on_status_change: Callable = None, on_monitor_change: Callable = None):
        super().__init__(parent, text="Recording", padding=10)
        self.on_status_change = on_status_change
        self.on_monitor_change = on_monitor_change
        self.automater: Optional[ScreenshotAutomater] = None
        self.is_recording = False
        self.listener = None
        self.click_count = 0
        self.monitor_display: Optional[MonitorDisplay] = None
        self._preview_photo = None
        self._preview_refresh_job = None
        
        self._setup_ui()

    def set_monitor_display(self, monitor_display: MonitorDisplay):
        """Attach the shared monitor display so the preview can use its selection."""
        self.monitor_display = monitor_display
        
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

        # Active monitor indicator
        monitor_frame = ttk.Frame(self)
        monitor_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(monitor_frame, text="Recording Screen:").pack(side=tk.LEFT)
        self.monitor_status_label = ttk.Label(monitor_frame, text="None", foreground='gray')
        self.monitor_status_label.pack(side=tk.LEFT, padx=5)

        # Visual preview of the recording screen
        preview_frame = ttk.Frame(self)
        preview_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(preview_frame, text="Recording Screen Preview:").pack(anchor=tk.W)
        self.preview_label = ttk.Label(preview_frame, text="No preview available", padding=4)
        self.preview_label.pack(anchor=tk.W, pady=(4, 0))

        self.preview_canvas = tk.Label(preview_frame, borderwidth=1, relief=tk.SOLID, background='white')
        self.preview_canvas.pack(fill=tk.X, pady=(4, 0))
        self.preview_canvas.bind("<Button-1>", lambda _event: self.refresh_recording_preview())

        ttk.Label(
            preview_frame,
            text="Click the preview to refresh it.",
            font=('Segoe UI', 8),
            foreground='gray'
        ).pack(anchor=tk.W, pady=(2, 0))
        
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

        self.pause_btn = ttk.Button(
            btn_frame,
            text="Pause Recording",
            command=self._pause_or_resume_recording,
            state=tk.DISABLED
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

    def refresh_recording_preview(self):
        """Capture and display a thumbnail of the monitor that will be recorded."""
        monitor_display = self.monitor_display
        if not monitor_display:
            self.preview_label.config(text="Preview unavailable")
            self.preview_canvas.config(image='', text='No preview available')
            self._preview_photo = None
            return

        monitor_number = monitor_display.current_monitor_number or monitor_display.get_default_monitor_number()
        monitor = monitor_display.get_monitor_by_number(monitor_number)
        if not monitor:
            self.preview_label.config(text="Preview unavailable")
            self.preview_canvas.config(image='', text='No preview available')
            self._preview_photo = None
            return

        try:
            screenshot = pyautogui.screenshot(region=(monitor.x, monitor.y, monitor.width, monitor.height))
            thumbnail = screenshot.copy()
            thumbnail.thumbnail((360, 200))
            self._preview_photo = ImageTk.PhotoImage(thumbnail)

            monitor_name = monitor.name or f"Display {monitor_number}"
            primary = " (primary)" if monitor.is_primary else ""
            self.preview_label.config(
                text=f"{monitor_number}. {monitor_name}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y}){primary}"
            )
            self.preview_canvas.config(image=self._preview_photo, text='')
        except Exception as exc:
            self.preview_label.config(text=f"Preview unavailable: {exc}")
            self.preview_canvas.config(image='', text='No preview available')
            self._preview_photo = None

    def _schedule_preview_refresh(self):
        """Refresh the monitor preview periodically while recording is active."""
        if not self.is_recording:
            self._preview_refresh_job = None
            return

        self.refresh_recording_preview()
        self._preview_refresh_job = self.after(3000, self._schedule_preview_refresh)

    def _cancel_preview_refresh(self):
        """Stop the periodic preview refresh loop."""
        if self._preview_refresh_job is not None:
            self.after_cancel(self._preview_refresh_job)
            self._preview_refresh_job = None

    def _set_monitor_status(self, text: str, color: str = 'gray'):
        """Update the active monitor indicator."""
        self.monitor_status_label.config(text=text, foreground=color)

    def _set_recording_indicator(self, state: str):
        """Update the recording state indicator."""
        if state == 'recording':
            self.indicator_canvas.itemconfig(self.indicator_circle, fill='red', outline='darkred')
            self.indicator_label.config(text="Recording")
        elif state == 'paused':
            self.indicator_canvas.itemconfig(self.indicator_circle, fill='gold', outline='darkgoldenrod')
            self.indicator_label.config(text="Paused")
        else:
            self.indicator_canvas.itemconfig(self.indicator_circle, fill='gray', outline='darkgray')
            self.indicator_label.config(text="Not Recording")

    def _update_monitor_display(self, monitor_info: Optional[dict]):
        """Update the monitor label and the shared monitor list."""
        if not monitor_info:
            self._set_monitor_status("None", 'gray')
            if self.on_monitor_change:
                self.on_monitor_change(None)
            self.refresh_recording_preview()
            return

        label = monitor_info.get('info', 'Unknown monitor')
        self._set_monitor_status(label, 'black')
        if self.on_monitor_change:
            self.on_monitor_change(monitor_info.get('number'))
        self.refresh_recording_preview()
        
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
        self.automater.is_recording = True
        self.automater.is_paused = False
        self.automater.click_count = 0
        self.automater.workflow = []
        
        self.is_recording = True
        self.click_count = 0
        self.automater.session_start_time = datetime.now().timestamp()
        
        # Update UI
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL, text="Pause Recording")
        self.output_dir_entry.config(state=tk.DISABLED)
        
        # Update indicator
        self._set_recording_indicator('recording')
        self._set_monitor_status("Waiting for the first click...", 'gray')
        self.refresh_recording_preview()
        self._schedule_preview_refresh()
        
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

        self._cancel_preview_refresh()

        # Save workflow without the CLI post-capture prompt
        if self.automater:
            self.automater.stop_recording(prompt_user=False)
            
        # Update UI
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED, text="Pause Recording")
        self.output_dir_entry.config(state=tk.NORMAL)
        
        # Update indicator
        self._set_recording_indicator('stopped')
        self._set_monitor_status("None", 'gray')
        if self.on_monitor_change:
            self.on_monitor_change(None)
        
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

    def _pause_or_resume_recording(self):
        """Toggle recording pause state."""
        if not self.is_recording or not self.automater:
            return

        if self.automater.is_paused:
            self.automater.resume_recording()
            self.pause_btn.config(text="Pause Recording")
            self._set_recording_indicator('recording')
            if self.on_status_change:
                self.on_status_change("Recording resumed - Click anywhere to capture")
        else:
            self.automater.pause_recording()
            self.pause_btn.config(text="Resume Recording")
            self._set_recording_indicator('paused')
            if self.on_status_change:
                self.on_status_change("Recording paused - Clicks are ignored until resumed")
            
    def _on_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click events."""
        if not pressed or button != Button.left:
            return
            
        if not self.is_recording or not self.automater:
            return

        if self.automater.is_paused:
            return
            
        # Record click and capture screenshot
        self.automater._on_click(x, y, button, pressed)
        self.click_count = self.automater.click_count

        monitor_info = self.automater._get_monitor_info(x, y)
        
        # Update UI from main thread
        self.after(10, self._update_stats)
        self.after(10, lambda: self.last_capture_label.config(
            text=f"Last: ({x}, {y}) at {datetime.now().strftime('%H:%M:%S')}"
        ))
        self.after(10, lambda info=monitor_info: self._update_monitor_display(info))
        
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
        self.generate_buttons = []
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

        # Top actions stay visible even when the panel is long
        top_actions = ttk.Frame(self)
        top_actions.pack(fill=tk.X, pady=(0, 6))
        self.generate_btn_top = ttk.Button(
            top_actions,
            text="Generate Storyboard",
            command=self._generate,
            style="Accent.TButton"
        )
        self.generate_btn_top.pack(side=tk.LEFT, padx=(0, 5))
        self.generate_buttons.append(self.generate_btn_top)

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

        # ── Title Page Image ───────────────────────────────────────────
        if HAS_STORYBOARD:
            from storyboard_generator import (
                DEFAULT_TITLE_PAGE,
                DEFAULT_INTRO_MUSIC,
                DEFAULT_ENDING_SLIDE,
                DEFAULT_ENDING_NARRATION,
            )
            
            title_page_frame = ttk.Frame(self)
            title_page_frame.pack(fill=tk.X, pady=4)
            ttk.Label(title_page_frame, text="Title Page Image:", width=18, anchor=tk.W).pack(side=tk.LEFT)
            self.title_page_var = tk.StringVar(value=DEFAULT_TITLE_PAGE if Path(DEFAULT_TITLE_PAGE).exists() else "")
            ttk.Entry(title_page_frame, textvariable=self.title_page_var).pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True
            )
            ttk.Button(title_page_frame, text="Browse…", command=self._browse_title_page_show).pack(side=tk.LEFT)
            ttk.Label(
                self, text="Image for the title slide (video title will be overlaid on this image).",
                font=("Segoe UI", 8), foreground="gray"
            ).pack(anchor=tk.W)
            
            # Title page file browser
            self.title_page_preview = FolderFilesPreview(
                self, title="Title Page Image Files", height=3, filter_images=True,
                on_file_selected=self._select_title_page_file,
                selectable=True
            )
            self.title_page_preview.pack(fill=tk.X, pady=(0, 4))

            # ── Intro Music ────────────────────────────────────────────
            intro_music_frame = ttk.Frame(self)
            intro_music_frame.pack(fill=tk.X, pady=4)
            ttk.Label(intro_music_frame, text="Intro Music:", width=18, anchor=tk.W).pack(side=tk.LEFT)
            self.intro_music_var = tk.StringVar(value=DEFAULT_INTRO_MUSIC if Path(DEFAULT_INTRO_MUSIC).exists() else "")
            ttk.Entry(intro_music_frame, textvariable=self.intro_music_var).pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True
            )
            ttk.Button(intro_music_frame, text="Browse…", command=self._browse_intro_music_show).pack(side=tk.LEFT)
            ttk.Label(
                self, text="Audio embedded on the title slide (.wav or .mp3).",
                font=("Segoe UI", 8), foreground="gray"
            ).pack(anchor=tk.W)

            # ── Ending Slide Media ─────────────────────────────────────
            ending_slide_frame = ttk.Frame(self)
            ending_slide_frame.pack(fill=tk.X, pady=4)
            ttk.Label(ending_slide_frame, text="Ending Media:", width=18, anchor=tk.W).pack(side=tk.LEFT)
            self.ending_slide_var = tk.StringVar(value=DEFAULT_ENDING_SLIDE if Path(DEFAULT_ENDING_SLIDE).exists() else "")
            ttk.Entry(ending_slide_frame, textvariable=self.ending_slide_var).pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True
            )
            ttk.Button(ending_slide_frame, text="Browse…", command=self._browse_ending_slide_show).pack(side=tk.LEFT)
            ttk.Label(
                self, text="Final slide media (image or MP4 video).",
                font=("Segoe UI", 8), foreground="gray"
            ).pack(anchor=tk.W)
            
            # Ending slide file browser
            self.ending_slide_preview = FolderFilesPreview(
                self, title="Ending Media Files", height=3, filter_images=False,
                on_file_selected=self._select_ending_slide_file,
                selectable=True
            )
            self.ending_slide_preview.pack(fill=tk.X, pady=(0, 4))

            # ── Ending Slide Narration ─────────────────────────────────
            ending_narr_frame = ttk.Frame(self)
            ending_narr_frame.pack(fill=tk.X, pady=4)
            ttk.Label(ending_narr_frame, text="Ending Narration:", width=18, anchor=tk.W).pack(side=tk.LEFT)
            self.ending_narration_var = tk.StringVar(value=DEFAULT_ENDING_NARRATION)
            ttk.Entry(ending_narr_frame, textvariable=self.ending_narration_var).pack(
                side=tk.LEFT, padx=5, fill=tk.X, expand=True
            )
            ttk.Label(
                self, text="Narration text for the ending slide (speaker notes).",
                font=("Segoe UI", 8), foreground="gray"
            ).pack(anchor=tk.W)

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
        self.generate_buttons.append(self.generate_btn)
        ttk.Button(btn_frame, text="Open Output File",
                   command=self._open_output_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Open Output Folder",
                   command=self._open_output_folder).pack(side=tk.LEFT, padx=5)

    def _set_generate_buttons_state(self, state: str):
        """Keep all Generate buttons enabled/disabled together."""
        for btn in self.generate_buttons:
            btn.config(state=state)

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
    
    def _browse_title_page_show(self):
        """Show title page image file browser."""
        current_path = self.title_page_var.get() if hasattr(self, 'title_page_var') else ""
        start_dir = str(Path(current_path).parent) if current_path and Path(current_path).exists() else "."
        
        path = filedialog.askopenfilename(
            title="Select Title Page Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"), ("All files", "*.*")],
            initialdir=start_dir,
        )
        if path:
            self.title_page_var.set(path)
            # Update the preview to show files in that directory
            self.title_page_preview.set_folder(str(Path(path).parent))
    
    def _select_title_page_file(self, file_path: str):
        """Called when a title page image file is selected in the preview."""
        self.title_page_var.set(file_path)
    
    def _browse_ending_slide_show(self):
        """Show ending slide media file browser."""
        current_path = self.ending_slide_var.get() if hasattr(self, 'ending_slide_var') else ""
        start_dir = str(Path(current_path).parent) if current_path and Path(current_path).exists() else "."
        
        path = filedialog.askopenfilename(
            title="Select Ending Slide Media",
            filetypes=[
                ("Media files", "*.mp4 *.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                ("Video files", "*.mp4"),
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                ("All files", "*.*"),
            ],
            initialdir=start_dir,
        )
        if path:
            self.ending_slide_var.set(path)
            # Update the preview to show files in that directory
            self.ending_slide_preview.set_folder(str(Path(path).parent))

    def _browse_intro_music_show(self):
        """Show intro music file browser."""
        current_path = self.intro_music_var.get() if hasattr(self, 'intro_music_var') else ""
        start_dir = str(Path(current_path).parent) if current_path and Path(current_path).exists() else "."

        path = filedialog.askopenfilename(
            title="Select Intro Music",
            filetypes=[
                ("Audio files", "*.wav *.mp3"),
                ("WAV files", "*.wav"),
                ("MP3 files", "*.mp3"),
                ("All files", "*.*"),
            ],
            initialdir=start_dir,
        )
        if path:
            self.intro_music_var.set(path)
    
    def _select_ending_slide_file(self, file_path: str):
        """Called when an ending slide image file is selected in the preview."""
        self.ending_slide_var.set(file_path)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _log(self, message: str):
        """Append a timestamped line to the storyboard log panel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
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
        self._set_generate_buttons_state(tk.DISABLED)
        self.progress_bar["value"] = 0
        self._clear_log()

        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()

    def _run_generation(self):
        """Run storyboard generation in a background thread."""
        try:
            tpl = self.template_var.get().strip() or None
            
            # Get title page and ending slide values, or None to use defaults
            title_page = self.title_page_var.get().strip() if hasattr(self, 'title_page_var') else None
            intro_music = self.intro_music_var.get().strip() if hasattr(self, 'intro_music_var') else None
            ending_slide = self.ending_slide_var.get().strip() if hasattr(self, 'ending_slide_var') else None
            ending_narration = self.ending_narration_var.get().strip() if hasattr(self, 'ending_narration_var') else None
            
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
                title_page_image=title_page or None,
                intro_music_path=intro_music or None,
                ending_slide_image=ending_slide or None,
                ending_slide_narration=ending_narration or None,
            )
            self.after(10, lambda: self._generation_complete(count))
        except Exception as exc:
            error_msg = str(exc)
            self.after(10, lambda: self._generation_error(error_msg))


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
        self._set_generate_buttons_state(tk.NORMAL)
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
        if messagebox.askyesno("Open Output", "Open the generated storyboard file now?"):
            self._open_output_file()

    def _generation_error(self, error: str):
        self.is_generating = False
        self._set_generate_buttons_state(tk.NORMAL)
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
            _open_path_with_system_app(folder)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open folder: {exc}")

    def _open_output_file(self):
        """Open the storyboard output file, or its folder if file doesn't exist yet."""
        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning("Missing Output", "Please specify an output storyboard file path.")
            return
        try:
            _open_output_file_or_folder(output)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output: {exc}")


class CamtasiaPanel(ttk.LabelFrame):
    """Panel for building a Camtasia project directly from a PowerPoint file."""

    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Camtasia from PowerPoint", padding=10)
        self.on_status_change = on_status_change
        self.is_running = False
        self._setup_ui()

    def _setup_ui(self):
        pptx_frame = ttk.Frame(self)
        pptx_frame.pack(fill=tk.X, pady=4)
        ttk.Label(pptx_frame, text="PowerPoint File:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.pptx_var = tk.StringVar()
        ttk.Entry(pptx_frame, textvariable=self.pptx_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(pptx_frame, text="Browse...", command=self._browse_pptx).pack(side=tk.LEFT)
        self.pptx_var.trace_add("write", self._on_pptx_change)

        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.X, pady=4)
        ttk.Label(output_frame, text="Output Camtasia Project:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.output_project_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_project_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse...", command=self._browse_output_project).pack(side=tk.LEFT)

        assets_frame = ttk.Frame(self)
        assets_frame.pack(fill=tk.X, pady=4)
        ttk.Label(assets_frame, text="Export Slides Folder:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.assets_dir_var = tk.StringVar()
        ttk.Entry(assets_frame, textvariable=self.assets_dir_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(assets_frame, text="Browse...", command=self._browse_assets_dir).pack(side=tk.LEFT)

        voice_frame = ttk.Frame(self)
        voice_frame.pack(fill=tk.X, pady=4)
        ttk.Label(voice_frame, text="Default Narrator Voice:", width=20, anchor=tk.W).pack(side=tk.LEFT)
        self.voice_var = tk.StringVar(value="Andrew (US)")
        ttk.Entry(voice_frame, textvariable=self.voice_var, width=30).pack(side=tk.LEFT, padx=5)

        self.generate_script_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self,
            text="Also export Audiate script from speaker notes",
            variable=self.generate_script_var
        ).pack(anchor=tk.W, pady=(2, 6))

        self.build_btn = ttk.Button(
            self,
            text="Create Camtasia Project from PowerPoint",
            command=self._start_build,
            style='Accent.TButton'
        )
        self.build_btn.pack(anchor=tk.W, pady=(0, 6))

        self.open_output_btn = ttk.Button(
            self,
            text="Open Output Project",
            command=self._open_output_project
        )
        self.open_output_btn.pack(anchor=tk.W, pady=(0, 6))

        self.status_label = ttk.Label(self, text="Ready", foreground='gray')
        self.status_label.pack(anchor=tk.W)

        self.log_text = tk.Text(self, height=8, state=tk.DISABLED, font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    def _set_running(self, running: bool):
        self.is_running = running
        self.build_btn.config(state=tk.DISABLED if running else tk.NORMAL)

    def _set_status(self, text: str, color: str = 'gray'):
        self.status_label.config(text=text, foreground=color)
        if self.on_status_change:
            self.on_status_change(text)

    def _log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _browse_pptx(self):
        path = filedialog.askopenfilename(
            title="Select PowerPoint File",
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")],
            initialdir=Path(self.pptx_var.get()).parent if self.pptx_var.get() else ".",
        )
        if path:
            self.pptx_var.set(path)

    def _browse_output_project(self):
        initial = self.output_project_var.get()
        start_dir = str(Path(initial).parent) if initial and Path(initial).parent.exists() else "."
        path = filedialog.asksaveasfilename(
            title="Save Camtasia Project As",
            defaultextension=".tscproj",
            filetypes=[("Camtasia Project", "*.tscproj"), ("All files", "*.*")],
            initialdir=start_dir,
            initialfile=Path(initial).name if initial else "presentation_project.tscproj",
        )
        if path:
            self.output_project_var.set(path)

    def _browse_assets_dir(self):
        path = filedialog.askdirectory(title="Select Slide Export Folder", initialdir=self.assets_dir_var.get() or ".")
        if path:
            self.assets_dir_var.set(path)

    def _on_pptx_change(self, *_):
        pptx_path = self.pptx_var.get().strip()
        if not pptx_path:
            return

        pptx_file = Path(pptx_path)
        if not self.output_project_var.get().strip():
            self.output_project_var.set(str(pptx_file.with_suffix('.tscproj')))
        if not self.assets_dir_var.get().strip():
            self.assets_dir_var.set(str(pptx_file.with_name(f"{pptx_file.stem}_camtasia_assets")))

    def _start_build(self):
        if self.is_running:
            return
        if not HAS_CAMTASIA:
            messagebox.showerror("Missing Dependency", "camtasia_generator.py is required")
            return
        if not HAS_PPT_TO_VIDEO:
            messagebox.showerror("Missing Dependency", "ppt_to_video.py is required")
            return

        pptx_path = self.pptx_var.get().strip()
        if not pptx_path or not Path(pptx_path).exists():
            messagebox.showwarning("Missing Input", "Please select a valid PowerPoint file.")
            return

        output_project = self.output_project_var.get().strip()
        if not output_project:
            messagebox.showwarning("Missing Input", "Please select an output Camtasia project path.")
            return

        assets_dir = self.assets_dir_var.get().strip()
        if not assets_dir:
            messagebox.showwarning("Missing Input", "Please select a slide export folder.")
            return

        self._set_running(True)
        self._set_status("Building Camtasia project from PowerPoint...", 'black')
        thread = threading.Thread(target=self._run_build, daemon=True)
        thread.start()

    def _run_build(self):
        try:
            pptx_path = Path(self.pptx_var.get().strip())
            output_project = Path(self.output_project_var.get().strip())
            assets_dir = Path(self.assets_dir_var.get().strip())
            slides_dir = assets_dir / "slides"
            if slides_dir.exists():
                shutil.rmtree(slides_dir)
            slides_dir.mkdir(parents=True, exist_ok=True)

            converter = PPTToVideoConverter()
            self.after(10, lambda: self._log("Exporting slides from PowerPoint..."))
            converter.export_slides_as_images(str(pptx_path), str(slides_dir))

            self.after(10, lambda: self._log("Creating Camtasia project from exported slides..."))
            project_path = create_camtasia_project(
                image_folder=str(slides_dir),
                output_path=str(output_project),
            )

            script_path = None
            if self.generate_script_var.get():
                script_path = create_audiate_script_from_pptx(
                    str(pptx_path),
                    output_path=str(assets_dir / f"{pptx_path.stem}_audiate_script.csv"),
                    default_voice=self.voice_var.get().strip() or "Andrew (US)",
                )

            def _success():
                self._set_running(False)
                self._set_status(f"Camtasia project created: {project_path}", 'green')
                self._log(f"Camtasia project created: {project_path}")
                if script_path:
                    self._log(f"Audiate script created: {script_path}")
                message = f"Camtasia project created:\n\n{project_path}"
                if script_path:
                    message += f"\n\nAudiate script:\n{script_path}"
                messagebox.showinfo("Success", message)
                if messagebox.askyesno("Open Output", "Open the generated Camtasia project now?"):
                    self._open_output_project()

            self.after(10, _success)
        except Exception as exc:
            error_msg = str(exc)
            self.after(10, lambda: self._build_error(error_msg))

    def _build_error(self, error_message: str):
        self._set_running(False)
        self._set_status(f"Build failed: {error_message}", 'red')
        self._log(f"ERROR: {error_message}")
        messagebox.showerror("Error", f"Build failed:\n\n{error_message}")

    def _open_output_project(self):
        """Open Camtasia project output (or containing folder if not created yet)."""
        output = self.output_project_var.get().strip()
        if not output:
            messagebox.showwarning("Missing Output", "Please select an output Camtasia project path.")
            return
        try:
            _open_output_file_or_folder(output)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output: {exc}")


class PPTToMP4Panel(ttk.LabelFrame):
    """Panel for converting a PowerPoint file directly to MP4."""

    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="PowerPoint to MP4", padding=10)
        self.on_status_change = on_status_change
        self.is_running = False
        self.voice_ids = {}
        self._setup_ui()
        self._load_voices()

    def _setup_ui(self):
        pptx_frame = ttk.Frame(self)
        pptx_frame.pack(fill=tk.X, pady=4)
        ttk.Label(pptx_frame, text="PowerPoint File:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.pptx_var = tk.StringVar()
        ttk.Entry(pptx_frame, textvariable=self.pptx_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(pptx_frame, text="Browse...", command=self._browse_pptx).pack(side=tk.LEFT)
        self.pptx_var.trace_add("write", self._on_pptx_change)

        output_frame = ttk.Frame(self)
        output_frame.pack(fill=tk.X, pady=4)
        ttk.Label(output_frame, text="Output MP4:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(output_frame, text="Browse...", command=self._browse_output).pack(side=tk.LEFT)

        settings_row = ttk.Frame(self)
        settings_row.pack(fill=tk.X, pady=4)

        ttk.Label(settings_row, text="Resolution:").pack(side=tk.LEFT)
        self.resolution_var = tk.StringVar(value="1920x1080")
        ttk.Combobox(
            settings_row,
            textvariable=self.resolution_var,
            values=["1920x1080", "1280x720", "3840x2160", "1080x1920"],
            width=12,
            state="readonly"
        ).pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(settings_row, text="FPS:").pack(side=tk.LEFT)
        self.fps_var = tk.StringVar(value="30")
        ttk.Combobox(
            settings_row,
            textvariable=self.fps_var,
            values=["24", "30", "60"],
            width=6,
            state="readonly"
        ).pack(side=tk.LEFT, padx=(5, 15))

        ttk.Label(settings_row, text="Default slide sec:").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="5.0")
        ttk.Entry(settings_row, textvariable=self.duration_var, width=6).pack(side=tk.LEFT, padx=5)

        voice_row = ttk.Frame(self)
        voice_row.pack(fill=tk.X, pady=4)
        ttk.Label(voice_row, text="Narrator Voice:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.voice_var = tk.StringVar(value="")
        self.voice_combo = ttk.Combobox(voice_row, textvariable=self.voice_var, width=45, state="readonly")
        self.voice_combo.pack(side=tk.LEFT, padx=5)

        self.convert_btn = ttk.Button(
            self,
            text="Convert PowerPoint to MP4",
            command=self._start_convert,
            style='Accent.TButton'
        )
        self.convert_btn.pack(anchor=tk.W, pady=(6, 6))

        self.open_output_btn = ttk.Button(
            self,
            text="Open Output MP4",
            command=self._open_output_mp4,
        )
        self.open_output_btn.pack(anchor=tk.W, pady=(0, 6))

        self.progress_label = ttk.Label(self, text="Ready", foreground='gray')
        self.progress_label.pack(anchor=tk.W)
        self.progress_bar = ttk.Progressbar(self, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(4, 6))

        self.log_text = tk.Text(self, height=8, state=tk.DISABLED, font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _set_running(self, running: bool):
        self.is_running = running
        self.convert_btn.config(state=tk.DISABLED if running else tk.NORMAL)

    def _log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_status(self, text: str, color: str = 'gray'):
        self.progress_label.config(text=text, foreground=color)
        if self.on_status_change:
            self.on_status_change(text)

    def _browse_pptx(self):
        path = filedialog.askopenfilename(
            title="Select PowerPoint File",
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")],
            initialdir=Path(self.pptx_var.get()).parent if self.pptx_var.get() else ".",
        )
        if path:
            self.pptx_var.set(path)

    def _browse_output(self):
        initial = self.output_var.get()
        start_dir = str(Path(initial).parent) if initial and Path(initial).parent.exists() else "."
        path = filedialog.asksaveasfilename(
            title="Save MP4 As",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All files", "*.*")],
            initialdir=start_dir,
            initialfile=Path(initial).name if initial else "presentation.mp4",
        )
        if path:
            self.output_var.set(path)

    def _on_pptx_change(self, *_):
        pptx_path = self.pptx_var.get().strip()
        if pptx_path and not self.output_var.get().strip():
            self.output_var.set(str(Path(pptx_path).with_suffix('.mp4')))

    def _load_voices(self):
        if not HAS_PPT_TO_VIDEO:
            return

        try:
            converter = PPTToVideoConverter()
            voices = converter.list_voices()
            names = []
            for voice_id, voice_name in voices:
                display = voice_name.split(' - ')[0] if ' - ' in voice_name else voice_name
                names.append(display)
                self.voice_ids[display] = voice_id

            self.voice_combo['values'] = names
            if names:
                preferred = None
                for name in names:
                    lowered = name.lower()
                    if 'andrew' in lowered and 'us' in lowered:
                        preferred = name
                        break
                if preferred is None:
                    for name in names:
                        if 'andrew' in name.lower():
                            preferred = name
                            break
                self.voice_var.set(preferred or names[0])
        except Exception as exc:
            self._log(f"Could not load voices: {exc}")

    def _start_convert(self):
        if self.is_running:
            return
        if not HAS_PPT_TO_VIDEO:
            messagebox.showerror("Missing Dependency", "ppt_to_video.py is required")
            return

        pptx_path = self.pptx_var.get().strip()
        output_path = self.output_var.get().strip()
        if not pptx_path or not Path(pptx_path).exists():
            messagebox.showwarning("Missing Input", "Please select a valid PowerPoint file.")
            return
        if not output_path:
            messagebox.showwarning("Missing Input", "Please select an output MP4 path.")
            return

        self.progress_bar['value'] = 0
        self._set_running(True)
        self._set_status("Converting PowerPoint to MP4...", 'black')
        thread = threading.Thread(target=self._run_convert, daemon=True)
        thread.start()

    def _run_convert(self):
        try:
            width, height = map(int, self.resolution_var.get().lower().split('x'))
            converter = PPTToVideoConverter(
                output_resolution=(width, height),
                fps=int(self.fps_var.get()),
                default_slide_duration=float(self.duration_var.get()),
                progress_callback=self._on_progress,
            )

            voice_name = self.voice_var.get().strip()
            voice_id = self.voice_ids.get(voice_name)
            if voice_id:
                converter.set_voice(voice_id)

            result = converter.convert(self.pptx_var.get().strip(), self.output_var.get().strip())

            self.after(10, lambda: self._convert_success(result))
        except Exception as exc:
            error_msg = str(exc)
            self.after(10, lambda: self._convert_error(error_msg))

    def _on_progress(self, status: str, current: int, total: int):
        percent = int((current / total) * 100) if total else 0
        self.after(10, lambda: self._update_progress(status, percent))

    def _update_progress(self, status: str, percent: int):
        self.progress_bar['value'] = percent
        self._set_status(status, 'black')
        self._log(status)

    def _convert_success(self, output_path: str):
        self._set_running(False)
        self.progress_bar['value'] = 100
        self._set_status(f"MP4 created: {output_path}", 'green')
        self._log(f"MP4 created: {output_path}")
        self.output_var.set(output_path)
        messagebox.showinfo("Success", f"MP4 created:\n\n{output_path}")
        if messagebox.askyesno("Open Output", "Open the generated MP4 now?"):
            self._open_output_mp4()

    def _convert_error(self, error_message: str):
        self._set_running(False)
        self._set_status(f"Conversion failed: {error_message}", 'red')
        self._log(f"ERROR: {error_message}")
        messagebox.showerror("Error", f"Conversion failed:\n\n{error_message}")

    def _open_output_mp4(self):
        """Open MP4 output (or containing folder if not created yet)."""
        output = self.output_var.get().strip()
        if not output:
            messagebox.showwarning("Missing Output", "Please select an output MP4 path.")
            return
        try:
            _open_output_file_or_folder(output)
        except Exception as exc:
            messagebox.showerror("Error", f"Could not open output: {exc}")


class Microsoft365VideoPanel(ttk.LabelFrame):
    """Panel for launching Microsoft 365 cloud video creation from a PowerPoint file."""

    CREATE_URL = "https://m365.cloud.microsoft/create?auth=2"

    def __init__(self, parent, on_status_change: Callable = None):
        super().__init__(parent, text="Microsoft 365 Cloud Video", padding=10)
        self.on_status_change = on_status_change
        self._setup_ui()

    def _setup_ui(self):
        info = (
            "Upload a PowerPoint to Microsoft Create in your browser to generate cloud video."
        )
        ttk.Label(self, text=info, foreground='gray').pack(anchor=tk.W, pady=(0, 8))

        pptx_frame = ttk.Frame(self)
        pptx_frame.pack(fill=tk.X, pady=4)
        ttk.Label(pptx_frame, text="PowerPoint File:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.pptx_var = tk.StringVar()
        ttk.Entry(pptx_frame, textvariable=self.pptx_var).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(pptx_frame, text="Browse...", command=self._browse_pptx).pack(side=tk.LEFT)

        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(6, 4))
        ttk.Button(
            actions,
            text="Open Microsoft Create",
            command=self._open_create_page,
            style='Accent.TButton'
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="Copy PPTX Path", command=self._copy_pptx_path).pack(side=tk.LEFT, padx=6)
        ttk.Button(actions, text="Open PPTX Folder", command=self._open_pptx_folder).pack(side=tk.LEFT, padx=6)

        self.status_label = ttk.Label(self, text="Ready", foreground='gray')
        self.status_label.pack(anchor=tk.W, pady=(6, 0))

        self.log_text = tk.Text(self, height=8, state=tk.DISABLED, font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    def _set_status(self, text: str, color: str = 'gray'):
        self.status_label.config(text=text, foreground=color)
        if self.on_status_change:
            self.on_status_change(text)

    def _log(self, message: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _browse_pptx(self):
        path = filedialog.askopenfilename(
            title="Select PowerPoint File",
            filetypes=[("PowerPoint files", "*.pptx"), ("All files", "*.*")],
            initialdir=Path(self.pptx_var.get()).parent if self.pptx_var.get() else ".",
        )
        if path:
            self.pptx_var.set(path)
            self._set_status("PowerPoint selected", 'black')
            self._log(f"Selected PowerPoint: {path}")

    def _open_create_page(self):
        try:
            webbrowser.open(self.CREATE_URL)
            self._set_status("Opened Microsoft Create in browser", 'green')
            self._log(f"Opened: {self.CREATE_URL}")
            pptx = self.pptx_var.get().strip()
            if pptx:
                self._log("Next: In browser, choose Upload and select your PowerPoint file.")
            else:
                self._log("Tip: Select a PowerPoint file first, then use Copy PPTX Path.")
        except Exception as exc:
            self._set_status("Could not open browser", 'red')
            self._log(f"ERROR: Could not open browser: {exc}")
            messagebox.showerror("Error", f"Could not open Microsoft Create:\n\n{exc}")

    def _copy_pptx_path(self):
        pptx = self.pptx_var.get().strip()
        if not pptx:
            messagebox.showwarning("Missing Input", "Please select a PowerPoint file first.")
            return
        if not Path(pptx).exists():
            messagebox.showwarning("Missing File", "The selected PowerPoint file does not exist.")
            return

        self.clipboard_clear()
        self.clipboard_append(pptx)
        self.update_idletasks()
        self._set_status("PPTX path copied to clipboard", 'green')
        self._log(f"Copied to clipboard: {pptx}")

    def _open_pptx_folder(self):
        pptx = self.pptx_var.get().strip()
        if not pptx:
            messagebox.showwarning("Missing Input", "Please select a PowerPoint file first.")
            return
        folder = Path(pptx).parent
        try:
            _open_path_with_system_app(folder)
            self._set_status("Opened PowerPoint folder", 'green')
            self._log(f"Opened folder: {folder}")
        except Exception as exc:
            self._set_status("Could not open folder", 'red')
            self._log(f"ERROR: Could not open folder: {exc}")
            messagebox.showerror("Error", f"Could not open folder:\n\n{exc}")


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
        
        self.record_panel = RecordPanel(
            record_frame,
            on_status_change=self._update_status,
            on_monitor_change=self._highlight_recording_monitor
        )
        self.record_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Monitor display in record tab
        self.monitor_display = MonitorDisplay(record_frame)
        self.monitor_display.pack(fill=tk.X)
        default_monitor_number = self.monitor_display.get_default_monitor_number()
        self._highlight_recording_monitor(default_monitor_number)
        self.record_panel.set_monitor_display(self.monitor_display)

        try:
            monitors = get_monitors()
            if default_monitor_number and 0 < default_monitor_number <= len(monitors):
                monitor = monitors[default_monitor_number - 1]
                monitor_name = monitor.name or f"Display {default_monitor_number}"
                primary = " (primary)" if monitor.is_primary else ""
                self.record_panel._update_monitor_display({
                    "number": default_monitor_number,
                    "info": f"{default_monitor_number}. {monitor_name}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y}){primary}",
                })
            else:
                self.record_panel._update_monitor_display(None)
        except Exception:
            self.record_panel._update_monitor_display(None)

        self.record_panel.refresh_recording_preview()
        
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

        # Camtasia tab
        camtasia_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(camtasia_frame, text="  Camtasia  ")

        self.camtasia_panel = CamtasiaPanel(
            camtasia_frame, on_status_change=self._update_status
        )
        self.camtasia_panel.pack(fill=tk.BOTH, expand=True)

        # PPT to MP4 tab
        mp4_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(mp4_frame, text="  PPT to MP4  ")

        self.ppt_to_mp4_panel = PPTToMP4Panel(
            mp4_frame, on_status_change=self._update_status
        )
        self.ppt_to_mp4_panel.pack(fill=tk.BOTH, expand=True)

        # Microsoft 365 Cloud Video tab
        m365_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(m365_frame, text="  M365 Video  ")

        self.m365_video_panel = Microsoft365VideoPanel(
            m365_frame, on_status_change=self._update_status
        )
        self.m365_video_panel.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self.status_bar = StatusBar(main_frame)
        self.status_bar.pack(fill=tk.X, pady=(10, 0))

    def _update_status(self, message: str):
        """Update the status bar."""
        self.status_bar.set_status(message)

    def _highlight_recording_monitor(self, monitor_number: Optional[int]):
        """Highlight the monitor currently being recorded."""
        self.monitor_display.highlight_monitor(monitor_number)
        
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
5. Use "Pause Recording" to temporarily ignore clicks
6. Click "Stop Recording" when done

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
