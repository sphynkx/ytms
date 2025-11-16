import os
import math
import shutil
import asyncio
from typing import List
from PIL import Image

def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)

async def run_ffmpeg_extract_frames(
    src: str,
    out_dir: str,
    interval_sec: float,
    tile_w: int,
    tile_h: int,
):
    ensure_dir(out_dir)
    vf = (
        f"fps=1/{interval_sec},"
        f"scale={tile_w}:-1:force_original_aspect_ratio=decrease:eval=frame,"
        f"pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    out_pattern = os.path.join(out_dir, "frame_%05d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-loglevel", "error",
        "-vf", vf,
        out_pattern,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode('utf-8', 'ignore')}")

async def probe_duration_sec(src: str) -> float | None:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        src,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0:
            try:
                return float(stdout.decode().strip())
            except Exception:
                return None
    except FileNotFoundError:
        return None
    return None

def list_frames(frames_dir: str) -> List[str]:
    files = [f for f in os.listdir(frames_dir) if f.lower().startswith("frame_") and f.lower().endswith(".jpg")]
    files.sort()
    return [os.path.join(frames_dir, f) for f in files]

def pack_sprites(
    frames: List[str],
    sprites_dir: str,
    cols: int,
    rows: int,
    tile_w: int,
    tile_h: int,
    quality: int = 85,
) -> List[str]:
    ensure_dir(sprites_dir)
    per_sprite = cols * rows
    sprite_paths: List[str] = []
    for sidx in range(math.ceil(len(frames) / per_sprite)):
        chunk = frames[sidx*per_sprite:(sidx+1)*per_sprite]
        if not chunk:
            break
        sprite = Image.new("RGB", (cols*tile_w, rows*tile_h), (0,0,0))
        for i, fp in enumerate(chunk):
            try:
                img = Image.open(fp).convert("RGB")
            except Exception:
                continue
            x = (i % cols) * tile_w
            y = (i // cols) * tile_h
            sprite.paste(img, (x, y))
        out = os.path.join(sprites_dir, f"sprite_{sidx+1:04d}.jpg")
        sprite.save(out, quality=quality, optimize=True)
        sprite_paths.append(out)
    return sprite_paths

def sec_fmt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    ss = s - h*3600 - m*60
    return f"{h:02d}:{m:02d}:{ss:06.3f}"

def write_vtt(
    vtt_path: str,
    sprites_web_base: str,
    total_frames: int,
    interval_sec: float,
    cols: int,
    rows: int,
    tile_w: int,
    tile_h: int,
):
    per_sprite = cols * rows
    lines = ["WEBVTT", ""]
    for i in range(total_frames):
        start = i * interval_sec
        end = (i + 1) * interval_sec
        sidx = i // per_sprite
        idx = i % per_sprite
        x = (idx % cols) * tile_w
        y = (idx // cols) * tile_h
        sprite_url = f"{sprites_web_base}/sprite_{sidx+1:04d}.jpg"
        lines.append(f"{sec_fmt(start)} --> {sec_fmt(end)}")
        lines.append(f"{sprite_url}#xywh={x},{y},{tile_w},{tile_h}")
        lines.append("")
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))