"""
Video Editor GUI - Visual interface for adding narration to images
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from PIL import Image, ImageTk
from datetime import datetime
from typing import Optional, List, Dict

# Import the video generator
try:
    from video_generator import VideoGenerator, TRANSITIONS
except ImportError:
    print("Error: video_generator.py not found in the same directory")
    sys.exit(1)


class ImageNarrationPanel(ttk.Frame):
    """Panel for a single image with narration input."""
    
    def __init__(self, parent, image_path: Path, index: int, on_change=None):
        super().__init__(parent, padding=5)
        self.image_path = image_path
        self.index = index
        self.on_change = on_change
        self.thumbnail = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI for this image panel."""
        # Main container with border
        self.configure(relief="groove", borderwidth=2)
        
        # Header with image number and filename
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(
            header_frame, 
            text=f"#{self.index + 1}: {self.image_path.name}",
            font=('Segoe UI', 10, 'bold')
        ).pack(side=tk.LEFT)
        
        # Content frame (image on left, narration on right)
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Image frame
        image_frame = ttk.Frame(content_frame)
        image_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        # Load and display thumbnail
        self._load_thumbnail()
        self.image_label = ttk.Label(image_frame, image=self.thumbnail)
        self.image_label.pack()
        
        # Right side - narration and settings
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Narration label
        ttk.Label(right_frame, text="Narration Script:").pack(anchor=tk.W)
        
        # Narration text area
        self.narration_text = scrolledtext.ScrolledText(
            right_frame, 
            width=50, 
            height=6,
            font=('Segoe UI', 10),
            wrap=tk.WORD
        )
        self.narration_text.pack(fill=tk.BOTH, expand=True, pady=(2, 5))
        self.narration_text.bind('<KeyRelease>', self._on_text_change)
        
        # Settings frame
        settings_frame = ttk.Frame(right_frame)
        settings_frame.pack(fill=tk.X)
        
        # Duration
        ttk.Label(settings_frame, text="Duration (sec):").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value="auto")
        self.duration_entry = ttk.Entry(settings_frame, textvariable=self.duration_var, width=8)
        self.duration_entry.pack(side=tk.LEFT, padx=(2, 15))
        
        # Transition (for after this image)
        ttk.Label(settings_frame, text="Transition after:").pack(side=tk.LEFT)
        self.transition_var = tk.StringVar(value="default")
        transition_options = ["default"] + list(TRANSITIONS.keys())
        self.transition_combo = ttk.Combobox(
            settings_frame, 
            textvariable=self.transition_var,
            values=transition_options,
            width=12,
            state="readonly"
        )
        self.transition_combo.pack(side=tk.LEFT, padx=2)
        
    def _load_thumbnail(self):
        """Load and create a thumbnail of the image."""
        try:
            img = Image.open(self.image_path)
            # Create thumbnail maintaining aspect ratio
            img.thumbnail((250, 180), Image.Resampling.LANCZOS)
            self.thumbnail = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error loading image {self.image_path}: {e}")
            # Create a placeholder
            placeholder = Image.new('RGB', (250, 180), color='gray')
            self.thumbnail = ImageTk.PhotoImage(placeholder)
    
    def _on_text_change(self, event=None):
        """Called when narration text changes."""
        if self.on_change:
            self.on_change()
    
    def get_data(self) -> Dict:
        """Get the data for this image."""
        narration = self.narration_text.get("1.0", tk.END).strip()
        duration_str = self.duration_var.get().strip()
        
        # Parse duration
        duration = None
        if duration_str and duration_str.lower() != "auto":
            try:
                duration = float(duration_str)
            except ValueError:
                pass
        
        # Get transition
        transition = self.transition_var.get()
        if transition == "default":
            transition = None
        
        return {
            "image_path": str(self.image_path),
            "narration": narration,
            "duration": duration,
            "transition": transition
        }
    
    def set_data(self, data: Dict):
        """Set data from a loaded project."""
        if "narration" in data:
            self.narration_text.delete("1.0", tk.END)
            self.narration_text.insert("1.0", data["narration"])
        
        if "duration" in data and data["duration"] is not None:
            self.duration_var.set(str(data["duration"]))
        else:
            self.duration_var.set("auto")
        
        if "transition" in data and data["transition"]:
            self.transition_var.set(data["transition"])
        else:
            self.transition_var.set("default")


