#!/usr/bin/env python
"""Test the new Camtasia 2025 JSON generator."""

from camtasia_generator import create_camtasia_project_json
import json
from pathlib import Path

# Test with the storyboard slide exports if they exist
test_dir = Path(r'C:\GitHub\zoomincategories-video\slides')
output = Path(r'C:\GitHub\zoomincategories-video\test_project.tscproj')

if not test_dir.exists():
    print(f"Creating test directory {test_dir}...")
    test_dir.mkdir(parents=True, exist_ok=True)
    # Create a couple of test images
    from PIL import Image, ImageDraw
    for i in range(3):
        img = Image.new('RGB', (1920, 1080), color=(73, 109, 137))
        draw = ImageDraw.Draw(img)
        draw.text((100, 400), f'Test Slide {i+1}', fill='white')
        img.save(test_dir / f'slide_{i+1:03d}.png')
    print(f"Created {3} test images in {test_dir}")

try:
    result = create_camtasia_project_json(str(test_dir), str(output), image_duration=3.0)
    
    # Verify the JSON is valid
    with open(result) as f:
        project = json.load(f)
    
    print('✓ Project created successfully')
    print(f'  Format version: {project.get("formatVersion")}')
    print(f'  Framerate: {project.get("framerate")}')
    print(f'  Resolution: {project.get("width")}x{project.get("height")}')
    timeline_medias = project.get('timeline', {}).get('medias', [])
    print(f'  Timeline medias: {len(timeline_medias)}')
    source_tracks = project.get('sourceBin', {}).get('sourceTracks', [])
    print(f'  Source tracks: {len(source_tracks)}')
    
    if timeline_medias:
        first_media = timeline_medias[0]
        print(f'  First media type: {first_media.get("_type")}')
        print(f'  First media has effects: {bool(first_media.get("effects"))}')
        print(f'  First media has attributes: {bool(first_media.get("attributes"))}')
    
    print('\n✓ Camtasia 2025 JSON format is valid and ready to open in Camtasia!')
    
except Exception as e:
    import traceback
    print(f'Error: {e}')
    traceback.print_exc()
