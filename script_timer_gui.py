"""
Script Timer GUI - Calculate end times for video narration scripts
Supports multiple script sections with automatic time chaining.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import re
import json


def parse_time(time_str: str) -> float:
    """Parse time string (MM:SS or MM:SS.mmm or just seconds) to total seconds."""
    time_str = time_str.strip()
    if not time_str:
        return 0.0
    
    # Try MM:SS.mmm or MM:SS format
    match = re.match(r'^(\d+):(\d{1,2})(?:\.(\d+))?$', time_str)
    if match:
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        milliseconds = int(match.group(3)) if match.group(3) else 0
        # Normalize milliseconds (handle .5 as .500, .50 as .500, etc.)
        if match.group(3):
            ms_str = match.group(3).ljust(3, '0')[:3]
            milliseconds = int(ms_str)
        return minutes * 60 + seconds + milliseconds / 1000
    
    # Try just seconds
    try:
        return float(time_str)
    except ValueError:
        return 0.0


def format_time(total_seconds: float) -> str:
    """Format total seconds to MM:SS.mmm."""
    if total_seconds < 0:
        total_seconds = 0
    
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def count_words(text: str) -> int:
    """Count words in text."""
    words = text.split()
    return len(words)


def estimate_duration(text: str, words_per_minute: float) -> float:
    """Estimate speaking duration in seconds."""
    word_count = count_words(text)
    if word_count == 0:
        return 0.0
    return (word_count / words_per_minute) * 60


class ScriptRow(ttk.Frame):
    """A single script row with text, timing info."""
    
    def __init__(self, parent, row_num: int, on_change=None, on_delete=None):
        super().__init__(parent, padding=5)
        self.row_num = row_num
        self.on_change = on_change
        self.on_delete = on_delete
        self.start_time = 0.0
        self.end_time = 0.0
        self.duration = 0.0
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the row UI."""
        self.configure(relief="groove", borderwidth=2)
        
        # Header row with row number and delete button
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.row_label = ttk.Label(
            header_frame,
            text=f"Section {self.row_num}",
            font=('Segoe UI', 10, 'bold')
        )
        self.row_label.pack(side=tk.LEFT)
        
        delete_btn = ttk.Button(header_frame, text="✕", width=3, command=self._on_delete)
        delete_btn.pack(side=tk.RIGHT)
        
        # Content frame
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side - timing info
        timing_frame = ttk.Frame(content_frame)
        timing_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Start time (read-only, set by previous row)
        ttk.Label(timing_frame, text="Start:").pack(anchor=tk.W)
        self.start_var = tk.StringVar(value="0:00.000")
        start_entry = ttk.Entry(timing_frame, textvariable=self.start_var, width=12, state='readonly')
        start_entry.pack(anchor=tk.W, pady=(0, 5))
        
        # Duration
        ttk.Label(timing_frame, text="Duration:").pack(anchor=tk.W)
        self.duration_var = tk.StringVar(value="0:00.000")
        duration_entry = ttk.Entry(timing_frame, textvariable=self.duration_var, width=12, state='readonly')
        duration_entry.pack(anchor=tk.W, pady=(0, 5))
        
        # End time
        ttk.Label(timing_frame, text="End:").pack(anchor=tk.W)
        self.end_var = tk.StringVar(value="0:00.000")
        end_entry = ttk.Entry(timing_frame, textvariable=self.end_var, width=12, state='readonly')
        end_entry.pack(anchor=tk.W, pady=(0, 5))
        
        # Word count
        ttk.Label(timing_frame, text="Words:").pack(anchor=tk.W)
        self.words_var = tk.StringVar(value="0")
        words_entry = ttk.Entry(timing_frame, textvariable=self.words_var, width=12, state='readonly')
        words_entry.pack(anchor=tk.W)
        
        # Right side - script text
        text_frame = ttk.Frame(content_frame)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(text_frame, text="Script:").pack(anchor=tk.W)
        self.script_text = scrolledtext.ScrolledText(
            text_frame,
            font=('Segoe UI', 10),
            wrap=tk.WORD,
            height=5
        )
        self.script_text.pack(fill=tk.BOTH, expand=True)
        self.script_text.bind('<KeyRelease>', self._on_text_change)
        
    def _on_text_change(self, event=None):
        """Handle text change."""
        if self.on_change:
            self.on_change()
            
    def _on_delete(self):
        """Handle delete button click."""
        if self.on_delete:
            self.on_delete(self)
            
    def update_row_number(self, num: int):
        """Update the row number display."""
        self.row_num = num
        self.row_label.config(text=f"Section {num}")
        
    def set_start_time(self, start_seconds: float):
        """Set the start time for this row."""
        self.start_time = start_seconds
        self.start_var.set(format_time(start_seconds))
        
    def calculate(self, wpm: float) -> float:
        """Calculate duration and end time. Returns end time."""
        script = self.script_text.get("1.0", tk.END).strip()
        word_count = count_words(script)
        self.duration = estimate_duration(script, wpm)
        self.end_time = self.start_time + self.duration
        
        self.words_var.set(str(word_count))
        self.duration_var.set(format_time(self.duration))
        self.end_var.set(format_time(self.end_time))
        
        return self.end_time
    
    def get_data(self) -> dict:
        """Get row data for saving."""
        return {
            "script": self.script_text.get("1.0", tk.END).strip()
        }
    
    def set_data(self, data: dict):
        """Set row data from loaded file."""
        self.script_text.delete("1.0", tk.END)
        self.script_text.insert("1.0", data.get("script", ""))


