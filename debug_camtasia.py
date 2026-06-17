#!/usr/bin/env python
"""Debug Camtasia project structure."""

import json

with open(r'C:\GitHub\zoomincategories-video\test_project.tscproj') as f:
    proj = json.load(f)

print("=== PROJECT STRUCTURE ===")
print(f"formatVersion: {proj.get('formatVersion')}")
print(f"framerate: {proj.get('framerate')}")
print(f"width x height: {proj.get('width')} x {proj.get('height')}")
print()

print("=== FIRST SOURCE TRACK ===")
st = proj['sourceBin']['sourceTracks'][0]
print(f"type: {st['type']}")
print(f"editRate: {st['editRate']}")
print(f"range: {st['range']}")
print()

print("=== FIRST TIMELINE MEDIA ===")
m = proj['timeline']['medias'][0]
print(f"_type: {m['_type']}")
print(f"src: {m['src']}")
print(f"start: {m['start']}, duration: {m['duration']}")
print(f"attributes: {m['attributes']}")
print(f"metadata: {m['metadata']}")
print()

print("=== TIMELINE ===")
print(f"timeline duration: {proj['timeline']['duration']}")
print(f"timeline playheadPosition: {proj['timeline']['playheadPosition']}")
print()

# Check JSON validity
print("✓ JSON is valid")
print(f"✓ {len(proj['sourceBin']['sourceTracks'])} source tracks")
print(f"✓ {len(proj['timeline']['medias'])} timeline medias")

# Pretty print the entire file to check structure
print("\n=== CHECKING FOR ISSUES ===")

# Check if all required fields are present
required_top = ['formatVersion', 'framerate', 'width', 'height', 'name', 'guid', 'creationDate', 'modificationDate', 'sourceBin', 'timeline']
missing = [k for k in required_top if k not in proj]
if missing:
    print(f"Missing top-level fields: {missing}")
else:
    print("✓ All required top-level fields present")

# Check source tracks
if proj['sourceBin']['sourceTracks']:
    st = proj['sourceBin']['sourceTracks'][0]
    required_st = ['range', 'type', 'editRate', 'trackRect', 'sampleRate', 'bitDepth', 'numChannels', 'integratedLUFS', 'peakLevel', 'tag', 'metaData', 'parameters']
    missing_st = [k for k in required_st if k not in st]
    if missing_st:
        print(f"Missing sourceTrack fields: {missing_st}")
    else:
        print("✓ All required sourceTrack fields present")

# Check media objects
if proj['timeline']['medias']:
    m = proj['timeline']['medias'][0]
    required_m = ['id', '_type', 'src', 'trackNumber', 'attributes', 'parameters', 'effects', 'start', 'duration', 'mediaStart', 'mediaDuration', 'scalar', 'metadata', 'animationTracks']
    missing_m = [k for k in required_m if k not in m]
    if missing_m:
        print(f"Missing media fields: {missing_m}")
    else:
        print("✓ All required media fields present")
