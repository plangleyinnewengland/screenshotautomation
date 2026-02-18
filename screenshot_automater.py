"""
Screenshot Automater - Capture screenshots on click and replay workflows
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

try:
    from pynput import mouse
    from pynput.mouse import Button, Controller as MouseController
    import pyautogui
    from PIL import Image
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
    
    def _on_click(self, x: int, y: int, button: Button, pressed: bool):
        """Handle mouse click events."""
        # Only capture on button press (not release), and only left clicks
        if not pressed or button != Button.left:
            return
            
        if self.is_paused:
            return
            
        print(f"Click detected at ({x}, {y})")
        
        # Record the click position and time
        click_data = {
            "x": x,
            "y": y,
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
                
            x = click["x"]
            y = click["y"]
            click_time = click.get("time", 0)
            
            # Calculate delay
            if i > 0:
                delay = (click_time - previous_time) * delay_multiplier
                delay = max(delay, min_delay)
                print(f"Waiting {delay:.2f}s before next click...")
                time.sleep(delay)
            
            previous_time = click_time
            
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
    else:
        # Interactive mode
        print("\n" + "="*50)
        print("SCREENSHOT AUTOMATER - Interactive Mode")
        print("="*50)
        
        print("\nSelect mode:")
        print("  1. Record - Capture screenshots on click")
        print("  2. Replay - Replay a recorded workflow")
        print("  3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
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
        else:
            print("Exiting...")
            sys.exit(0)


if __name__ == "__main__":
    main()
