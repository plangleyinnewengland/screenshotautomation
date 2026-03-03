# Copy image paths to clipboard
$paths = @(
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0001.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0002.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0003.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0004.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0005.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0006.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0007.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0008.png"
    "C:\Python\automater\screenshots\cloudwatcher\cloud_0009.png"
)
$paths -join "`n" | Set-Clipboard
Write-Host "Copied 9 file paths to clipboard!"
Read-Host 'Press Enter to exit'
