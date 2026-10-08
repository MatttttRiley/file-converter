#!/usr/bin/env python3
"""File Converter - core conversion engine.

Covers the everyday stuff, all locally:
  Images:    PNG, JPG/JPEG, WEBP, BMP, GIF, TIFF, ICO
  Audio:     MP3, WAV, OGG, FLAC, M4A, OPUS
  Video:     MP4, MKV, AVI, MOV, WEBM  -> video formats or audio extraction
  Documents: PDF -> TXT / PNG / JPG, DOCX -> TXT, TXT/MD -> PDF, CSV <-> XLSX
"""

import os
import subprocess

# ----------------------------------------------------------------------------
# Format registry
# ----------------------------------------------------------------------------

IMAGE_FORMATS = ["png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff", "ico"]
AUDIO_FORMATS = ["mp3", "wav", "ogg", "flac", "m4a", "opus"]
VIDEO_FORMATS = ["mp4", "mkv", "avi", "mov", "webm"]
DOC_FORMATS = ["pdf", "docx", "txt", "md", "csv", "xlsx"]

ALL_KNOWN = set(IMAGE_FORMATS + AUDIO_FORMATS + VIDEO_FORMATS + DOC_FORMATS)


def category_of(ext):
    ext = ext.lower().lstrip(".")
    if ext in IMAGE_FORMATS:
        return "image"
    if ext in AUDIO_FORMATS:
        return "audio"
    if ext in VIDEO_FORMATS:
        return "video"
    if ext in DOC_FORMATS:
        return "document"
    return None


