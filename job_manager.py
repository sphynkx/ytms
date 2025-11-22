import asyncio
import json
from typing import Dict, Any, Optional

import httpx

from schemas import (
    ThumbnailsJobCreate,
    JobInfo,
    ThumbnailsJobResult,
)
from utils.utils_ut import generate_thumbnails_pipeline
from config import settings


class JobManager:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._shutdown = False


    async def submit_thumbnails(self, data: ThumbnailsJobCreate) -> JobInfo:
        job_id = self._gen_job_id()
        record = {
            "job_id": job_id,
            "kind": "thumbnails",
            "status": "queued",
            "error": None,
            "result": None,
            "payload": data.model_dump(),
        }
        self.jobs[job_id] = record
        await self.queue.put(job_id)
        print(f"[JOB SUBMIT] job_id={job_id} video_id={data.video_id} out_base={data.out_base_path}")
        return JobInfo(
            job_id=job_id,
            kind="thumbnails",
            status="queued",
            error=None,
            result=None,
        )


    async def get_job(self, job_id: str) -> Optional[JobInfo]:
        rec = self.jobs.get(job_id)
        if not rec:
            return None
        result_obj = None
        if rec["result"]:
            result_obj = ThumbnailsJobResult(**rec["result"])
        return JobInfo(
            job_id=rec["job_id"],
            kind=rec["kind"],
            status=rec["status"],
            error=rec["error"],
            result=result_obj,
        )


    async def run_workers(self, num_workers: int = 1):
        workers = [asyncio.create_task(self._worker_loop(i)) for i in range(max(1, num_workers))]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            pass


    async def shutdown(self):
        self._shutdown = True
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception:
                break
        print("[JOB MANAGER] shutdown initiated")


    async def _worker_loop(self, worker_id: int):
        print(f"[WORKER START] id={worker_id}")
        while not self._shutdown:
            try:
                job_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            rec = self.jobs.get(job_id)
            if not rec:
                self.queue.task_done()
                continue
            rec["status"] = "running"
            print(f"[WORKER] id={worker_id} job_id={job_id} running")
            try:
                await self._process_thumbnails(job_id, rec["payload"])
                rec["status"] = "succeeded"
                print(f"[WORKER] id={worker_id} job_id={job_id} succeeded")
            except Exception as e:
                rec["status"] = "failed"
                rec["error"] = str(e)
                print(f"[WORKER ERROR] id={worker_id} job_id={job_id} error={e}")
                await self._send_callback_failed(rec["payload"], str(e))
            finally:
                self.queue.task_done()


    async def _process_thumbnails(self, job_id: str, payload: Dict[str, Any]):
        data = ThumbnailsJobCreate(**payload)
        print(f"[PIPELINE START] job_id={job_id} video_id={data.video_id}")
        pipeline_result = await generate_thumbnails_pipeline(
            video_id=data.video_id,
            out_base_path=data.out_base_path,
            src_path=data.src_path,
            src_url=data.src_url,
            interval_sec=data.interval_sec,
            tile_w=data.tile_w,
            tile_h=data.tile_h,
            cols=data.cols,
            rows=data.rows,
        )
        sprites_struct = [
            {"path": sp["path"], "index": i}
            for i, sp in enumerate(pipeline_result["sprites"])
        ]
        vtt_struct = {
            "path": pipeline_result["vtt"]["path"],
            "meta": pipeline_result["meta"],
        }
        result_obj = {
            "sprites": sprites_struct,
            "vtt": vtt_struct,
        }

        rec = self.jobs.get(job_id)
        if rec is not None:
            rec["result"] = result_obj

        print(f"[PIPELINE DONE] job_id={job_id} frames={pipeline_result['meta']['frames']} sprites={len(sprites_struct)} vtt={vtt_struct['path']}")
        await self._send_callback_success(data, result_obj)


    async def _send_callback_success(self, data: ThumbnailsJobCreate, result_obj: Dict[str, Any]):
        if not data.callback_url:
            print("[CALLBACK SKIP] no callback_url")
            return
        body = {
            "status": "succeeded",
            "video_id": data.video_id,
            "vtt": {"path": result_obj["vtt"]["path"], "meta": result_obj["vtt"]["meta"]},
            "sprites": [{"path": s["path"], "index": s["index"]} for s in result_obj["sprites"]],
        }
        raw = json.dumps(body).encode("utf-8")
        sig = settings.sign(data.auth_token, raw)
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                r = await client.post(data.callback_url, content=raw, headers={"X-Signature": sig})
                print("[CALLBACK SUCCESS]", r.status_code, r.text[:200])
            except Exception as e:
                print("[CALLBACK ERROR success]", e)


    async def _send_callback_failed(self, payload: Dict[str, Any], error: str):
        data = ThumbnailsJobCreate(**payload)
        if not data.callback_url:
            print("[CALLBACK SKIP FAILED] no callback_url")
            return
        body = {
            "status": "failed",
            "video_id": data.video_id,
            "error": error,
        }
        raw = json.dumps(body).encode("utf-8")
        sig = settings.sign(data.auth_token, raw)
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                r = await client.post(data.callback_url, content=raw, headers={"X-Signature": sig})
                print("[CALLBACK FAILED]", r.status_code, r.text[:200])
            except Exception as e:
                print("[CALLBACK ERROR failed]", e)


    def _gen_job_id(self) -> str:
        import uuid
        return str(uuid.uuid4())