class VideoEditorGUI:
    """Main GUI application for video editing."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Video Narration Editor")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Variables
        self.image_dir = None
        self.image_panels: List[ImageNarrationPanel] = []
        self.generator = VideoGenerator()
        self.project_modified = False
        self.current_project_path = None
        
        self._setup_ui()
        self._setup_menu()
        
    def _setup_menu(self):
        """Set up the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Image Folder...", command=self._open_folder, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Workflow...", command=self._open_workflow)
        file_menu.add_separator()
        file_menu.add_command(label="Save Project", command=self._save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Save Project As...", command=self._save_project_as)
        file_menu.add_command(label="Load Project...", command=self._load_project)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Clear All Narrations", command=self._clear_all_narrations)
        
        # Video menu
        video_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Video", menu=video_menu)
        video_menu.add_command(label="Generate Video", command=self._generate_video, accelerator="F5")
        video_menu.add_command(label="Preview Narration", command=self._preview_narration)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self._open_folder())
        self.root.bind('<Control-s>', lambda e: self._save_project())
        self.root.bind('<F5>', lambda e: self._generate_video())
        
    def _setup_ui(self):
        """Set up the main UI."""
        # Top toolbar
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X)
        
        ttk.Button(toolbar, text="Open Folder", command=self._open_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Project", command=self._save_project).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Generate Video", command=self._generate_video).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # Global settings
        ttk.Label(toolbar, text="Default Transition:").pack(side=tk.LEFT, padx=(0, 2))
        self.default_transition_var = tk.StringVar(value="fade")
        transition_combo = ttk.Combobox(
            toolbar,
            textvariable=self.default_transition_var,
            values=list(TRANSITIONS.keys()),
            width=12,
            state="readonly"
        )
        transition_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Resolution:").pack(side=tk.LEFT, padx=(15, 2))
        self.resolution_var = tk.StringVar(value="1920x1080")
        res_combo = ttk.Combobox(
            toolbar,
            textvariable=self.resolution_var,
            values=["1920x1080", "1280x720", "3840x2160"],
            width=12,
            state="readonly"
        )
        res_combo.pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="Voice:").pack(side=tk.LEFT, padx=(15, 2))
        self.voice_var = tk.StringVar()
        voices = self.generator.list_voices()
        voice_names = [v[1] for v in voices] if voices else ["No voices available"]
        self.voice_combo = ttk.Combobox(
            toolbar,
            textvariable=self.voice_var,
            values=voice_names,
            width=30,
            state="readonly"
        )
        self.voice_combo.pack(side=tk.LEFT, padx=2)
        if voice_names:
            self.voice_combo.current(0)
        
        # Main content area with scrolling
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas and scrollbar for scrolling
        self.canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mouse wheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Bind canvas resize
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready - Open an image folder to begin")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=2, pady=2)
        
        # Welcome message in the main area
        self.welcome_label = ttk.Label(
            self.scrollable_frame,
            text="Welcome to Video Narration Editor!\n\nClick 'Open Folder' to select a directory containing images.\nYou can then add narration text for each image.",
            font=('Segoe UI', 12),
            justify=tk.CENTER
        )
        self.welcome_label.pack(expand=True, pady=100)
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_canvas_configure(self, event):
        """Handle canvas resize to adjust the scrollable frame width."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _open_folder(self):
        """Open a folder dialog to select image directory."""
        folder = filedialog.askdirectory(title="Select Image Folder")
        if folder:
            self._load_images(folder)
    
    def _open_workflow(self):
        """Open a workflow.json file from screenshot automation."""
        filepath = filedialog.askopenfilename(
            title="Open Workflow File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # Extract image directory from workflow
                clicks = data.get("clicks", [])
                if clicks and "screenshot" in clicks[0]:
                    screenshot_path = Path(clicks[0]["screenshot"])
                    if screenshot_path.is_absolute():
                        image_dir = screenshot_path.parent
                    else:
                        image_dir = Path(filepath).parent / screenshot_path.parent
                    
                    if image_dir.exists():
                        self._load_images(str(image_dir))
                    else:
                        messagebox.showerror("Error", f"Image directory not found: {image_dir}")
                else:
                    messagebox.showerror("Error", "No screenshots found in workflow")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load workflow: {e}")
    
    def _load_images(self, folder: str):
        """Load images from the specified folder."""
        self.image_dir = Path(folder)
        
        try:
            images = self.generator.get_images_from_directory(folder)
        except FileNotFoundError as e:
            messagebox.showerror("Error", str(e))
            return
        
        if not images:
            messagebox.showinfo("No Images", f"No image files found in:\n{folder}")
            return
        
        # Clear existing panels
        self._clear_panels()
        
        # Remove welcome label
        if hasattr(self, 'welcome_label') and self.welcome_label:
            self.welcome_label.destroy()
            self.welcome_label = None
        
        # Create panels for each image
        for i, image_path in enumerate(images):
            panel = ImageNarrationPanel(
                self.scrollable_frame, 
                image_path, 
                i,
                on_change=self._on_content_change
            )
            panel.pack(fill=tk.X, pady=5, padx=5)
            self.image_panels.append(panel)
        
        self.status_var.set(f"Loaded {len(images)} images from {folder}")
        self.project_modified = False
        self.current_project_path = None
        
        # Scroll to top
        self.canvas.yview_moveto(0)
    
    def _clear_panels(self):
        """Clear all image panels."""
        for panel in self.image_panels:
            panel.destroy()
        self.image_panels = []
    
    def _on_content_change(self):
        """Called when any content changes."""
        self.project_modified = True
        if self.current_project_path:
            self.root.title(f"Video Narration Editor - {self.current_project_path}*")
        else:
            self.root.title("Video Narration Editor*")
    
    def _clear_all_narrations(self):
        """Clear all narration text."""
        if not self.image_panels:
            return
        
        if messagebox.askyesno("Confirm", "Clear all narration text?"):
            for panel in self.image_panels:
                panel.narration_text.delete("1.0", tk.END)
            self._on_content_change()
    
    def _get_config(self) -> Dict:
        """Get the current configuration."""
        if not self.image_panels:
            return None
        
        # Get resolution
        res_str = self.resolution_var.get()
        width, height = map(int, res_str.split('x'))
        
        # Get voice
        voice_idx = self.voice_combo.current()
        voices = self.generator.list_voices()
        voice_id = voices[voice_idx][0] if voices and voice_idx >= 0 else None
        
        return {
            "images": [panel.get_data() for panel in self.image_panels],
            "resolution": (width, height),
            "default_transition": self.default_transition_var.get(),
            "transition_duration": 1.0,
            "enable_narration": True,
            "voice_id": voice_id,
            "image_dir": str(self.image_dir) if self.image_dir else None
        }
    
    def _save_project(self):
        """Save the current project."""
        if not self.image_panels:
            messagebox.showinfo("Nothing to Save", "No images loaded.")
            return
        
        if self.current_project_path:
            self._do_save_project(self.current_project_path)
        else:
            self._save_project_as()
    
    def _save_project_as(self):
        """Save project with a new filename."""
        if not self.image_panels:
            messagebox.showinfo("Nothing to Save", "No images loaded.")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="video_project.json"
        )
        if filepath:
            self._do_save_project(filepath)
    
    def _do_save_project(self, filepath: str):
        """Actually save the project to a file."""
        config = self._get_config()
        if config:
            try:
                with open(filepath, 'w') as f:
                    json.dump(config, f, indent=2)
                self.current_project_path = filepath
                self.project_modified = False
                self.root.title(f"Video Narration Editor - {filepath}")
                self.status_var.set(f"Project saved to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save project: {e}")
    
    def _load_project(self):
        """Load a saved project."""
        filepath = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not filepath:
            return
        
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            # Load images from the saved directory
            image_dir = config.get("image_dir")
            if not image_dir or not Path(image_dir).exists():
                # Ask for new location
                messagebox.showinfo(
                    "Image Folder Required",
                    f"Original image folder not found:\n{image_dir}\n\nPlease select the image folder."
                )
                image_dir = filedialog.askdirectory(title="Select Image Folder")
                if not image_dir:
                    return
            
            self._load_images(image_dir)
            
            # Apply saved narrations
            saved_images = config.get("images", [])
            for i, panel in enumerate(self.image_panels):
                if i < len(saved_images):
                    panel.set_data(saved_images[i])
            
            # Apply settings
            if "default_transition" in config:
                self.default_transition_var.set(config["default_transition"])
            
            if "resolution" in config:
                res = config["resolution"]
                self.resolution_var.set(f"{res[0]}x{res[1]}")
            
            self.current_project_path = filepath
            self.project_modified = False
            self.root.title(f"Video Narration Editor - {filepath}")
            self.status_var.set(f"Project loaded from {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load project: {e}")
    
    def _load_project_file(self, filepath: str):
        """Load a project from a specific file path (for command line startup)."""
        if not filepath or not Path(filepath).exists():
            messagebox.showerror("Error", f"Project file not found: {filepath}")
            return
        
        try:
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            # Load images from the saved directory
            image_dir = config.get("image_dir")
            if not image_dir or not Path(image_dir).exists():
                messagebox.showinfo(
                    "Image Folder Required",
                    f"Original image folder not found:\n{image_dir}\n\nPlease select the image folder."
                )
                image_dir = filedialog.askdirectory(title="Select Image Folder")
                if not image_dir:
                    return
            
            self._load_images(image_dir)
            
            # Apply saved narrations
            saved_images = config.get("images", [])
            for i, panel in enumerate(self.image_panels):
                if i < len(saved_images):
                    panel.set_data(saved_images[i])
            
            # Apply settings
            if "default_transition" in config:
                self.default_transition_var.set(config["default_transition"])
            
            if "resolution" in config:
                res = config["resolution"]
                self.resolution_var.set(f"{res[0]}x{res[1]}")
            
            self.current_project_path = filepath
            self.project_modified = False
            self.root.title(f"Video Narration Editor - {filepath}")
            self.status_var.set(f"Project loaded from {filepath}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load project: {e}")
    
    def _preview_narration(self):
        """Preview the narration for the selected image using TTS."""
        # For now, preview all narrations sequentially (could be enhanced)
        if not self.image_panels:
            return
        
        try:
            import pyttsx3
            engine = pyttsx3.init()
            
            # Set voice
            voice_idx = self.voice_combo.current()
            voices = self.generator.list_voices()
            if voices and voice_idx >= 0:
                engine.setProperty('voice', voices[voice_idx][0])
            
            # Speak each narration
            for i, panel in enumerate(self.image_panels):
                narration = panel.narration_text.get("1.0", tk.END).strip()
                if narration:
                    self.status_var.set(f"Speaking narration for image {i+1}...")
                    self.root.update()
                    engine.say(f"Image {i+1}. {narration}")
                    engine.runAndWait()
            
            engine.stop()
            self.status_var.set("Narration preview complete")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview narration: {e}")
    
    def _generate_video(self):
        """Generate the video with current settings."""
        if not self.image_panels:
            messagebox.showinfo("No Images", "Please load images first.")
            return
        
        # Check if any narration has been added
        has_narration = any(
            panel.narration_text.get("1.0", tk.END).strip() 
            for panel in self.image_panels
        )
        
        if not has_narration:
            if not messagebox.askyesno(
                "No Narration",
                "No narration has been added. Continue without narration?"
            ):
                return
        
        # Get output file
        default_name = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_path = filedialog.asksaveasfilename(
            title="Save Video As",
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")],
            initialfile=default_name,
            initialdir=str(self.image_dir) if self.image_dir else None
        )
        
        if not output_path:
            return
        
        # Build configuration
        config = self._get_config()
        if not config:
            return
        
        config["output_path"] = output_path
        config["default_duration"] = 5.0
        
        # Set generator settings
        self.generator.output_resolution = config["resolution"]
        self.generator.transition_duration = config.get("transition_duration", 1.0)
        
        if config.get("voice_id"):
            self.generator.set_voice(config["voice_id"])
        
        # Show progress
        self.status_var.set("Generating video... This may take a few minutes.")
        self.root.update()
        
        # Disable UI during generation
        self.root.config(cursor="wait")
        
        try:
            result = self.generator.generate_video(config)
            
            if result:
                self.status_var.set(f"Video saved to {result}")
                if messagebox.askyesno("Success", f"Video generated successfully!\n\n{result}\n\nOpen containing folder?"):
                    import subprocess
                    subprocess.run(["explorer", "/select,", result], check=False)
            else:
                self.status_var.set("Video generation failed")
                messagebox.showerror("Error", "Video generation failed. Check console for details.")
                
        except Exception as e:
            self.status_var.set("Video generation error")
            messagebox.showerror("Error", f"Video generation failed:\n{e}")
        finally:
            self.root.config(cursor="")
    
    def _on_close(self):
        """Handle window close."""
        if self.project_modified:
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes. Save before closing?"
            )
            if result is None:  # Cancel
                return
            if result:  # Yes - save
                self._save_project()
        
        self.root.destroy()
    
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Video Narration Editor")
    parser.add_argument("-i", "--input", help="Path to image directory to load on startup")
    parser.add_argument("-p", "--project", help="Load a saved project file on startup")
    args = parser.parse_args()
    
    app = VideoEditorGUI()
    
    if args.project:
        app.root.after(100, lambda: app._load_project_file(args.project))
    elif args.input:
        app.root.after(100, lambda: app._load_images(args.input))
    
    app.run()


if __name__ == "__main__":
    main()