# Screenshot Automater

A Python application that captures screenshots every time you click and can replay recorded workflows.

## Features

- **Click-to-Capture**: Automatically captures a screenshot every time you click
- **Custom Naming**: Use flexible naming patterns for your screenshots
- **Workflow Recording**: Records click positions and timing for replay
- **Workflow Replay**: Re-execute your recorded clicks and capture new screenshots
- **Video Generation**: Create MP4 videos from images with narration and transitions
- **Interactive & CLI modes**: Use from command line or interactive prompts

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Graphical User Interface (GUI)

For the easiest experience, launch the GUI application:

```bash
python screenshot_automater_gui.py
```

Or use the batch file:

```bash
run_screenshot_gui.bat
```

**GUI Features:**
- **Record Tab**: Configure output directory, naming patterns, and image format, then click to capture screenshots
- **Replay Tab**: Load workflow files and replay recorded click sequences with customizable delays
- **Video Tab**: Quick access to video generation and the visual narration editor
- **Monitor Display**: View connected monitors and their configurations
- **Real-time Status**: See click counts and capture status while recording

### Interactive Mode (CLI)

Simply run the script without arguments:

```bash
python screenshot_automater.py
```

You'll be prompted to choose between Record and Replay modes.

### Command Line Mode

#### Recording Screenshots

```bash
python screenshot_automater.py record -o my_screenshots -n "step_{count}" -f png
```

Options:
- `-o, --output`: Output directory (default: `screenshots`)
- `-n, --naming`: Naming pattern (default: `{timestamp}_{count}`)
- `-f, --format`: Image format: `png`, `jpg`, or `bmp` (default: `png`)

#### Replaying a Workflow

```bash
python screenshot_automater.py replay -w my_screenshots/workflow.json -o new_screenshots
```

Options:
- `-w, --workflow`: Path to the workflow JSON file
- `-o, --output`: Output directory for new screenshots
- `-d, --delay`: Delay multiplier (default: 1.0)
- `-m, --min-delay`: Minimum delay between clicks in seconds (default: 0.5)
- `--no-capture`: Don't capture screenshots during replay (just replay clicks)

#### Creating Videos from Images

Create an MP4 video from a directory of images with narration and transitions:

```bash
python screenshot_automater.py video -i my_screenshots
```

Or create a video directly from a recorded workflow:

```bash
python screenshot_automater.py video -i my_screenshots/workflow.json
```

Options:
- `-i, --input`: Path to image directory or workflow JSON file
- `-o, --output`: Output video file path
- `-p, --project`: Load a saved video project file

### Video Generation Features

- **Multiple image formats**: PNG, JPG, JPEG, BMP, GIF, TIFF, WEBP
- **Custom resolutions**: 1080p, 720p, 4K, or custom
- **Text-to-Speech narration**: Enter narration scripts for each image
- **Multiple voices**: Choose from available system TTS voices
- **Transitions**: None, Fade, Crossfade, Slide (left/right/up/down)
- **Per-image settings**: Custom duration and transitions per image
- **Project saving**: Save configurations for later editing

### Video Interactive Mode

When running in interactive mode, you'll be prompted for:

1. **Image directory**: Folder containing your images
2. **Resolution**: Output video resolution (1080p, 720p, 4K, or custom)
3. **Default duration**: How long each image displays (auto-adjusts for narration)
4. **Transition type**: Effect between images
5. **Narration**: Text-to-speech script for each image (optional)
6. **Voice selection**: Choose from available TTS voices
7. **Output file**: Where to save the final MP4

### Visual Narration Editor (GUI)

For a more visual experience, use the GUI editor:

```bash
python screenshot_automater.py editor
```

Or launch directly:

```bash
python video_editor_gui.py
```

Or use the batch file:

```bash
run_video_editor.bat
```

Options:
- `-i, --input`: Path to image directory to load on startup
- `-p, --project`: Load a saved project file on startup

**GUI Features:**
- See each image as a thumbnail alongside its narration text box
- Edit narration text for each image in a scrollable interface
- Set custom duration and transitions per image
- Preview narration using text-to-speech
- Save and load projects for later editing
- Generate video directly from the GUI

## Naming Pattern Variables

Use these variables in your naming pattern:

| Variable | Description | Example |
|----------|-------------|---------|
| `{timestamp}` | Full timestamp | `20260218_143025` |
| `{count}` | Sequential counter (zero-padded) | `0001`, `0002` |
| `{x}` | X coordinate of click | `512` |
| `{y}` | Y coordinate of click | `384` |
| `{date}` | Date only | `2026-02-18` |
| `{time}` | Time only | `14-30-25` |

### Naming Examples

```bash
# Default: timestamp_0001.png
python screenshot_automater.py record -n "{timestamp}_{count}"

# Just numbered: screenshot_0001.png
python screenshot_automater.py record -n "screenshot_{count}"

# With coordinates: click_512_384_0001.png
python screenshot_automater.py record -n "click_{x}_{y}_{count}"

# Date-based: 2026-02-18_step_0001.png
python screenshot_automater.py record -n "{date}_step_{count}"
```

## Workflow Files

When you record a session, a `workflow.json` file is saved in the output directory. This file contains:

- Session information (start time, settings)
- Each click with position, timing, and screenshot path

### Example workflow.json:

```json
{
  "session_info": {
    "start_time": "2026-02-18T14:30:25",
    "total_clicks": 5,
    "output_dir": "C:/screenshots",
    "naming_pattern": "{timestamp}_{count}",
    "image_format": "png"
  },
  "clicks": [
    {
      "x": 512,
      "y": 384,
      "time": 0.0,
      "timestamp": "2026-02-18T14:30:26",
      "screenshot": "screenshots/20260218_143026_0001.png"
    }
  ]
}
```

## Controls

### During Recording
- **Left-click anywhere**: Captures a screenshot
- **Ctrl+C in terminal**: Stops recording and saves workflow

### During Replay
- **Move mouse to corner**: Aborts replay (PyAutoGUI failsafe)

## Tips

1. **Consistent naming**: Use `{count}` to ensure unique filenames
2. **Workflow organization**: Create separate output directories for different workflows
3. **Replay timing**: Increase `--min-delay` for slower systems or complex UIs
4. **No capture replay**: Use `--no-capture` to just replay clicks without screenshots

## Requirements

- Python 3.7+
- Windows/macOS/Linux
- Display access for screenshots
- FFmpeg (bundled with moviepy for video generation)

## Troubleshooting

### "Missing required package" error
Run: `pip install -r requirements.txt`

### Screenshots are blank or incorrect
- Increase the delay in the code (currently 0.1s)
- Some applications may have screenshot protection

### Replay clicks are in wrong positions
- Ensure screen resolution is the same as during recording
- Window positions should match the original recording

## License

MIT License

## User Guide (PSL)

### Capture

1. Open the screenshot.bat
2. Move the window to a secondary monitor
3. in the primary monitor, open up the browser to the page where you want to start the captures
4. exapnd the browser window to full screen mode (f11)
5. start the capture (option 1)
6. Select the output directory
7. Select the naming convention
8. Select an image format
9. Then click anywhere to start the captures
10. The tool captures the primary monitor

### replay