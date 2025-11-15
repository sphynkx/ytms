import os
import json
import httpx
from typing import Dict, Any, List
from app.config import settings
from app.schemas import JobInfo, ThumbnailsJobCreate, SpriteInfo, VTTInfo, ThumbnailsJobResult
from app.utils.utils_ut import (
    ensure_dir,
    run_ffmpeg_extract_frames,
    list_frames,
    pack_sprites,
    write_vtt,
)

async def process_thumbnails_job(manager, job_id: str, payload: Dict[str, Any]):
    await manager.update_job(job_id, status="running", error=None, result=None)
    req = ThumbnailsJobCreate(**payload)

    # Resolve params
    tile_w = req.tile_w or settings.DEFAULT_TILE_W
    tile_h = req.tile_h or settings.DEFAULT_TILE_H
    cols = req.cols or settings.DEFAULT_COLS
    rows = req.rows or settings.DEFAULT_ROWS

    # Interval (or adaptively)
    interval = req.interval_sec
    if not interval:
        interval = settings.PREVIEW_INTERVAL_MEDIUM

    # IO paths
    out_base = req.out_base_path.rstrip("/")

    sprites_dir = os.path.join(out_base, "sprites")
    frames_dir = os.path.join(sprites_dir, "_frames")
    ensure_dir(frames_dir)

    # Source (path/url) for ffmpeg
    if req.src_path:
        src = req.src_path
    elif req.src_url:
        src = req.src_url
    else:
        await manager.update_job(job_id, status="failed", error="src_path or src_url required")
        return

    try:
        # 1) Extract frames
        await run_ffmpeg_extract_frames(src, frames_dir, interval, tile_w, tile_h)

        # 2) Pack sprites
        frames = list_frames(frames_dir)
        if not frames:
            raise RuntimeError("No frames generated")

        sprite_paths = pack_sprites(frames, sprites_dir, cols, rows, tile_w, tile_h, quality=85)

        # 3) Write VTT
        # We put relative paths from the video folder in the VTT so the player can access it through its static route.
        # We assume that out_base is accessible via HTTP, just like the file hierarchy (the app will pull it in).
        # For example: /storage/<prefix>/<video_id>/sprites
        # Here we write it as a relative path from out_base:        sprites_web_base = "sprites"
        vtt_path = os.path.join(sprites_dir, "thumbs.vtt")
        write_vtt(
            vtt_path=vtt_path,
            sprites_web_base=sprites_web_base,
            total_frames=len(frames),
            interval_sec=interval,
            cols=cols,
            rows=rows,
            tile_w=tile_w,
            tile_h=tile_h,
        )

        # 4) Prepare result
        sprites_out = []
        for i, p in enumerate(sprite_paths, start=1):
            # path depending on out_base
            rel = os.path.relpath(p, out_base)
            sprites_out.append(SpriteInfo(path=rel.replace("\\", "/"), index=i))

        vtt_rel = os.path.relpath(vtt_path, out_base).replace("\\", "/")
        result = ThumbnailsJobResult(
            sprites=sprites_out,
            vtt=VTTInfo(
                path=vtt_rel,
                meta={
                    "tile_w": tile_w,
                    "tile_h": tile_h,
                    "cols": cols,
                    "rows": rows,
                    "interval": interval,
                },
            ),
        )

        await manager.update_job(job_id, status="succeeded", result=result)

        # 5) Callback
        if req.callback_url:
            body = {
                "job_id": job_id,
                "video_id": req.video_id,
                "status": "succeeded",
                "error": None,
                "sprites": [s.model_dump() for s in sprites_out],
                "vtt": {"path": vtt_rel, "meta": result.vtt.meta},
            }
            await _send_callback(req.callback_url, req.auth_token, body)

    except Exception as e:
        err = str(e)
        await manager.update_job(job_id, status="failed", error=err)
        if req.callback_url:
            body = {
                "job_id": job_id,
                "video_id": req.video_id,
                "status": "failed",
                "error": err,
            }
            await _send_callback(req.callback_url, req.auth_token, body)
    finally:
        try:
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)
        except Exception:
            pass

async def _send_callback(url: str, auth_token: str | None, payload: dict):
    import json as _json
    body_bytes = _json.dumps(payload, ensure_ascii=False).encode("utf-8")
    signature = settings.sign(auth_token or "", body_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-Signature": signature,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(url, content=body_bytes, headers=headers)