class ScriptTimerGUI:
    """Main GUI for script timing with multiple rows."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Script Timer")
        self.root.geometry("800x700")
        self.root.minsize(700, 500)
        
        self.rows = []
        self._setup_ui()
        
        # Add first row
        self._add_row()
        
    def _setup_ui(self):
        """Set up the UI."""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top settings frame
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Settings
        settings_frame = ttk.LabelFrame(top_frame, text="Settings", padding=10)
        settings_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(settings_frame, text="Words per minute:").pack(side=tk.LEFT)
        self.wpm_var = tk.StringVar(value="150")
        wpm_entry = ttk.Entry(settings_frame, textvariable=self.wpm_var, width=6)
        wpm_entry.pack(side=tk.LEFT, padx=(5, 20))
        self.wpm_var.trace_add('write', self._on_wpm_change)
        
        ttk.Label(settings_frame, text="Start time:").pack(side=tk.LEFT)
        self.global_start_var = tk.StringVar(value="0:00.000")
        start_entry = ttk.Entry(settings_frame, textvariable=self.global_start_var, width=12)
        start_entry.pack(side=tk.LEFT, padx=(5, 20))
        self.global_start_var.trace_add('write', self._on_start_change)
        
        ttk.Label(settings_frame, text="(Typical WPM: 120-180)").pack(side=tk.LEFT)
        
        # Totals frame
        totals_frame = ttk.LabelFrame(top_frame, text="Totals", padding=10)
        totals_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Label(totals_frame, text="Total Duration:").pack(side=tk.LEFT)
        self.total_duration_var = tk.StringVar(value="0:00.000")
        ttk.Entry(totals_frame, textvariable=self.total_duration_var, width=12, state='readonly').pack(side=tk.LEFT, padx=(5, 15))
        
        ttk.Label(totals_frame, text="Total Words:").pack(side=tk.LEFT)
        self.total_words_var = tk.StringVar(value="0")
        ttk.Entry(totals_frame, textvariable=self.total_words_var, width=8, state='readonly').pack(side=tk.LEFT, padx=5)
        
        # Scrollable rows area
        rows_container = ttk.Frame(main_frame)
        rows_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Canvas with scrollbar
        self.canvas = tk.Canvas(rows_container)
        scrollbar = ttk.Scrollbar(rows_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas resize to adjust frame width
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        add_btn = ttk.Button(button_frame, text="+ Add Section", command=self._add_row)
        add_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(button_frame, text="Clear All", command=self._clear_all)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        save_btn = ttk.Button(button_frame, text="Save Script", command=self._save_script)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = ttk.Button(button_frame, text="Load Script", command=self._load_script)
        load_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(button_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        export_btn = ttk.Button(button_frame, text="Export Text", command=self._export_text)
        export_btn.pack(side=tk.LEFT, padx=5)
        
    def _on_canvas_configure(self, event):
        """Adjust frame width when canvas is resized."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def _add_row(self):
        """Add a new script row."""
        row_num = len(self.rows) + 1
        row = ScriptRow(
            self.scrollable_frame,
            row_num,
            on_change=self._recalculate_all,
            on_delete=self._delete_row
        )
        row.pack(fill=tk.X, pady=5)
        self.rows.append(row)
        self._recalculate_all()
        
        # Scroll to bottom
        self.root.after(100, lambda: self.canvas.yview_moveto(1.0))
        
    def _delete_row(self, row: ScriptRow):
        """Delete a script row."""
        if len(self.rows) <= 1:
            messagebox.showwarning("Cannot Delete", "Must have at least one section.")
            return
            
        row.pack_forget()
        row.destroy()
        self.rows.remove(row)
        
        # Renumber remaining rows
        for i, r in enumerate(self.rows):
            r.update_row_number(i + 1)
            
        self._recalculate_all()
        
    def _on_wpm_change(self, *args):
        """Handle WPM change."""
        self._recalculate_all()
        
    def _on_start_change(self, *args):
        """Handle global start time change."""
        self._recalculate_all()
        
    def _get_wpm(self) -> float:
        """Get current WPM value."""
        try:
            wpm = float(self.wpm_var.get().strip())
            if wpm <= 0:
                return 150.0
            return wpm
        except ValueError:
            return 150.0
        
    def _recalculate_all(self):
        """Recalculate all rows."""
        wpm = self._get_wpm()
        current_time = parse_time(self.global_start_var.get())
        total_words = 0
        start_time = current_time
        
        for row in self.rows:
            row.set_start_time(current_time)
            current_time = row.calculate(wpm)
            total_words += count_words(row.script_text.get("1.0", tk.END).strip())
        
        total_duration = current_time - start_time
        self.total_duration_var.set(format_time(total_duration))
        self.total_words_var.set(str(total_words))
        
    def _clear_all(self):
        """Clear all rows and start fresh."""
        if messagebox.askyesno("Clear All", "Are you sure you want to clear all sections?"):
            for row in self.rows[1:]:  # Keep first row
                row.pack_forget()
                row.destroy()
            self.rows = self.rows[:1]
            self.rows[0].script_text.delete("1.0", tk.END)
            self.global_start_var.set("0:00.000")
            self._recalculate_all()
            
    def _save_script(self):
        """Save script to JSON file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Script"
        )
        if not filepath:
            return
            
        data = {
            "wpm": self._get_wpm(),
            "start_time": self.global_start_var.get(),
            "sections": [row.get_data() for row in self.rows]
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
            
        messagebox.showinfo("Saved", f"Script saved to {filepath}")
        
    def _load_script(self):
        """Load script from JSON file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Script"
        )
        if not filepath:
            return
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
            return
            
        # Clear existing rows
        for row in self.rows:
            row.pack_forget()
            row.destroy()
        self.rows = []
        
        # Set settings
        self.wpm_var.set(str(data.get("wpm", 150)))
        self.global_start_var.set(data.get("start_time", "0:00.000"))
        
        # Create rows from data
        for section_data in data.get("sections", []):
            self._add_row()
            self.rows[-1].set_data(section_data)
            
        # Ensure at least one row
        if not self.rows:
            self._add_row()
            
        self._recalculate_all()
        
    def _export_text(self):
        """Export all script text to a text file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Script Text"
        )
        if not filepath:
            return
            
        lines = []
        for i, row in enumerate(self.rows):
            script = row.script_text.get("1.0", tk.END).strip()
            if script:
                lines.append(f"--- Section {i+1} ({row.start_var.get()} - {row.end_var.get()}) ---")
                lines.append(script)
                lines.append("")
                
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
            
        messagebox.showinfo("Exported", f"Script exported to {filepath}")
        
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    app = ScriptTimerGUI()
    app.run()


if __name__ == "__main__":
    main()
