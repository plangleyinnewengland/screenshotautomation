"""
Video Generator - Create MP4 videos from image directories with narration and transitions
"""

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

try:
    from PIL import Image
    from moviepy import (
        ImageClip, AudioFileClip, CompositeVideoClip, 
        concatenate_videoclips, ColorClip, CompositeAudioClip
    )
    from moviepy import vfx
    import pyttsx3
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


# Available transitions
TRANSITIONS = {
    "none": "No transition - instant cut",
    "fade": "Fade to black between images",
    "crossfade": "Crossfade/dissolve between images",
    "slide_left": "Slide new image from right to left",
    "slide_right": "Slide new image from left to right",
    "slide_up": "Slide new image from bottom to top",
    "slide_down": "Slide new image from top to bottom",
}


class VideoGenerator:
    """Generate MP4 videos from image directories with narration and transitions."""
    
    def __init__(
        self,
        output_resolution: tuple = (1920, 1080),
        fps: int = 30,
        default_image_duration: float = 5.0,
        transition_duration: float = 1.0,
        tts_rate: int = 150,
        tts_volume: float = 1.0
    ):
        """
        Initialize the Video Generator.
        
        Args:
            output_resolution: Video resolution (width, height)
            fps: Frames per second
            default_image_duration: Default duration for each image in seconds
            transition_duration: Duration of transitions in seconds
            tts_rate: Text-to-speech speech rate (words per minute)
            tts_volume: Text-to-speech volume (0.0 to 1.0)
        """
        self.output_resolution = output_resolution
        self.fps = fps
        self.default_image_duration = default_image_duration
        self.transition_duration = transition_duration
        self.tts_rate = tts_rate
        self.tts_volume = tts_volume
        self._selected_voice_id = None
        
        # Initialize TTS engine
        self.tts_engine = None
        self._init_tts()
        
    def _init_tts(self):
        """Initialize the text-to-speech engine."""
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', self.tts_rate)
            self.tts_engine.setProperty('volume', self.tts_volume)
            
            # List available voices
            voices = self.tts_engine.getProperty('voices')
            self.available_voices = [(v.id, v.name) for v in voices]
        except Exception as e:
            print(f"Warning: Could not initialize TTS engine: {e}")
            self.tts_engine = None
            self.available_voices = []
    
    def list_voices(self) -> List[tuple]:
        """List available TTS voices."""
        return self.available_voices
    
    def set_voice(self, voice_id: str):
        """Set the TTS voice by ID."""
        self._selected_voice_id = voice_id
        if self.tts_engine:
            self.tts_engine.setProperty('voice', voice_id)
    
    def get_images_from_directory(self, directory: str) -> List[Path]:
        """
        Get all image files from a directory.
        
        Args:
            directory: Path to the directory containing images
            
        Returns:
            List of image file paths, sorted by name
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        # Supported image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
        
        image_files = sorted([
            f for f in directory.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ])
        
        return image_files
    
    def _generate_narration_audio(self, text: str, output_path: str) -> Optional[str]:
        """
        Generate audio file from text using TTS.
        
        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            
        Returns:
            Path to the generated audio file, or None if failed
        """
        if not text.strip():
            return None
        
        try:
            # Reinitialize TTS engine for each file (fixes Windows crash issue)
            engine = pyttsx3.init()
            engine.setProperty('rate', self.tts_rate)
            engine.setProperty('volume', self.tts_volume)
            
            # Set voice if one was selected
            if hasattr(self, '_selected_voice_id') and self._selected_voice_id:
                engine.setProperty('voice', self._selected_voice_id)
            
            engine.save_to_file(text, output_path)
            engine.runAndWait()
            engine.stop()
            
            # Small delay to ensure file is written
            time.sleep(0.2)
            
            if Path(output_path).exists() and Path(output_path).stat().st_size > 0:
                return output_path
            else:
                print(f"Warning: Audio file was not created or is empty")
                return None
                
        except Exception as e:
            print(f"Warning: Could not generate narration audio: {e}")
            import traceback
            traceback.print_exc()
        
        return None
    
    def _resize_image_for_video(self, image_path: Path, target_size: tuple) -> Image.Image:
        """
        Resize image to fit target size while maintaining aspect ratio.
        Adds black letterboxing if needed.
        
        Args:
            image_path: Path to the image
            target_size: Target (width, height)
            
        Returns:
            PIL Image resized and letterboxed
        """
        img = Image.open(image_path)
        img_ratio = img.width / img.height
        target_ratio = target_size[0] / target_size[1]
        
        if img_ratio > target_ratio:
            # Image is wider - fit to width
            new_width = target_size[0]
            new_height = int(new_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = target_size[1]
            new_width = int(new_height * img_ratio)
        
        img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create black background and paste centered image
        background = Image.new('RGB', target_size, (0, 0, 0))
        paste_x = (target_size[0] - new_width) // 2
        paste_y = (target_size[1] - new_height) // 2
        
        # Handle images with alpha channel
        if img_resized.mode == 'RGBA':
            background.paste(img_resized, (paste_x, paste_y), img_resized)
        else:
            background.paste(img_resized, (paste_x, paste_y))
        
        return background
    
    def _create_image_clip(
        self, 
        image_path: Path, 
        duration: float,
        audio_path: Optional[str] = None
    ) -> tuple:
        """
        Create a video clip from an image.
        
        Args:
            image_path: Path to the image file
            duration: Duration of the clip in seconds
            audio_path: Optional path to audio file for narration
            
        Returns:
            Tuple of (ImageClip, AudioFileClip or None, actual_duration)
        """
        # Resize image to output resolution
        resized_img = self._resize_image_for_video(image_path, self.output_resolution)
        
        # Save to temp file for moviepy
        temp_img_path = tempfile.mktemp(suffix='.png')
        resized_img.save(temp_img_path)
        
        # Create image clip
        clip = ImageClip(temp_img_path, duration=duration)
        actual_duration = duration
        audio_clip = None
        
        # Load audio if provided
        if audio_path and Path(audio_path).exists():
            try:
                audio_clip = AudioFileClip(audio_path)
                # If audio is longer than image duration, extend the image duration
                if audio_clip.duration > duration:
                    actual_duration = audio_clip.duration + 0.5
                    clip = clip.with_duration(actual_duration)
            except Exception as e:
                print(f"Warning: Could not load audio clip: {e}")
                audio_clip = None
        
        # Clean up temp file after clip is created
        # Note: moviepy will read the file, so we can delete after ImageClip is created
        try:
            os.unlink(temp_img_path)
        except:
            pass
        
        return clip, audio_clip, actual_duration
    
    def _apply_transition(
        self, 
        clips: List[ImageClip], 
        transition: str
    ) -> List[ImageClip]:
        """
        Apply transitions between clips.
        
        Args:
            clips: List of image clips
            transition: Transition type
            
        Returns:
            List of clips with transitions applied
        """
        if transition == "none" or len(clips) <= 1:
            return clips
        
        transition_clips = []
        trans_dur = self.transition_duration
        
        for i, clip in enumerate(clips):
            if transition == "fade":
                # Fade out all clips except the last
                if i < len(clips) - 1:
                    clip = clip.with_effects([vfx.FadeOut(trans_dur)])
                # Fade in all clips except the first
                if i > 0:
                    clip = clip.with_effects([vfx.FadeIn(trans_dur)])
                    
            elif transition == "crossfade":
                # For crossfade, we'll use moviepy's crossfade features
                if i < len(clips) - 1:
                    clip = clip.with_effects([vfx.CrossFadeOut(trans_dur)])
                if i > 0:
                    clip = clip.with_effects([vfx.CrossFadeIn(trans_dur)])
            
            elif transition == "slide_left":
                if i > 0:
                    clip = clip.with_effects([vfx.SlideIn(trans_dur, "right")])
                    
            elif transition == "slide_right":
                if i > 0:
                    clip = clip.with_effects([vfx.SlideIn(trans_dur, "left")])
                    
            elif transition == "slide_up":
                if i > 0:
                    clip = clip.with_effects([vfx.SlideIn(trans_dur, "bottom")])
                    
            elif transition == "slide_down":
                if i > 0:
                    clip = clip.with_effects([vfx.SlideIn(trans_dur, "top")])
            
            transition_clips.append(clip)
        
        return transition_clips
    
    def interactive_setup(self, image_dir: str = None) -> Dict:
        """
        Interactive setup for video generation.
        Prompts user for narration, transitions, and settings.
        
        Args:
            image_dir: Directory containing images (will prompt if None)
            
        Returns:
            Dictionary with all settings and narration scripts
        """
        print("\n" + "="*60)
        print("VIDEO GENERATOR - Interactive Setup")
        print("="*60)
        
        # Get image directory
        if not image_dir:
            image_dir = input("\nEnter path to image directory: ").strip()
        
        try:
            images = self.get_images_from_directory(image_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            return None
        
        if not images:
            print(f"No image files found in: {image_dir}")
            return None
        
        print(f"\nFound {len(images)} image(s):")
        for i, img in enumerate(images, 1):
            print(f"  {i}. {img.name}")
        
        # Video settings
        print("\n" + "-"*60)
        print("VIDEO SETTINGS")
        print("-"*60)
        
        # Resolution
        print("\nSelect output resolution:")
        print("  1. 1920x1080 (Full HD) [default]")
        print("  2. 1280x720 (HD)")
        print("  3. 3840x2160 (4K)")
        print("  4. Custom")
        
        res_choice = input("Enter choice (1-4): ").strip() or "1"
        
        if res_choice == "2":
            self.output_resolution = (1280, 720)
        elif res_choice == "3":
            self.output_resolution = (3840, 2160)
        elif res_choice == "4":
            try:
                width = int(input("Enter width: ").strip())
                height = int(input("Enter height: ").strip())
                self.output_resolution = (width, height)
            except ValueError:
                print("Invalid input, using default 1920x1080")
                self.output_resolution = (1920, 1080)
        
        print(f"Resolution: {self.output_resolution[0]}x{self.output_resolution[1]}")
        
        # Default image duration
        try:
            duration_input = input("\nDefault image duration in seconds (default: 5): ").strip()
            if duration_input:
                self.default_image_duration = float(duration_input)
        except ValueError:
            print("Invalid input, using default 5 seconds")
        
        # Transition selection
        print("\n" + "-"*60)
        print("TRANSITIONS")
        print("-"*60)
        print("\nAvailable transitions:")
        for i, (key, desc) in enumerate(TRANSITIONS.items(), 1):
            print(f"  {i}. {key}: {desc}")
        
        trans_choice = input("\nSelect transition (1-7, default: 1): ").strip() or "1"
        transition_keys = list(TRANSITIONS.keys())
        
        try:
            transition_idx = int(trans_choice) - 1
            selected_transition = transition_keys[transition_idx] if 0 <= transition_idx < len(transition_keys) else "none"
        except ValueError:
            selected_transition = "none"
        
        print(f"Selected transition: {selected_transition}")
        
        if selected_transition != "none":
            try:
                trans_dur_input = input("Transition duration in seconds (default: 1): ").strip()
                if trans_dur_input:
                    self.transition_duration = float(trans_dur_input)
            except ValueError:
                print("Invalid input, using default 1 second")
        
        # Voice selection
        print("\n" + "-"*60)
        print("NARRATION SETTINGS")
        print("-"*60)
        
        enable_narration = input("\nEnable narration? (y/n, default: y): ").strip().lower() != 'n'
        
        selected_voice = None
        if enable_narration and self.available_voices:
            print("\nAvailable voices:")
            for i, (vid, vname) in enumerate(self.available_voices, 1):
                print(f"  {i}. {vname}")
            
            voice_choice = input(f"\nSelect voice (1-{len(self.available_voices)}, default: 1): ").strip() or "1"
            try:
                voice_idx = int(voice_choice) - 1
                if 0 <= voice_idx < len(self.available_voices):
                    selected_voice = self.available_voices[voice_idx][0]
                    self.set_voice(selected_voice)
                    print(f"Selected voice: {self.available_voices[voice_idx][1]}")
            except ValueError:
                pass
            
            # Speech rate
            try:
                rate_input = input("Speech rate (words per minute, default: 150): ").strip()
                if rate_input:
                    self.tts_rate = int(rate_input)
                    self.tts_engine.setProperty('rate', self.tts_rate)
            except ValueError:
                print("Invalid input, using default rate")
        
        # Collect narration for each image
        print("\n" + "-"*60)
        print("NARRATION SCRIPTS")
        print("-"*60)
        print("\nEnter narration for each image (press Enter to skip):")
        print("(Images without narration will use default duration)")
        print("-"*60)
        
        image_settings = []
        
        for i, img in enumerate(images, 1):
            print(f"\n[Image {i}/{len(images)}] {img.name}")
            
            narration = ""
            if enable_narration:
                print("Enter narration (multi-line, enter blank line to finish):")
                lines = []
                while True:
                    line = input()
                    if line == "":
                        break
                    lines.append(line)
                narration = "\n".join(lines)
            
            # Custom duration for this image
            custom_duration = None
            duration_prompt = input(f"Custom duration for this image? (default: {self.default_image_duration}s, or auto if narration): ").strip()
            if duration_prompt:
                try:
                    custom_duration = float(duration_prompt)
                except ValueError:
                    pass
            
            # Per-image transition (optional)
            custom_transition = None
            if i < len(images):  # No transition after last image
                use_custom = input(f"Use different transition after this image? (y/n, default: n): ").strip().lower()
                if use_custom == 'y':
                    print("Available transitions:")
                    for j, (key, desc) in enumerate(TRANSITIONS.items(), 1):
                        print(f"  {j}. {key}")
                    trans_idx = input("Select transition: ").strip()
                    try:
                        custom_transition = transition_keys[int(trans_idx) - 1]
                    except (ValueError, IndexError):
                        pass
            
            image_settings.append({
                "image_path": str(img),
                "narration": narration,
                "duration": custom_duration,
                "transition": custom_transition
            })
        
        # Output file
        print("\n" + "-"*60)
        print("OUTPUT")
        print("-"*60)
        
        default_output = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        output_file = input(f"\nOutput filename (default: {default_output}): ").strip() or default_output
        
        if not output_file.endswith('.mp4'):
            output_file += '.mp4'
        
        # Output directory
        output_dir = input("Output directory (default: same as images): ").strip()
        if not output_dir:
            output_dir = image_dir
        
        output_path = Path(output_dir) / output_file
        
        # Summary
        print("\n" + "="*60)
        print("CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Images: {len(images)} files from {image_dir}")
        print(f"Resolution: {self.output_resolution[0]}x{self.output_resolution[1]}")
        print(f"Default duration: {self.default_image_duration}s")
        print(f"Transition: {selected_transition} ({self.transition_duration}s)")
        print(f"Narration: {'Enabled' if enable_narration else 'Disabled'}")
        print(f"Output: {output_path}")
        print("="*60)
        
        confirm = input("\nProceed with video generation? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Video generation cancelled.")
            return None
        
        return {
            "images": image_settings,
            "output_path": str(output_path),
            "resolution": self.output_resolution,
            "default_duration": self.default_image_duration,
            "default_transition": selected_transition,
            "transition_duration": self.transition_duration,
            "enable_narration": enable_narration,
            "voice_id": selected_voice
        }
    
    def generate_video(self, config: Dict, progress_callback=None) -> Optional[str]:
        """
        Generate video from configuration.
        
        Args:
            config: Configuration dictionary from interactive_setup
            progress_callback: Optional callback function(current, total, message) for progress updates
            
        Returns:
            Path to generated video file, or None if failed
        """
        if not config:
            return None
        
        def report_progress(current, total, message):
            """Report progress if callback is provided."""
            print(message)
            if progress_callback:
                progress_callback(current, total, message)
        
        report_progress(0, 100, "\n" + "="*60)
        report_progress(0, 100, "GENERATING VIDEO")
        report_progress(0, 100, "="*60)
        
        temp_dir = tempfile.mkdtemp(prefix="video_gen_")
        clips = []
        audio_clips = []  # Store audio clips separately with start times
        current_time = 0.0  # Track cumulative time for audio positioning
        
        try:
            image_settings = config["images"]
            default_transition = config.get("default_transition", "none")
            total_images = len(image_settings)
            
            for i, img_config in enumerate(image_settings):
                image_path = Path(img_config["image_path"])
                narration = img_config.get("narration", "")
                custom_duration = img_config.get("duration")
                
                progress_pct = int((i / total_images) * 70)  # 0-70% for image processing
                report_progress(progress_pct, 100, f"\n[{i+1}/{total_images}] Processing: {image_path.name}")
                
                # Generate narration audio if provided
                audio_path = None
                if narration and config.get("enable_narration", True):
                    report_progress(progress_pct, 100, f"  Generating narration audio...")
                    audio_path = os.path.join(temp_dir, f"narration_{i}.wav")
                    audio_path = self._generate_narration_audio(narration, audio_path)
                    if audio_path:
                        report_progress(progress_pct, 100, f"  Narration audio generated")
                
                # Determine base duration
                if custom_duration:
                    duration = custom_duration
                elif audio_path:
                    # Use audio duration + padding
                    try:
                        temp_audio = AudioFileClip(audio_path)
                        duration = temp_audio.duration + 1.0
                        temp_audio.close()
                    except:
                        duration = self.default_image_duration
                else:
                    duration = self.default_image_duration
                
                report_progress(progress_pct, 100, f"  Duration: {duration:.1f}s")
                
                # Create image clip (returns video clip, audio clip, actual duration)
                report_progress(progress_pct, 100, f"  Creating video clip...")
                clip, audio_clip, actual_duration = self._create_image_clip(image_path, duration, audio_path)
                clips.append(clip)
                
                # Store audio with its start time for later composition
                if audio_clip is not None:
                    audio_clips.append((audio_clip, current_time))
                    report_progress(progress_pct, 100, f"  Audio clip added at {current_time:.1f}s")
                
                current_time += actual_duration
            
            if not clips:
                report_progress(0, 100, "No clips created!")
                return None
            
            # Apply transitions
            report_progress(75, 100, f"\nApplying transitions ({default_transition})...")
            clips = self._apply_transition(clips, default_transition)
            
            # Concatenate clips
            report_progress(80, 100, "Concatenating clips...")
            
            if default_transition in ["crossfade", "fade"]:
                # For crossfade/fade, use composition method with overlap
                # But for simplicity, we'll concatenate with the fade effects already applied
                final_video = concatenate_videoclips(clips, method="compose")
            else:
                final_video = concatenate_videoclips(clips, method="compose")
            
            # Compose and attach audio tracks
            if audio_clips:
                report_progress(82, 100, f"Compositing {len(audio_clips)} audio track(s)...")
                try:
                    # Position each audio clip at its correct start time
                    positioned_audios = []
                    for audio_clip, start_time in audio_clips:
                        positioned_audio = audio_clip.with_start(start_time)
                        positioned_audios.append(positioned_audio)
                    
                    # Create composite audio from all positioned clips
                    composite_audio = CompositeAudioClip(positioned_audios)
                    final_video = final_video.with_audio(composite_audio)
                    report_progress(83, 100, "Audio tracks attached successfully")
                except Exception as e:
                    report_progress(83, 100, f"Warning: Could not attach audio: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Write output file
            output_path = config["output_path"]
            report_progress(85, 100, f"\nRendering video to: {output_path}")
            report_progress(85, 100, "This may take a few minutes...")
            
            final_video.write_videofile(
                output_path,
                fps=self.fps,
                codec='libx264',
                audio_codec='aac'
            )
            
            # Close clips
            final_video.close()
            for clip in clips:
                clip.close()
            # Close audio clips
            for audio_clip, _ in audio_clips:
                try:
                    audio_clip.close()
                except:
                    pass
            
            report_progress(100, 100, "\n" + "="*60)
            report_progress(100, 100, "VIDEO GENERATION COMPLETE")
            report_progress(100, 100, f"Output: {output_path}")
            report_progress(100, 100, "="*60)
            
            return output_path
            
        except Exception as e:
            report_progress(0, 100, f"\nError generating video: {e}")
            import traceback
            traceback.print_exc()
            return None
            
        finally:
            # Clean up temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    def generate_from_workflow(self, workflow_path: str, output_path: str = None) -> Optional[str]:
        """
        Generate video from a workflow JSON file (screenshots captured by the automater).
        
        Args:
            workflow_path: Path to workflow.json file
            output_path: Output path for video (optional)
            
        Returns:
            Path to generated video file, or None if failed
        """
        workflow_path = Path(workflow_path)
        
        if not workflow_path.exists():
            print(f"Workflow file not found: {workflow_path}")
            return None
        
        try:
            with open(workflow_path, 'r') as f:
                data = json.load(f)
            
            clicks = data.get("clicks", [])
            if not clicks:
                print("No screenshots found in workflow")
                return None
            
            # Extract image paths
            image_dir = workflow_path.parent
            images = []
            
            for click in clicks:
                screenshot = click.get("screenshot")
                if screenshot:
                    img_path = Path(screenshot)
                    if not img_path.is_absolute():
                        img_path = image_dir / screenshot
                    if img_path.exists():
                        images.append(img_path)
            
            if not images:
                print("No valid screenshot files found in workflow")
                return None
            
            print(f"Found {len(images)} screenshots in workflow")
            
            # Run interactive setup with the images
            return self.interactive_setup(str(image_dir))
            
        except json.JSONDecodeError as e:
            print(f"Error parsing workflow file: {e}")
            return None
    
    def save_project(self, config: Dict, project_path: str):
        """
        Save video project configuration for later editing.
        
        Args:
            config: Configuration dictionary
            project_path: Path to save project file
        """
        with open(project_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Project saved to: {project_path}")
    
    def load_project(self, project_path: str) -> Optional[Dict]:
        """
        Load a saved video project configuration.
        
        Args:
            project_path: Path to project file
            
        Returns:
            Configuration dictionary, or None if failed
        """
        try:
            with open(project_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading project: {e}")
            return None


def main():
    """Standalone entry point for video generator."""
    print("\n" + "="*60)
    print("VIDEO GENERATOR")
    print("Create MP4 videos from images with narration and transitions")
    print("="*60)
    
    print("\nOptions:")
    print("  1. Create video from image directory")
    print("  2. Create video from workflow (screenshots)")
    print("  3. Load saved project")
    print("  4. Exit")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    generator = VideoGenerator()
    
    if choice == "1":
        image_dir = input("\nEnter path to image directory: ").strip()
        config = generator.interactive_setup(image_dir)
        
        if config:
            # Offer to save project
            save_project = input("\nSave project for later editing? (y/n): ").strip().lower()
            if save_project == 'y':
                project_path = input("Project file path (default: video_project.json): ").strip() or "video_project.json"
                generator.save_project(config, project_path)
            
            # Generate video
            generator.generate_video(config)
            
    elif choice == "2":
        workflow_path = input("\nEnter path to workflow.json: ").strip()
        config = generator.generate_from_workflow(workflow_path)
        
        if config:
            generator.generate_video(config)
            
    elif choice == "3":
        project_path = input("\nEnter path to project file: ").strip()
        config = generator.load_project(project_path)
        
        if config:
            print("\nLoaded project configuration.")
            edit = input("Edit configuration before generating? (y/n): ").strip().lower()
            
            if edit == 'y':
                # Re-run interactive setup with existing images
                if config.get("images"):
                    image_dir = str(Path(config["images"][0]["image_path"]).parent)
                    config = generator.interactive_setup(image_dir)
            
            if config:
                generator.generate_video(config)
    else:
        print("Exiting...")


if __name__ == "__main__":
    main()
