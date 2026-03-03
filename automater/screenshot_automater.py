"""
Screenshot Automater - Capture screenshots on click and replay workflows
"""

import os
import sys
import json
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

try:
    from pynput import mouse
    from pynput.mouse import Button, Controller as MouseController
    import pyautogui
    from PIL import Image
    from screeninfo import get_monitors
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install dependencies: pip install -r requirements.txt")
    sys.exit(1)


class ScreenshotAutomater:
    """Main class for capturing screenshots and managing workflows."""
    
    def __init__(
        self,
        output_dir: str = "screenshots",
        naming_pattern: str = "{timestamp}_{count}",
        image_format: str = "png"
    ):
        """
        Initialize the Screenshot Automater.
        
        Args:
            output_dir: Directory to save screenshots
            naming_pattern: Pattern for naming files. Supports:
                - {timestamp}: Current timestamp (YYYYMMDD_HHMMSS)
                - {count}: Sequential click counter
                - {x}: X coordinate of click
                - {y}: Y coordinate of click
                - {date}: Date (YYYY-MM-DD)
                - {time}: Time (HH-MM-SS)
            image_format: Image format (png, jpg, bmp)
        """
        self.output_dir = Path(output_dir)
        self.naming_pattern = naming_pattern
        self.image_format = image_format.lower()
        self.click_count = 0
        self.workflow = []
        self.is_recording = False
        self.is_paused = False
        self.listener: Optional[mouse.Listener] = None
        self.mouse_controller = MouseController()
        self.session_start_time = None
        self.workflow_file = "workflow.json"
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def _generate_filename(self, x: int, y: int) -> str:
        """Generate filename based on the naming pattern."""
        now = datetime.now()
        
        replacements = {
            "{timestamp}": now.strftime("%Y%m%d_%H%M%S"),
            "{count}": str(self.click_count).zfill(4),
            "{x}": str(x),
            "{y}": str(y),
            "{date}": now.strftime("%Y-%m-%d"),
            "{time}": now.strftime("%H-%M-%S"),
        }
        
        filename = self.naming_pattern
        for pattern, value in replacements.items():
            filename = filename.replace(pattern, value)
            
        return f"{filename}.{self.image_format}"
    
    def _capture_screenshot(self, x: int, y: int) -> Optional[str]:
        """Capture a screenshot and save it to the output directory."""
        try:
            self.click_count += 1
            filename = self._generate_filename(x, y)
            filepath = self.output_dir / filename
            
            # Small delay to ensure the click action is visible
            time.sleep(0.1)
            
            # Capture screenshot
            screenshot = pyautogui.screenshot()
            screenshot.save(str(filepath))
            
            print(f"  Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"  Error capturing screenshot: {e}")
            return None
    
    def _get_monitor_info(self, x: int, y: int) -> dict:
        """
        Determine which monitor contains the given coordinates.
        
        Returns:
            dict: Monitor information including resolution for scaling
        """
        try:
            monitors = get_monitors()
            for i, monitor in enumerate(monitors, 1):
                if (monitor.x <= x < monitor.x + monitor.width and
                    monitor.y <= y < monitor.y + monitor.height):
                    name = monitor.name or f"Monitor {i}"
                    return {
                        "number": i,
                        "name": name,
                        "info": f"Monitor {i}: {name} ({monitor.width}x{monitor.height})",
                        "width": monitor.width,
                        "height": monitor.height,
                        "x_offset": monitor.x,
                        "y_offset": monitor.y,
                        "is_primary": monitor.is_primary
                    }
            # If not found in any monitor bounds, return primary info
            primary = monitors[0] if monitors else None
            return {
                "number": 1,
                "name": "Unknown",
                "info": "Monitor 1 (primary)",
                "width": primary.width if primary else 1920,
                "height": primary.height if primary else 1080,
                "x_offset": 0,
                "y_offset": 0,
                "is_primary": True
            }
        except Exception:
            return {
                "number": 1,
                "name": "Unknown",
                "info": "Monitor detection unavailable",
                "width": 1920,
                "height": 1080,
                "x_offset": 0,
                "y_offset": 0,
                "is_primary": True
            }
    
    def _list_monitors(self):
        """Print information about all connected monitors."""
        try:
            monitors = get_monitors()
            print(f"\nDetected {len(monitors)} monitor(s):")
            for i, monitor in enumerate(monitors, 1):
                name = monitor.name or f"Display {i}"
                primary = " (primary)" if monitor.is_primary else ""
                print(f"  {i}. {name}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y}){primary}")
        except Exception as e:
            print(f"Could not detect monitors: {e}")
    
    def _on_click(self, x: int, y: int, button: Button, pressed: bool):
        """Handle mouse click events."""
        # Only capture on button press (not release), and only left clicks
        if not pressed or button != Button.left:
            return
            
        if self.is_paused:
            return
        
        # Get monitor information
        monitor_info = self._get_monitor_info(x, y)
        print(f"Click detected at ({x}, {y}) - {monitor_info['info']}")
        
        # Calculate relative position within the monitor (0.0-1.0) for scaling
        rel_x = (x - monitor_info["x_offset"]) / monitor_info["width"]
        rel_y = (y - monitor_info["y_offset"]) / monitor_info["height"]
        
        # Record the click position and time
        click_data = {
            "x": x,
            "y": y,
            "rel_x": rel_x,  # Relative X position (0.0-1.0) for scaling
            "rel_y": rel_y,  # Relative Y position (0.0-1.0) for scaling
            "monitor": monitor_info["number"],
            "monitor_name": monitor_info["name"],
            "monitor_width": monitor_info["width"],
            "monitor_height": monitor_info["height"],
            "monitor_x_offset": monitor_info["x_offset"],
            "monitor_y_offset": monitor_info["y_offset"],
            "time": time.time() - self.session_start_time,
            "timestamp": datetime.now().isoformat()
        }
        
        # Capture screenshot
        filepath = self._capture_screenshot(x, y)
        if filepath:
            click_data["screenshot"] = filepath
            
        self.workflow.append(click_data)
    
    def start_recording(self):
        """Start recording clicks and capturing screenshots."""
        if self.is_recording:
            print("Already recording!")
            return
            
        self.is_recording = True
        self.is_paused = False
        self.click_count = 0
        self.workflow = []
        self.session_start_time = time.time()
        
        print("\n" + "="*50)
        print("SCREENSHOT AUTOMATER - RECORDING STARTED")
        print("="*50)
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Naming pattern: {self.naming_pattern}")
        print(f"Image format: {self.image_format}")
        self._list_monitors()
        print("-"*50)
        print("Controls:")
        print("  - Click anywhere to capture a screenshot")
        print("  - Press Ctrl+C in terminal to stop recording")
        print("="*50 + "\n")
        
        # Start mouse listener
        self.listener = mouse.Listener(on_click=self._on_click)
        self.listener.start()
        
        try:
            # Keep the main thread alive
            while self.is_recording:
                time.sleep(0.1)
        except KeyboardInterrupt:
            self.stop_recording()
    
    def stop_recording(self):
        """Stop recording and save the workflow."""
        if not self.is_recording:
            return
            
        self.is_recording = False
        
        if self.listener:
            self.listener.stop()
            self.listener = None
        
        # Save workflow to file
        self._save_workflow()
        
        print("\n" + "="*50)
        print("RECORDING STOPPED")
        print(f"Total screenshots captured: {self.click_count}")
        print(f"Workflow saved to: {self.workflow_file}")
        print("="*50 + "\n")
        
        # Prompt user for post-capture action
        self._prompt_post_capture_action()
    
    def _save_workflow(self):
        """Save the recorded workflow to a JSON file."""
        workflow_data = {
            "session_info": {
                "start_time": datetime.fromtimestamp(self.session_start_time).isoformat() if self.session_start_time else None,
                "total_clicks": self.click_count,
                "output_dir": str(self.output_dir.absolute()),
                "naming_pattern": self.naming_pattern,
                "image_format": self.image_format
            },
            "clicks": self.workflow
        }
        
        workflow_path = self.output_dir / self.workflow_file
        with open(workflow_path, 'w') as f:
            json.dump(workflow_data, f, indent=2)
    
    def _prompt_post_capture_action(self):
        """Prompt user for action after capture completes."""
        if self.click_count == 0:
            return
            
        print("\nWhat would you like to do with the captured files?")
        print("  1. Open destination folder in File Explorer")
        print("  2. Import files into a Camtasia project")
        print("  3. Delete all captured screenshots")
        print("  4. Do nothing (exit)")
        
        try:
            choice = input("\nEnter choice (1-4): ").strip()
            
            if choice == "1":
                self._open_in_explorer()
            elif choice == "2":
                self._import_to_camtasia()
            elif choice == "3":
                self._delete_captured_screenshots()
            else:
                print("Done.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
    
    def _open_in_explorer(self):
        """Open the output directory in Windows File Explorer."""
        folder_path = self.output_dir.absolute()
        
        try:
            if sys.platform == "win32":
                os.startfile(str(folder_path))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder_path)], check=True)
            else:
                subprocess.run(["xdg-open", str(folder_path)], check=True)
            print(f"Opened folder: {folder_path}")
        except Exception as e:
            print(f"Error opening folder: {e}")
            print(f"You can manually navigate to: {folder_path}")
    
    def _delete_captured_screenshots(self):
        """Delete all captured screenshots from this session."""
        folder_path = self.output_dir.absolute()
        
        # Get list of captured screenshot files
        screenshot_files = sorted([
            f for f in folder_path.iterdir()
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']
        ])
        
        if not screenshot_files:
            print("No screenshot files found to delete.")
            return
        
        print(f"\nThis will delete {len(screenshot_files)} screenshot(s):")
        for f in screenshot_files[:5]:
            print(f"  - {f.name}")
        if len(screenshot_files) > 5:
            print(f"  ... and {len(screenshot_files) - 5} more")
        
        confirm = input("\nAre you sure you want to delete these files? (y/n): ").strip().lower()
        
        if confirm == 'y':
            deleted_count = 0
            for f in screenshot_files:
                try:
                    f.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {f.name}: {e}")
            
            # Also delete the workflow file if it exists
            workflow_path = folder_path / self.workflow_file
            if workflow_path.exists():
                try:
                    workflow_path.unlink()
                    print(f"Deleted workflow file: {self.workflow_file}")
                except Exception as e:
                    print(f"Error deleting workflow file: {e}")
            
            print(f"\nDeleted {deleted_count} screenshot(s).")
            
            # Check if folder is empty and offer to delete it
            remaining = list(folder_path.iterdir())
            if not remaining:
                delete_folder = input("Folder is now empty. Delete the folder too? (y/n): ").strip().lower()
                if delete_folder == 'y':
                    try:
                        folder_path.rmdir()
                        print(f"Deleted folder: {folder_path}")
                    except Exception as e:
                        print(f"Error deleting folder: {e}")
        else:
            print("Deletion cancelled.")

    def _import_to_camtasia(self):
        """Import captured screenshots into a Camtasia project."""
        folder_path = self.output_dir.absolute()
        
        # Get list of captured screenshot files
        screenshot_files = sorted([
            f for f in folder_path.iterdir()
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp']
        ])
        
        if not screenshot_files:
            print("No screenshot files found to import.")
            return
        
        print(f"\nFound {len(screenshot_files)} screenshot(s) to import.")
        
        # Try to find Camtasia installation
        camtasia_paths = [
            r"C:\Program Files\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2023\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2022\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2021\CamtasiaStudio.exe",
            r"C:\Program Files\TechSmith\Camtasia 2020\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2025\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2024\CamtasiaStudio.exe",
            r"C:\Program Files (x86)\TechSmith\Camtasia 2023\CamtasiaStudio.exe",
        ]
        
        camtasia_exe = None
        for path in camtasia_paths:
            if Path(path).exists():
                camtasia_exe = path
                break
        
        if not camtasia_exe:
            print("Camtasia installation not found in standard locations.")
            custom_path = input("\nEnter path to Camtasia installation folder (or press Enter to skip): ").strip()
            
            if custom_path:
                # Try to find the executable in the provided path
                custom_path = Path(custom_path)
                possible_exe = custom_path / "CamtasiaStudio.exe"
                if possible_exe.exists():
                    camtasia_exe = str(possible_exe)
                elif custom_path.exists() and custom_path.suffix.lower() == '.exe':
                    # User provided direct path to exe
                    camtasia_exe = str(custom_path)
                else:
                    print(f"Could not find CamtasiaStudio.exe in: {custom_path}")
        
        if camtasia_exe:
            print(f"Found Camtasia at: {camtasia_exe}")
            print("\nOptions:")
            print("  1. Open Camtasia and File Explorer (drag files to Media Bin)")
            print("  2. Open Camtasia and copy file paths to clipboard")
            
            sub_choice = input("\nEnter choice (1-2): ").strip()
            
            if sub_choice == "1":
                # Open Camtasia and then open explorer with files selected
                try:
                    subprocess.Popen([camtasia_exe])
                    print("Camtasia is starting...")
                    time.sleep(2)
                    # Open explorer with first file selected
                    subprocess.run(["explorer", "/select,", str(screenshot_files[0])], check=False)
                    print("File Explorer opened. Select all files and drag them to the Camtasia Media Bin.")
                except Exception as e:
                    print(f"Error launching Camtasia: {e}")
            else:
                self._copy_files_to_clipboard(screenshot_files, camtasia_exe)
        else:
            print("\nOptions:")
            print("  1. Copy file paths to clipboard (for pasting into Camtasia Import)")
            print("  2. Open folder in File Explorer instead")
            
            sub_choice = input("\nEnter choice (1-2): ").strip()
            
            if sub_choice == "1":
                self._copy_files_to_clipboard(screenshot_files, None)
            else:
                self._open_in_explorer()
    
    def _copy_files_to_clipboard(self, screenshot_files: list, camtasia_exe: str = None):
        """Copy file paths to clipboard and optionally open Camtasia."""
        try:
            import pyperclip
            
            # Format paths for clipboard - use quotes and separate by newlines
            file_paths = "\n".join([f'"{f.absolute()}"' for f in screenshot_files])
            pyperclip.copy(file_paths)
            
            print(f"\nCopied {len(screenshot_files)} file path(s) to clipboard!")
            print("\nTo import into Camtasia:")
            print("  1. In Camtasia, go to File > Import > Media...")
            print("  2. In the file dialog, paste (Ctrl+V) the paths into the filename field")
            print("  3. Click Open to import all files")
            
            if camtasia_exe:
                open_camtasia = input("\nOpen Camtasia now? (y/n): ").strip().lower()
                if open_camtasia == 'y':
                    subprocess.Popen([camtasia_exe])
                    print("Camtasia is starting...")
                    
        except ImportError:
            print("pyperclip not available. File paths:")
            for f in screenshot_files:
                print(f"  {f.absolute()}")
        except Exception as e:
            print(f"Error copying to clipboard: {e}")

    def _get_current_monitors(self) -> dict:
        """Get information about all current monitors for coordinate scaling."""
        monitors_info = {}
        try:
            monitors = get_monitors()
            for i, monitor in enumerate(monitors, 1):
                monitors_info[i] = {
                    "width": monitor.width,
                    "height": monitor.height,
                    "x_offset": monitor.x,
                    "y_offset": monitor.y,
                    "name": monitor.name or f"Monitor {i}",
                    "is_primary": monitor.is_primary
                }
        except Exception:
            # Fallback to a default monitor
            monitors_info[1] = {
                "width": 1920,
                "height": 1080,
                "x_offset": 0,
                "y_offset": 0,
                "name": "Default",
                "is_primary": True
            }
        return monitors_info

    def _scale_coordinates(self, click: dict, current_monitors: dict) -> tuple:
        """
        Scale click coordinates from recorded resolution to current resolution.
        
        Uses relative coordinates (rel_x, rel_y) if available for accurate scaling,
        otherwise falls back to proportional scaling based on monitor dimensions.
        
        Args:
            click: Click data from workflow
            current_monitors: Current monitor configuration
            
        Returns:
            tuple: (scaled_x, scaled_y)
        """
        original_monitor = click.get("monitor", 1)
        
        # Check if we have relative coordinates (new format)
        if "rel_x" in click and "rel_y" in click:
            # Use relative coordinates for accurate replay
            rel_x = click["rel_x"]
            rel_y = click["rel_y"]
            
            # Find a matching monitor or use primary/first available
            if original_monitor in current_monitors:
                curr_mon = current_monitors[original_monitor]
            elif 1 in current_monitors:
                curr_mon = current_monitors[1]
            else:
                curr_mon = list(current_monitors.values())[0]
            
            # Scale relative coordinates to current monitor
            new_x = int(curr_mon["x_offset"] + rel_x * curr_mon["width"])
            new_y = int(curr_mon["y_offset"] + rel_y * curr_mon["height"])
            return (new_x, new_y)
        
        # Fallback: Proportional scaling based on recorded monitor dimensions
        orig_width = click.get("monitor_width")
        orig_height = click.get("monitor_height")
        orig_x_offset = click.get("monitor_x_offset", 0)
        orig_y_offset = click.get("monitor_y_offset", 0)
        
        if orig_width and orig_height:
            # Find matching current monitor
            if original_monitor in current_monitors:
                curr_mon = current_monitors[original_monitor]
            elif 1 in current_monitors:
                curr_mon = current_monitors[1]
            else:
                curr_mon = list(current_monitors.values())[0]
            
            # Calculate position relative to the original monitor
            rel_x = (click["x"] - orig_x_offset) / orig_width
            rel_y = (click["y"] - orig_y_offset) / orig_height
            
            # Apply to current monitor
            new_x = int(curr_mon["x_offset"] + rel_x * curr_mon["width"])
            new_y = int(curr_mon["y_offset"] + rel_y * curr_mon["height"])
            return (new_x, new_y)
        
        # No scaling info available - use original coordinates
        return (click["x"], click["y"])

    def load_workflow(self, workflow_path: str = None) -> bool:
        """Load a previously recorded workflow."""
        if workflow_path is None:
            workflow_path = self.output_dir / self.workflow_file
        else:
            workflow_path = Path(workflow_path)
            
        if not workflow_path.exists():
            print(f"Workflow file not found: {workflow_path}")
            return False
            
        try:
            with open(workflow_path, 'r') as f:
                data = json.load(f)
                
            self.workflow = data.get("clicks", [])
            session_info = data.get("session_info", {})
            
            print(f"Loaded workflow with {len(self.workflow)} clicks")
            print(f"Original session: {session_info.get('start_time', 'Unknown')}")
            return True
            
        except Exception as e:
            print(f"Error loading workflow: {e}")
            return False
    
    def replay_workflow(
        self,
        workflow_path: str = None,
        output_dir: str = None,
        delay_multiplier: float = 1.0,
        min_delay: float = 0.5,
        capture_screenshots: bool = True
    ):
        """
        Replay a recorded workflow, optionally capturing new screenshots.
        
        Args:
            workflow_path: Path to workflow JSON file
            output_dir: Directory for new screenshots (if None, uses replay_<timestamp>)
            delay_multiplier: Multiply original delays by this factor
            min_delay: Minimum delay between clicks in seconds
            capture_screenshots: Whether to capture screenshots during replay
        """
        if not self.load_workflow(workflow_path):
            return
            
        if len(self.workflow) == 0:
            print("No clicks in workflow to replay")
            return
            
        # Set up output directory for replay
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(f"replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.click_count = 0
        
        print("\n" + "="*50)
        print("WORKFLOW REPLAY STARTING")
        print("="*50)
        print(f"Replaying {len(self.workflow)} clicks")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Delay multiplier: {delay_multiplier}x")
        print(f"Minimum delay: {min_delay}s")
        print("-"*50)
        
        # Get current monitor configuration for coordinate scaling
        current_monitors = self._get_current_monitors()
        has_scaling_info = any("rel_x" in click or "monitor_width" in click for click in self.workflow)
        
        if has_scaling_info:
            print("Resolution scaling: ENABLED (coordinates will be adjusted)")
        else:
            print("Resolution scaling: DISABLED (legacy workflow - re-record for scaling)")
        
        self._list_monitors()
        print("-"*50)
        print("Starting in 3 seconds... (move mouse to corner to abort)")
        print("="*50 + "\n")
        
        time.sleep(3)
        
        previous_time = 0
        
        for i, click in enumerate(self.workflow):
            # Check for abort (mouse in corner)
            try:
                pyautogui.failsafe = True
            except pyautogui.FailSafeException:
                print("\nReplay aborted by user (mouse moved to corner)")
                break
            
            # Scale coordinates to current resolution
            x, y = self._scale_coordinates(click, current_monitors)
            orig_x, orig_y = click["x"], click["y"]
            click_time = click.get("time", 0)
            
            # Calculate delay
            if i > 0:
                delay = (click_time - previous_time) * delay_multiplier
                delay = max(delay, min_delay)
                print(f"Waiting {delay:.2f}s before next click...")
                time.sleep(delay)
            
            previous_time = click_time
            
            if (x, y) != (orig_x, orig_y):
                print(f"[{i+1}/{len(self.workflow)}] Clicking at ({x}, {y}) [scaled from ({orig_x}, {orig_y})]")
            else:
                print(f"[{i+1}/{len(self.workflow)}] Clicking at ({x}, {y})")
            
            # Move mouse and click
            pyautogui.moveTo(x, y, duration=0.2)
            pyautogui.click(x, y)
            
            # Capture screenshot if enabled
            if capture_screenshots:
                self._capture_screenshot(x, y)
        
        print("\n" + "="*50)
        print("REPLAY COMPLETED")
        print(f"Screenshots captured: {self.click_count}")
        print(f"Saved to: {self.output_dir.absolute()}")
        print("="*50 + "\n")
        
        # Prompt user for post-capture action
        if capture_screenshots:
            self._prompt_post_capture_action()


def main():
    """Main entry point with CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Screenshot Automater - Capture screenshots on click and replay workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Naming Pattern Variables:
  {timestamp}  - Full timestamp (YYYYMMDD_HHMMSS)
  {count}      - Sequential click counter (0001, 0002, ...)
  {x}          - X coordinate of click
  {y}          - Y coordinate of click
  {date}       - Date (YYYY-MM-DD)
  {time}       - Time (HH-MM-SS)

Examples:
  Record screenshots:
    python screenshot_automater.py record -o my_screenshots -n "step_{count}"
    
  Replay a workflow:
    python screenshot_automater.py replay -w my_screenshots/workflow.json
    
  Replay with custom output:
    python screenshot_automater.py replay -w workflow.json -o new_screenshots --delay 2.0
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Record command
    record_parser = subparsers.add_parser("record", help="Record clicks and capture screenshots")
    record_parser.add_argument(
        "-o", "--output",
        default="screenshots",
        help="Output directory for screenshots (default: screenshots)"
    )
    record_parser.add_argument(
        "-n", "--naming",
        default="{timestamp}_{count}",
        help="Naming pattern for screenshots (default: {timestamp}_{count})"
    )
    record_parser.add_argument(
        "-f", "--format",
        default="png",
        choices=["png", "jpg", "bmp"],
        help="Image format (default: png)"
    )
    
    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a recorded workflow")
    replay_parser.add_argument(
        "-w", "--workflow",
        help="Path to workflow JSON file"
    )
    replay_parser.add_argument(
        "-o", "--output",
        help="Output directory for new screenshots"
    )
    replay_parser.add_argument(
        "-d", "--delay",
        type=float,
        default=1.0,
        help="Delay multiplier (default: 1.0)"
    )
    replay_parser.add_argument(
        "-m", "--min-delay",
        type=float,
        default=0.5,
        help="Minimum delay between clicks in seconds (default: 0.5)"
    )
    replay_parser.add_argument(
        "--no-capture",
        action="store_true",
        help="Don't capture screenshots during replay"
    )
    
    # Video command
    video_parser = subparsers.add_parser("video", help="Create video from images with narration")
    video_parser.add_argument(
        "-i", "--input",
        help="Path to image directory or workflow JSON file"
    )
    video_parser.add_argument(
        "-o", "--output",
        help="Output video file path"
    )
    video_parser.add_argument(
        "-p", "--project",
        help="Load a saved video project file"
    )
    
    # Editor command (GUI)
    editor_parser = subparsers.add_parser("editor", help="Open visual editor for adding narration to images")
    editor_parser.add_argument(
        "-i", "--input",
        help="Path to image directory to load on startup"
    )
    editor_parser.add_argument(
        "-p", "--project",
        help="Load a saved project file on startup"
    )
    
    # GUI command
    gui_parser = subparsers.add_parser("gui", help="Open the main graphical user interface")
    
    args = parser.parse_args()
    
    if args.command == "record":
        automater = ScreenshotAutomater(
            output_dir=args.output,
            naming_pattern=args.naming,
            image_format=args.format
        )
        automater.start_recording()
        
    elif args.command == "replay":
        automater = ScreenshotAutomater()
        automater.replay_workflow(
            workflow_path=args.workflow,
            output_dir=args.output,
            delay_multiplier=args.delay,
            min_delay=args.min_delay,
            capture_screenshots=not args.no_capture
        )
    elif args.command == "video":
        from video_generator import VideoGenerator
        generator = VideoGenerator()
        
        if args.project:
            # Load saved project
            config = generator.load_project(args.project)
            if config:
                generator.generate_video(config)
        elif args.input:
            input_path = Path(args.input)
            if input_path.suffix.lower() == '.json':
                # Load from workflow
                config = generator.generate_from_workflow(str(input_path))
            else:
                # Load from image directory
                config = generator.interactive_setup(str(input_path))
            
            if config:
                generator.generate_video(config)
        else:
            # Interactive setup
            config = generator.interactive_setup()
            if config:
                generator.generate_video(config)
    elif args.command == "editor":
        from video_editor_gui import VideoEditorGUI
        app = VideoEditorGUI()
        
        if args.project:
            # Load project on startup
            app.root.after(100, lambda: app._load_project_file(args.project))
        elif args.input:
            # Load images on startup
            app.root.after(100, lambda: app._load_images(args.input))
        
        app.run()
    elif args.command == "gui":
        from screenshot_automater_gui import ScreenshotAutomaterGUI
        print("Launching Screenshot Automater GUI...")
        app = ScreenshotAutomaterGUI()
        app.run()
    else:
        # Interactive mode
        print("\n" + "="*50)
        print("SCREENSHOT AUTOMATER - Interactive Mode")
        print("="*50)
        
        print("\nSelect mode:")
        print("  1. Record - Capture screenshots on click")
        print("  2. Replay - Replay a recorded workflow")
        print("  3. Video - Create video from images with narration")
        print("  4. Video Editor (GUI) - Visual editor for adding narration")
        print("  5. Main GUI - Open the full graphical interface")
        print("  6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            output_dir = input("Output directory (default: screenshots): ").strip() or "screenshots"
            naming = input("Naming pattern (default: {timestamp}_{count}): ").strip() or "{timestamp}_{count}"
            format_choice = input("Image format (png/jpg/bmp, default: png): ").strip() or "png"
            
            automater = ScreenshotAutomater(
                output_dir=output_dir,
                naming_pattern=naming,
                image_format=format_choice
            )
            automater.start_recording()
            
        elif choice == "2":
            workflow_path = input("Workflow file path (or press Enter for default): ").strip() or None
            output_dir = input("Output directory (or press Enter for auto): ").strip() or None
            
            automater = ScreenshotAutomater()
            automater.replay_workflow(
                workflow_path=workflow_path,
                output_dir=output_dir
            )
        elif choice == "3":
            from video_generator import VideoGenerator
            generator = VideoGenerator()
            
            print("\nVideo generation options:")
            print("  1. Create video from image directory")
            print("  2. Create video from workflow (screenshots)")
            print("  3. Load saved project")
            
            video_choice = input("\nEnter choice (1-3): ").strip()
            
            if video_choice == "1":
                image_dir = input("\nEnter path to image directory: ").strip()
                config = generator.interactive_setup(image_dir)
                if config:
                    save_proj = input("\nSave project for later editing? (y/n): ").strip().lower()
                    if save_proj == 'y':
                        proj_path = input("Project file path (default: video_project.json): ").strip() or "video_project.json"
                        generator.save_project(config, proj_path)
                    generator.generate_video(config)
                    
            elif video_choice == "2":
                workflow_path = input("\nEnter path to workflow.json: ").strip()
                config = generator.generate_from_workflow(workflow_path)
                if config:
                    generator.generate_video(config)
                    
            elif video_choice == "3":
                project_path = input("\nEnter path to project file: ").strip()
                config = generator.load_project(project_path)
                if config:
                    generator.generate_video(config)
        elif choice == "4":
            from video_editor_gui import VideoEditorGUI
            print("\nLaunching Video Narration Editor...")
            app = VideoEditorGUI()
            app.run()
        elif choice == "5":
            from screenshot_automater_gui import ScreenshotAutomaterGUI
            print("\nLaunching Screenshot Automater GUI...")
            app = ScreenshotAutomaterGUI()
            app.run()
        else:
            print("Exiting...")
            sys.exit(0)


if __name__ == "__main__":
    main()