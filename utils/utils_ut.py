import os
import math
import shutil
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from PIL import Image
import httpx

from config import settings


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)



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
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            try:
                return float(stdout.decode().strip())
            except Exception:
                return None
        else:
            print("[FFPROBE DURATION ERROR]", stderr.decode("utf-8", "ignore")[:300])
    except FileNotFoundError:
        print("[FFPROBE MISSING] ffprobe not found")
        return None
    return None



async def probe_video_dims(src: str) -> Tuple[Optional[int], Optional[int]]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        src,
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            line = stdout.decode().strip()
            if "x" in line:
                try:
                    w, h = line.split("x", 1)
                    return int(w), int(h)
                except Exception:
                    return None, None
        else:
            print("[FFPROBE DIMS ERROR]", stderr.decode("utf-8", "ignore")[:300])
    except FileNotFoundError:
        print("[FFPROBE DIMS MISSING] ffprobe not found")
    return None, None



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
        sprite = Image.new("RGB", (cols*tile_w, rows*tile_h), (0, 0, 0))
        for i, fp in enumerate(chunk):
            try:
                img = Image.open(fp).convert("RGB")
            except Exception as e:
                print("[SPRITE FRAME ERROR]", fp, e)
                continue
            x = (i % cols) * tile_w
            y = (i // cols) * tile_h
            sprite.paste(img, (x, y))
        out = os.path.join(sprites_dir, f"sprite_{sidx+1:04d}.jpg")
        sprite.save(out, quality=quality, optimize=True)
        sprite_paths.append(out)
    print(f"[SPRITES BUILT] count={len(sprite_paths)}")
    return sprite_paths



def sec_fmt(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    ss = s - h*3600 - m*60
    return f"{h:02d}:{m:02d}:{ss:06.3f}"



def write_vtt(
    vtt_path: str,
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
        sprite_url = f"sprites/sprite_{sidx+1:04d}.jpg"
        lines.append(f"{sec_fmt(start)} --> {sec_fmt(end)}")
        lines.append(f"{sprite_url}#xywh={x},{y},{tile_w},{tile_h}")
        lines.append("")
    ensure_dir(os.path.dirname(vtt_path))
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[VTT WRITTEN] path={vtt_path} frames={total_frames}")



async def download_src(url: str, dest: str) -> None:
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        ensure_dir(os.path.dirname(dest))
        with open(dest, "wb") as f:
            f.write(r.content)
    print(f"[DOWNLOAD OK] url={url} dest={dest}")



def build_vf_chain(interval_sec: float, tile_w: int, tile_h: int) -> str:
    return f"scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease,pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2:color=black,fps=1/{interval_sec}"



async def run_ffmpeg_extract_frames(
    src: str,
    out_dir: str,
    interval_sec: float,
    tile_w: int,
    tile_h: int,
):
    ensure_dir(out_dir)
    vf = build_vf_chain(interval_sec, tile_w, tile_h)
    out_pattern = os.path.join(out_dir, "frame_%05d.jpg")
    cmd = [
        "ffmpeg", "-y",
        "-i", src,
        "-loglevel", "error",
        "-vf", vf,
        out_pattern,
    ]
    print("[FFMPEG CMD]", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_txt = stderr.decode("utf-8", "ignore")
        print("[FFMPEG STDERR]", err_txt)
        raise RuntimeError(f"ffmpeg failed: {err_txt[:500]}")
    else:
        print("[FFMPEG OK] frames extracted (check directory)")



async def generate_thumbnails_pipeline(
    video_id: str,
    out_base_path: str,
    src_path: Optional[str],
    src_url: Optional[str],
    interval_sec: Optional[float],
    tile_w: Optional[int],
    tile_h: Optional[int],
    cols: Optional[int],
    rows: Optional[int],
) -> Dict[str, Any]:
    abs_base = out_base_path.rstrip("/")

    sprites_dir = os.path.join(abs_base, "sprites")
    frames_dir = os.path.join(abs_base, "sprites_frames_tmp")
    ensure_dir(sprites_dir)
    ensure_dir(frames_dir)

    source = src_path
    if not source and src_url:
        source = os.path.join(sprites_dir, "download_source.webm")
        await download_src(src_url, source)

    if not source or not os.path.exists(source):
        raise RuntimeError(f"source_not_found src={source}")

    size_bytes = os.path.getsize(source)
    w0, h0 = await probe_video_dims(source)
    print(f"[SOURCE OK] path={source} size={size_bytes} bytes dims={w0}x{h0}")

    if interval_sec is None:
        dur = await probe_duration_sec(source)
        if dur is None:
            interval_sec = settings.PREVIEW_INTERVAL_MEDIUM
        elif dur <= settings.PREVIEW_SHORT_MAX_SEC:
            interval_sec = settings.PREVIEW_INTERVAL_SHORT
        elif dur <= settings.PREVIEW_MEDIUM_MAX_SEC:
            interval_sec = settings.PREVIEW_INTERVAL_MEDIUM
        else:
            interval_sec = settings.PREVIEW_INTERVAL_LONG
        print(f"[ADAPTIVE INTERVAL] duration={dur} chosen={interval_sec}")
    else:
        dur = await probe_duration_sec(source)

    tw = tile_w or settings.DEFAULT_TILE_W
    th = tile_h or settings.DEFAULT_TILE_H
    c = cols or settings.DEFAULT_COLS
    r = rows or settings.DEFAULT_ROWS

    if dur and interval_sec:
        rough_frames = int(dur / interval_sec)
        if rough_frames > settings.MAX_FRAMES:
            interval_sec = max(settings.MIN_INTERVAL_SEC, dur / settings.MAX_FRAMES)
            print(f"[FRAME LIMIT] rough_frames={rough_frames} > {settings.MAX_FRAMES} => interval_sec={interval_sec:.4f}")

    print(f"[PARAMS] interval={interval_sec} tw={tw} th={th} cols={c} rows={r}")

    await run_ffmpeg_extract_frames(
        src=source,
        out_dir=frames_dir,
        interval_sec=interval_sec,
        tile_w=tw,
        tile_h=th,
    )

    frames = list_frames(frames_dir)
    print(f"[FRAMES FOUND] count={len(frames)} dir={frames_dir}")
    if not frames:
        raise RuntimeError("no_frames_extracted")

    sprites = pack_sprites(
        frames=frames,
        sprites_dir=sprites_dir,
        cols=c,
        rows=r,
        tile_w=tw,
        tile_h=th,
    )

    vtt_rel = "sprites.vtt"
    vtt_abs = os.path.join(abs_base, vtt_rel)
    write_vtt(
        vtt_path=vtt_abs,
        total_frames=len(frames),
        interval_sec=interval_sec,
        cols=c,
        rows=r,
        tile_w=tw,
        tile_h=th,
    )

    deleted = 0
    for f in frames:
        try:
            os.remove(f)
            deleted += 1
        except Exception as e:
            print("[FRAMES CLEANUP ERROR]", f, e)
    try:
        os.rmdir(frames_dir)
    except Exception:
        pass
    print(f"[FRAMES CLEANUP] deleted={deleted} dir_removed={not os.path.exists(frames_dir)}")

    result = {
        "vtt": {"path": vtt_rel},
        "sprites": [{"path": f"sprites/{os.path.basename(p)}"} for p in sprites],
        "meta": {
            "frames": len(frames),
            "interval": interval_sec,
            "tile_w": tw,
            "tile_h": th,
            "cols": c,
            "rows": r,
            "src_dims": f"{w0}x{h0}",
            "frame_limit": settings.MAX_FRAMES,
        },
    }
    return result