def valid_targets(src_ext):
    """Return list of sensible output formats for a source extension."""
    cat = category_of(src_ext)
    src = src_ext.lower().lstrip(".")
    if cat == "image":
        return [f for f in IMAGE_FORMATS if f != src]
    if cat == "audio":
        return [f for f in AUDIO_FORMATS if f != src]
    if cat == "video":
        # video -> video, or extract audio
        return [f for f in VIDEO_FORMATS if f != src] + ["mp3", "wav", "m4a"]
    if cat == "document":
        mapping = {
            "pdf": ["txt", "png", "jpg"],
            "docx": ["txt", "pdf"],
            "txt": ["pdf", "md", "docx"],
            "md": ["pdf", "txt", "html"],
            "csv": ["xlsx", "txt"],
            "xlsx": ["csv"],
        }
        return mapping.get(src, [])
    return []


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _ffmpeg_bin():
    """Locate an ffmpeg binary (imageio-ffmpeg bundles one)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _out_path(src, new_ext, out_dir=None):
    base = os.path.splitext(os.path.basename(src))[0]
    # multi-page PDFs produce several files; caller handles suffixes
    name = f"{base}.{new_ext}"
    return os.path.join(out_dir or os.path.dirname(src) or ".", name)


# ----------------------------------------------------------------------------
# Converters
# ----------------------------------------------------------------------------

def convert_image(src, dst_ext, out_dir=None):
    from PIL import Image
    dst = _out_path(src, dst_ext, out_dir)
    img = Image.open(src)
    ext = dst_ext.lower()
    save_kwargs = {}
    if ext in ("jpg", "jpeg"):
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        save_kwargs["quality"] = 92
    elif ext == "webp":
        save_kwargs["quality"] = 90
    elif ext == "ico":
        img = img.resize((256, 256))
    img.save(dst, **save_kwargs)
    return dst


def convert_audio(src, dst_ext, out_dir=None, progress_cb=None):
    ff = _ffmpeg_bin()
    dst = _out_path(src, dst_ext, out_dir)
    cmd = [ff, "-y", "-i", src]
    if dst_ext == "mp3":
        cmd += ["-codec:a", "libmp3lame", "-b:a", "192k"]
    elif dst_ext == "m4a":
        cmd += ["-codec:a", "aac", "-b:a", "192k"]
    elif dst_ext == "ogg":
        cmd += ["-codec:a", "libvorbis", "-q:a", "5"]
    elif dst_ext == "opus":
        cmd += ["-codec:a", "libopus", "-b:a", "128k"]
    elif dst_ext == "flac":
        cmd += ["-codec:a", "flac"]
    elif dst_ext == "wav":
        cmd += ["-codec:a", "pcm_s16le"]
    cmd += [dst]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


def convert_video(src, dst_ext, out_dir=None, progress_cb=None):
    """Video->video re-encode, or video->audio extraction."""
    ff = _ffmpeg_bin()
    dst = _out_path(src, dst_ext, out_dir)
    cmd = [ff, "-y", "-i", src]
    if dst_ext in AUDIO_FORMATS or category_of(dst_ext) == "audio":
        cmd += ["-vn"]
        return convert_audio(src, dst_ext, out_dir, progress_cb)
    # video output: h264 + aac is the safe universal combo
    cmd += ["-codec:v", "libx264", "-preset", "medium", "-crf", "21",
            "-codec:a", "aac", "-b:a", "160k", dst]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


def convert_document(src, dst_ext, out_dir=None):
    src_ext = os.path.splitext(src)[1].lower().lstrip(".")
    dst_ext = dst_ext.lower()
    out_dir = out_dir or os.path.dirname(src) or "."

    if src_ext == "pdf" and dst_ext == "txt":
        import fitz  # PyMuPDF
        doc = fitz.open(src)
        text = "\n".join(page.get_text() for page in doc)
        dst = _out_path(src, "txt", out_dir)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        return dst

    if src_ext == "pdf" and dst_ext in ("png", "jpg"):
        import fitz
        doc = fitz.open(src)
        outs = []
        base = os.path.splitext(os.path.basename(src))[0]
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            name = f"{base}-p{i+1}.{dst_ext}"
            dst = os.path.join(out_dir, name)
            pix.save(dst)
            outs.append(dst)
        return outs[0] if len(outs) == 1 else outs

    if src_ext == "docx" and dst_ext == "txt":
        import docx
        d = docx.Document(src)
        dst = _out_path(src, "txt", out_dir)
        with open(dst, "w", encoding="utf-8") as f:
            f.write("\n".join(p.text for p in d.paragraphs))
        return dst

    if src_ext == "docx" and dst_ext == "pdf":
        # text-based PDF via fpdf (no Word/LibreOffice needed)
        import docx
        from fpdf import FPDF
        d = docx.Document(src)
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(20, 20, 20)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        for p in d.paragraphs:
            txt = p.text.encode("latin-1", "replace").decode("latin-1") or " "
            pdf.cell(0, 6, txt, new_x="LMARGIN", new_y="NEXT")
        dst = _out_path(src, "pdf", out_dir)
        pdf.output(dst)
        return dst

    if src_ext in ("txt", "md") and dst_ext == "pdf":
        from fpdf import FPDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(20, 20, 20)
        pdf.add_page()
        pdf.set_font("Courier", size=10)
        with open(src, encoding="utf-8", errors="replace") as f:
            for line in f:
                txt = line.rstrip("\n") or " "
                # latin-1 safe: Courier is a core font
                txt = txt.encode("latin-1", "replace").decode("latin-1")
                pdf.cell(0, 5, txt, new_x="LMARGIN", new_y="NEXT")
        dst = _out_path(src, "pdf", out_dir)
        pdf.output(dst)
        return dst

    if src_ext == "txt" and dst_ext == "md":
        dst = _out_path(src, "md", out_dir)
        with open(src, encoding="utf-8", errors="replace") as f:
            content = f.read()
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        return dst

    if src_ext == "txt" and dst_ext == "docx":
        import docx
        d = docx.Document()
        with open(src, encoding="utf-8", errors="replace") as f:
            for line in f:
                d.add_paragraph(line.rstrip("\n"))
        dst = _out_path(src, "docx", out_dir)
        d.save(dst)
        return dst

    if src_ext == "md" and dst_ext in ("txt", "html"):
        with open(src, encoding="utf-8", errors="replace") as f:
            content = f.read()
        if dst_ext == "html":
            import markdown
            content = markdown.markdown(content)
        dst = _out_path(src, dst_ext, out_dir)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(content)
        return dst

    if src_ext == "csv" and dst_ext == "xlsx":
        import csv
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        with open(src, newline="", encoding="utf-8", errors="replace") as f:
            for row in csv.reader(f):
                ws.append(row)
        dst = _out_path(src, "xlsx", out_dir)
        wb.save(dst)
        return dst

    if src_ext == "xlsx" and dst_ext == "csv":
        import csv
        from openpyxl import load_workbook
        wb = load_workbook(src, read_only=True, data_only=True)
        ws = wb.active
        dst = _out_path(src, "csv", out_dir)
        with open(dst, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                w.writerow(["" if v is None else v for v in row])
        return dst

    raise ValueError(f"Conversion {src_ext} -> {dst_ext} is not supported")


def convert(src, dst_ext, out_dir=None, progress_cb=None):
    """Dispatch to the right converter. Returns output path (or list)."""
    cat = category_of(os.path.splitext(src)[1])
    if cat == "image":
        return convert_image(src, dst_ext, out_dir)
    if cat == "audio":
        return convert_audio(src, dst_ext, out_dir, progress_cb)
    if cat == "video":
        return convert_video(src, dst_ext, out_dir, progress_cb)
    if cat == "document":
        return convert_document(src, dst_ext, out_dir)
    raise ValueError(f"Unknown file type: {src}")
