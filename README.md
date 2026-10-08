# File Converter

A simple desktop app that converts everyday files, 100% locally on your PC.
No uploads, no cloud, no accounts.

## What it converts

| Type | From | To |
|------|------|----|
| Images | PNG, JPG, WEBP, BMP, GIF, TIFF, ICO | any image format |
| Audio | MP3, WAV, OGG, FLAC, M4A, OPUS | any audio format |
| Video | MP4, MKV, AVI, MOV, WEBM | any video format, or extract audio (MP3/WAV/M4A) |
| Documents | PDF | TXT, PNG, JPG (per page) |
| | DOCX | TXT, PDF |
| | TXT / MD | PDF, DOCX, HTML |
| | CSV | XLSX |
| | XLSX | CSV |

## Install (Windows)

1. Download `FileConverter.exe` from the latest release (or the Actions build artifact).
2. Run it. That's it — no installer.

ffmpeg is bundled automatically via imageio-ffmpeg, so MP4→MP3 and friends work out of the box.

## Run from source

```bash
pip install -r requirements.txt
python app.py
```

## Build the exe yourself

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed --name FileConverter app.py
```
