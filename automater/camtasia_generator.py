"""
Camtasia Project Generator - Create Camtasia projects from image folders
"""

import os
import sys
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from xml.dom import minidom

try:
    from PIL import Image
except ImportError:
    print("PIL not available - image dimensions will use defaults")
    Image = None


def generate_guid():
    """Generate a GUID in Camtasia format."""
    return str(uuid.uuid4()).upper()


def get_image_info(image_path: Path) -> Dict:
    """Get image dimensions and format."""
    if Image:
        try:
            with Image.open(image_path) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format or 'PNG'
                }
        except:
            pass
    # Default to 1920x1080 if we can't read
    return {'width': 1920, 'height': 1080, 'format': 'PNG'}


def get_images_from_directory(directory: str) -> List[Path]:
    """Get all image files from a directory, sorted by name."""
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")
    
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}
    
    image_files = sorted([
        f for f in directory.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ])
    
    return image_files


def create_camtasia_project(
    image_folder: str,
    output_path: str = None,
    image_duration: float = 5.0,
    project_width: int = 1920,
    project_height: int = 1080,
    framerate: float = 30.0
) -> str:
    """
    Create a Camtasia project file (.tscproj) from images in a folder.
    
    Args:
        image_folder: Path to folder containing images
        output_path: Path for output .tscproj file (default: folder name + .tscproj)
        image_duration: Duration for each image in seconds
        project_width: Project canvas width
        project_height: Project canvas height
        framerate: Project framerate
        
    Returns:
        Path to created project file
    """
    image_folder = Path(image_folder)
    images = get_images_from_directory(image_folder)
    
    if not images:
        raise ValueError(f"No images found in {image_folder}")
    
    if output_path is None:
        output_path = str(image_folder / f"{image_folder.name}_project.tscproj")
    
    # Calculate frame duration
    frames_per_image = int(image_duration * framerate)
    
    # Create the XML structure
    root = ET.Element('Project')
    root.set('version', '1')
    root.set('guid', generate_guid())
    
    # Project settings
    settings = ET.SubElement(root, 'ProjectSettings')
    ET.SubElement(settings, 'Width').text = str(project_width)
    ET.SubElement(settings, 'Height').text = str(project_height)
    ET.SubElement(settings, 'FrameRate').text = str(framerate)
    ET.SubElement(settings, 'AudioSampleRate').text = '44100'
    ET.SubElement(settings, 'AudioChannels').text = '2'
    
    # Media bin
    media_bin = ET.SubElement(root, 'MediaBin')
    media_items = []
    
    for i, img_path in enumerate(images):
        img_info = get_image_info(img_path)
        media_id = generate_guid()
        
        media = ET.SubElement(media_bin, 'Media')
        media.set('id', media_id)
        media.set('type', 'image')
        
        ET.SubElement(media, 'FilePath').text = str(img_path.absolute())
        ET.SubElement(media, 'FileName').text = img_path.name
        ET.SubElement(media, 'Width').text = str(img_info['width'])
        ET.SubElement(media, 'Height').text = str(img_info['height'])
        ET.SubElement(media, 'Duration').text = str(frames_per_image)
        
        media_items.append({
            'id': media_id,
            'path': str(img_path.absolute()),
            'name': img_path.name,
            'width': img_info['width'],
            'height': img_info['height'],
            'duration': frames_per_image
        })
    
    # Timeline
    timeline = ET.SubElement(root, 'Timeline')
    
    # Video track
    video_track = ET.SubElement(timeline, 'Track')
    video_track.set('type', 'video')
    video_track.set('name', 'Track 1')
    
    current_frame = 0
    for i, media_item in enumerate(media_items):
        clip = ET.SubElement(video_track, 'Clip')
        clip.set('id', generate_guid())
        clip.set('mediaId', media_item['id'])
        
        ET.SubElement(clip, 'Start').text = str(current_frame)
        ET.SubElement(clip, 'Duration').text = str(media_item['duration'])
        ET.SubElement(clip, 'MediaStart').text = '0'
        ET.SubElement(clip, 'FileName').text = media_item['name']
        ET.SubElement(clip, 'FilePath').text = media_item['path']
        
        current_frame += media_item['duration']
    
    # Audio track (empty)
    audio_track = ET.SubElement(timeline, 'Track')
    audio_track.set('type', 'audio')
    audio_track.set('name', 'Track 2')
    
    # Total duration
    ET.SubElement(timeline, 'TotalDuration').text = str(current_frame)
    
    # Pretty print the XML
    xml_str = ET.tostring(root, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ')
    
    # Remove extra blank lines
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    pretty_xml = '\n'.join(lines)
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)
    
    print(f"Created Camtasia project: {output_path}")
    print(f"  - {len(images)} images imported")
    print(f"  - Duration per image: {image_duration}s")
    print(f"  - Total duration: {len(images) * image_duration}s")
    
    return output_path


