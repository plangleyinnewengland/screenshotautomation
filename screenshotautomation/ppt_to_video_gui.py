"""
PowerPoint to Video GUI - Visual interface for converting PPT storyboards to narrated videos
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Optional, List

try:
    from ppt_to_video import PPTToVideoConverter
except ImportError:
    print("Error: ppt_to_video.py not found in the same directory")
    sys.exit(1)


class SlideNarrationPanel(ttk.Frame):
    """Panel for editing a single slide's narration."""
    
    def __init__(self, parent, slide_num: int, notes: str, on_change=None):
        super().__init__(parent, padding=5)
        self.slide_num = slide_num
        self.original_notes = notes
        self.on_change = on_change
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI."""
        self.configure(relief="groove", borderwidth=2)
        
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(
            header_frame,
            text=f"Slide {self.slide_num}",
            font=('Segoe UI', 10, 'bold')
        ).pack(side=tk.LEFT)
        
        # Reset button
        reset_btn = ttk.Button(
            header_frame, 
            text="Reset to Original", 
            command=self._reset_notes
        )
        reset_btn.pack(side=tk.RIGHT)
        
        # Use checkbox
        self.use_var = tk.BooleanVar(value=bool(self.original_notes.strip()))
        use_check = ttk.Checkbutton(
            header_frame,
            text="Include narration",
            variable=self.use_var,
            command=self._on_use_change
        )
        use_check.pack(side=tk.RIGHT, padx=10)
        
        # Narration text
        ttk.Label(self, text="Narration:").pack(anchor=tk.W)
        self.narration_text = scrolledtext.ScrolledText(
            self,
            font=('Segoe UI', 10),
            wrap=tk.WORD,
            height=4
        )
        self.narration_text.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.narration_text.insert("1.0", self.original_notes)
        self.narration_text.bind('<KeyRelease>', self._on_text_change)
        
        # Update state based on whether there's text
        self._update_state()
        
    def _on_use_change(self):
        """Handle use checkbox change."""
        self._update_state()
        if self.on_change:
            self.on_change()
            
    def _update_state(self):
        """Update UI state based on use checkbox."""
        if self.use_var.get():
            self.narration_text.config(state='normal')
        else:
            self.narration_text.config(state='disabled')
            
    def _on_text_change(self, event=None):
        """Handle text change."""
        if self.on_change:
            self.on_change()
            
    def _reset_notes(self):
        """Reset to original notes."""
        self.narration_text.config(state='normal')
        self.narration_text.delete("1.0", tk.END)
        self.narration_text.insert("1.0", self.original_notes)
        self.use_var.set(bool(self.original_notes.strip()))
        self._update_state()
        if self.on_change:
            self.on_change()
            
    def get_narration(self) -> Optional[str]:
        """Get the narration text, or None if disabled."""
        if not self.use_var.get():
            return ""
        return self.narration_text.get("1.0", tk.END).strip()


class PPTToVideoGUI:
    """Main GUI application."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PowerPoint to Video Converter")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        self.pptx_path = None
        self.slides_info = []
        self.slide_panels: List[SlideNarrationPanel] = []
        self.converter = None
        self.is_converting = False
        
        self._setup_ui()
        self._setup_menu()
        
    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PowerPoint...", command=self._open_pptx, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        self.root.bind('<Control-o>', lambda e: self._open_pptx())
        
    def _setup_ui(self):
        """Set up the UI."""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section - file selection and settings
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # File selection
        file_frame = ttk.LabelFrame(top_frame, text="PowerPoint File", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.file_label = ttk.Label(file_frame, text="No file selected")
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        open_btn = ttk.Button(file_frame, text="Open...", command=self._open_pptx)
        open_btn.pack(side=tk.RIGHT)
        
        # Settings
        settings_frame = ttk.LabelFrame(top_frame, text="Settings", padding=10)
        settings_frame.pack(fill=tk.X)
        
        # Row 1 - Resolution and FPS
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Resolution:").pack(side=tk.LEFT)
        self.resolution_var = tk.StringVar(value="1920x1080")
        resolution_combo = ttk.Combobox(
            row1,
            textvariable=self.resolution_var,
            values=["1920x1080", "1280x720", "3840x2160", "1080x1920"],
            width=12,
            state="readonly"
        )
        resolution_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1, text="FPS:").pack(side=tk.LEFT)
        self.fps_var = tk.StringVar(value="30")
        fps_combo = ttk.Combobox(
            row1,
            textvariable=self.fps_var,
            values=["24", "30", "60"],
            width=6,
            state="readonly"
        )
        fps_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row1, text="Default slide duration (sec):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="5.0")
        duration_entry = ttk.Entry(row1, textvariable=self.duration_var, width=6)
        duration_entry.pack(side=tk.LEFT, padx=5)
        
        # Row 2 - Voice settings
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="TTS Voice:").pack(side=tk.LEFT)
        self.voice_var = tk.StringVar(value="")
        self.voice_combo = ttk.Combobox(row2, textvariable=self.voice_var, width=40, state="readonly")
        self.voice_combo.pack(side=tk.LEFT, padx=(5, 20))
        
        ttk.Label(row2, text="Speech Rate:").pack(side=tk.LEFT)
        self.rate_var = tk.StringVar(value="150")
        rate_entry = ttk.Entry(row2, textvariable=self.rate_var, width=6)
        rate_entry.pack(side=tk.LEFT, padx=5)
        
        # Load voices
        self._load_voices()
        
        # Slides section with scroll
        slides_label = ttk.Label(main_frame, text="Slide Narrations:", font=('Segoe UI', 10, 'bold'))
        slides_label.pack(anchor=tk.W, pady=(10, 5))
        
        # Canvas with scrollbar for slides
        slides_container = ttk.Frame(main_frame)
        slides_container.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.canvas = tk.Canvas(slides_container)
        scrollbar = ttk.Scrollbar(slides_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Placeholder message
        self.placeholder = ttk.Label(
            self.scrollable_frame, 
            text="Open a PowerPoint file to see slides and narrations",
            font=('Segoe UI', 11),
            foreground='gray'
        )
        self.placeholder.pack(pady=50)
        
        # Bottom section - progress and convert button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X)
        
        # Progress bar
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(bottom_frame, textvariable=self.progress_var)
        self.progress_label.pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(bottom_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill=tk.X)
        
        self.convert_btn = ttk.Button(
            button_frame, 
            text="Convert to Video",
            command=self._start_conversion,
            state='disabled'
        )
        self.convert_btn.pack(side=tk.RIGHT, padx=5)
        
        preview_btn = ttk.Button(
            button_frame,
            text="Preview Narration",
            command=self._preview_narration
        )
        preview_btn.pack(side=tk.RIGHT, padx=5)
        
    def _on_canvas_configure(self, event):
        """Adjust frame width when canvas is resized."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def _load_voices(self):
        """Load available TTS voices."""
        try:
            temp_converter = PPTToVideoConverter()
            voices = temp_converter.list_voices()
            
            voice_names = []
            self.voice_ids = {}
            
            for voice_id, voice_name in voices:
                # Shorten the name for display
                short_name = voice_name.split(' - ')[0] if ' - ' in voice_name else voice_name
                voice_names.append(short_name)
                self.voice_ids[short_name] = voice_id
                
            self.voice_combo['values'] = voice_names
            if voice_names:
                self.voice_combo.current(0)
        except Exception as e:
            print(f"Could not load voices: {e}")
            
    def _open_pptx(self):
        """Open a PowerPoint file."""
        filepath = filedialog.askopenfilename(
            filetypes=[
                ("PowerPoint files", "*.pptx"),
                ("All files", "*.*")
            ],
            title="Open PowerPoint"
        )
        
        if not filepath:
            return
            
        self.pptx_path = Path(filepath)
        self.file_label.config(text=str(self.pptx_path))
        
        # Load slides
        self._load_slides()
        
    def _load_slides(self):
        """Load slides from the PowerPoint file."""
        if not self.pptx_path:
            return
            
        try:
            # Create converter temporarily to extract slides
            converter = PPTToVideoConverter()
            self.slides_info = converter.extract_slides_info(str(self.pptx_path))
            
            # Clear existing panels
            for panel in self.slide_panels:
                panel.destroy()
            self.slide_panels = []
            
            # Hide placeholder
            self.placeholder.pack_forget()
            
            # Create panels for each slide
            for info in self.slides_info:
                panel = SlideNarrationPanel(
                    self.scrollable_frame,
                    info['slide_number'],
                    info['notes']
                )
                panel.pack(fill=tk.X, pady=5, padx=5)
                self.slide_panels.append(panel)
                
            # Enable convert button
            self.convert_btn.config(state='normal')
            self.progress_var.set(f"Loaded {len(self.slides_info)} slides")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load PowerPoint file:\n{e}")
            
    def _preview_narration(self):
        """Preview narration using TTS."""
        if not self.slide_panels:
            messagebox.showinfo("No Slides", "Please open a PowerPoint file first.")
            return
            
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # Set voice
            voice_name = self.voice_var.get()
            if voice_name and voice_name in self.voice_ids:
                engine.setProperty('voice', self.voice_ids[voice_name])
                
            # Set rate
            try:
                rate = int(self.rate_var.get())
                engine.setProperty('rate', rate)
            except ValueError:
                pass
                
            # Speak narration from first slide with text
            for panel in self.slide_panels:
                narration = panel.get_narration()
                if narration:
                    engine.say(f"Slide {panel.slide_num}: {narration}")
                    engine.runAndWait()
                    break
            else:
                messagebox.showinfo("No Narration", "No narration text found in any slide.")
                
        except Exception as e:
            messagebox.showerror("Error", f"Could not preview narration:\n{e}")
            
    def _start_conversion(self):
        """Start the conversion process."""
        if self.is_converting:
            return
            
        # Get output path
        default_name = self.pptx_path.stem + ".mp4"
        output_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")],
            initialfile=default_name,
            title="Save Video As"
        )
        
        if not output_path:
            return
            
        # Collect narrations
        custom_narrations = {}
        for panel in self.slide_panels:
            narration = panel.get_narration()
            if narration is not None:
                custom_narrations[panel.slide_num] = narration
                
        # Parse settings
        try:
            res_str = self.resolution_var.get()
            width, height = map(int, res_str.lower().split('x'))
            resolution = (width, height)
        except ValueError:
            resolution = (1920, 1080)
            
        try:
            fps = int(self.fps_var.get())
        except ValueError:
            fps = 30
            
        try:
            duration = float(self.duration_var.get())
        except ValueError:
            duration = 5.0
            
        try:
            rate = int(self.rate_var.get())
        except ValueError:
            rate = 150
            
        # Get voice ID
        voice_id = None
        voice_name = self.voice_var.get()
        if voice_name and voice_name in self.voice_ids:
            voice_id = self.voice_ids[voice_name]
            
        # Disable UI
        self.is_converting = True
        self.convert_btn.config(state='disabled')
        self.progress_bar['value'] = 0
        
        # Run conversion in background thread
        def run_conversion():
            try:
                def progress_callback(status, current, total):
                    self.root.after(0, lambda: self._update_progress(status, current, total))
                    
                converter = PPTToVideoConverter(
                    output_resolution=resolution,
                    fps=fps,
                    default_slide_duration=duration,
                    tts_rate=rate,
                    progress_callback=progress_callback
                )
                
                if voice_id:
                    converter.set_voice(voice_id)
                    
                result = converter.convert(
                    str(self.pptx_path),
                    output_path,
                    custom_narrations=custom_narrations
                )
                
                self.root.after(0, lambda: self._conversion_complete(result))
                
            except Exception as e:
                self.root.after(0, lambda: self._conversion_error(str(e)))
                
        thread = threading.Thread(target=run_conversion, daemon=True)
        thread.start()
        
    def _update_progress(self, status: str, current: int, total: int):
        """Update progress display."""
        self.progress_var.set(status)
        if total > 0:
            self.progress_bar['value'] = (current / total) * 100
            
    def _conversion_complete(self, result_path: str):
        """Handle conversion completion."""
        self.is_converting = False
        self.convert_btn.config(state='normal')
        self.progress_bar['value'] = 100
        self.progress_var.set("Complete!")
        
        messagebox.showinfo("Success", f"Video created successfully:\n{result_path}")
        
    def _conversion_error(self, error_msg: str):
        """Handle conversion error."""
        self.is_converting = False
        self.convert_btn.config(state='normal')
        self.progress_bar['value'] = 0
        self.progress_var.set("Error occurred")
        
        messagebox.showerror("Error", f"Conversion failed:\n{error_msg}")
        
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    app = PPTToVideoGUI()
    app.run()


if __name__ == "__main__":
    main()