def create_camrec_package(
    image_folder: str,
    output_path: str = None,
    image_duration: float = 5.0,
    project_width: int = 1920,
    project_height: int = 1080,
    framerate: float = 30.0
) -> str:
    """
    Create a Camtasia recording package (.camrec) that can be imported.
    This is an alternative format that Camtasia can import more easily.
    
    Args:
        image_folder: Path to folder containing images
        output_path: Path for output .camrec file
        image_duration: Duration for each image in seconds
        project_width: Project canvas width
        project_height: Project canvas height
        framerate: Project framerate
        
    Returns:
        Path to created file
    """
    image_folder = Path(image_folder)
    images = get_images_from_directory(image_folder)
    
    if not images:
        raise ValueError(f"No images found in {image_folder}")
    
    if output_path is None:
        output_path = str(image_folder / f"{image_folder.name}_import.camrec")
    
    # Create metadata JSON
    metadata = {
        "version": "1.0",
        "type": "image_sequence", 
        "created": datetime.now().isoformat(),
        "settings": {
            "width": project_width,
            "height": project_height,
            "framerate": framerate,
            "image_duration": image_duration
        },
        "images": [
            {
                "filename": img.name,
                "path": str(img.absolute()),
                "order": i
            }
            for i, img in enumerate(images)
        ]
    }
    
    # Save as JSON (not a true .camrec but useful reference)
    json_path = output_path.replace('.camrec', '_metadata.json')
    with open(json_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Created metadata file: {json_path}")
    
    return json_path


def generate_camtasia_import_script(
    image_folder: str,
    output_path: str = None
) -> str:
    """
    Generate a text file with instructions and file paths for manual Camtasia import.
    Also creates a batch file to copy paths to clipboard.
    
    Args:
        image_folder: Path to folder containing images
        output_path: Path for output files
        
    Returns:
        Path to created instruction file
    """
    image_folder = Path(image_folder)
    images = get_images_from_directory(image_folder)
    
    if not images:
        raise ValueError(f"No images found in {image_folder}")
    
    if output_path is None:
        output_path = str(image_folder / "camtasia_import.txt")
    
    # Create instruction file
    with open(output_path, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("CAMTASIA IMPORT INSTRUCTIONS\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Folder: {image_folder.absolute()}\n")
        f.write(f"Images found: {len(images)}\n\n")
        
        f.write("METHOD 1 - Drag and Drop:\n")
        f.write("-" * 40 + "\n")
        f.write("1. Open Camtasia\n")
        f.write("2. Open this folder in File Explorer\n")
        f.write("3. Select all images (Ctrl+A)\n")
        f.write("4. Drag them to the Camtasia Media Bin\n")
        f.write("5. Then drag from Media Bin to Timeline\n\n")
        
        f.write("METHOD 2 - File Import:\n")
        f.write("-" * 40 + "\n")
        f.write("1. In Camtasia: File > Import > Media\n")
        f.write("2. Navigate to the folder listed above\n")
        f.write("3. Select all images and click Open\n\n")
        
        f.write("METHOD 3 - Copy Paths:\n")
        f.write("-" * 40 + "\n")
        f.write("Run 'copy_paths_to_clipboard.bat' to copy all paths\n\n")
        
        f.write("IMAGE FILES:\n")
        f.write("-" * 40 + "\n")
        for img in images:
            f.write(f"{img.absolute()}\n")
    
    # Create batch file to copy paths to clipboard
    batch_path = image_folder / "copy_paths_to_clipboard.bat"
    with open(batch_path, 'w') as f:
        f.write("@echo off\n")
        f.write("(\n")
        for img in images:
            f.write(f'echo "{img.absolute()}"\n')
        f.write(") | clip\n")
        f.write(f"echo Copied {len(images)} file paths to clipboard!\n")
        f.write("pause\n")
    
    # Create PowerShell script for more reliable clipboard
    ps_path = image_folder / "copy_paths_to_clipboard.ps1"
    with open(ps_path, 'w') as f:
        f.write("# Copy image paths to clipboard\n")
        f.write("$paths = @(\n")
        for img in images:
            f.write(f'    "{img.absolute()}"\n')
        f.write(")\n")
        f.write("$paths -join \"`n\" | Set-Clipboard\n")
        f.write(f'Write-Host "Copied {len(images)} file paths to clipboard!"')
        f.write("\nRead-Host 'Press Enter to exit'\n")
    
    print(f"Created Camtasia import helper files:")
    print(f"  - Instructions: {output_path}")
    print(f"  - Batch file: {batch_path}")
    print(f"  - PowerShell: {ps_path}")
    
    return output_path


def interactive_camtasia_export():
    """Interactive mode for creating Camtasia import files."""
    print("\n" + "=" * 60)
    print("CAMTASIA PROJECT GENERATOR")
    print("=" * 60)
    
    # Get folder
    folder = input("\nEnter path to image folder: ").strip()
    if not folder:
        print("No folder specified.")
        return
    
    folder = Path(folder)
    if not folder.exists():
        print(f"Folder not found: {folder}")
        return
    
    try:
        images = get_images_from_directory(folder)
        print(f"\nFound {len(images)} images")
    except Exception as e:
        print(f"Error: {e}")
        return
    
    print("\nExport options:")
    print("  1. Create Camtasia project file (.tscproj)")
    print("  2. Generate import helper files (instructions + scripts)")
    print("  3. Both")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice in ['1', '3']:
        duration = input("Duration per image in seconds (default: 5): ").strip()
        duration = float(duration) if duration else 5.0
        
        try:
            create_camtasia_project(folder, image_duration=duration)
        except Exception as e:
            print(f"Error creating project: {e}")
    
    if choice in ['2', '3']:
        try:
            generate_camtasia_import_script(folder)
        except Exception as e:
            print(f"Error creating import scripts: {e}")
    
    print("\nDone!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Camtasia Project Generator")
    parser.add_argument("folder", nargs='?', help="Path to image folder")
    parser.add_argument("-o", "--output", help="Output path for project file")
    parser.add_argument("-d", "--duration", type=float, default=5.0, 
                        help="Duration per image in seconds (default: 5)")
    parser.add_argument("--width", type=int, default=1920, help="Project width")
    parser.add_argument("--height", type=int, default=1080, help="Project height")
    parser.add_argument("--scripts-only", action="store_true",
                        help="Only generate import helper scripts (no project file)")
    
    args = parser.parse_args()
    
    if args.folder:
        if args.scripts_only:
            generate_camtasia_import_script(args.folder, args.output)
        else:
            create_camtasia_project(
                args.folder,
                args.output,
                args.duration,
                args.width,
                args.height
            )
            generate_camtasia_import_script(args.folder)
    else:
        interactive_camtasia_export()
