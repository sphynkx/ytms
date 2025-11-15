import asyncio
import uuid
from typing import Dict, Optional, Any

from app.schemas import JobInfo, ThumbnailsJobCreate
from app.workers import process_thumbnails_job

class JobManager:
    def __init__(self) -> None:
        self.queue: "asyncio.Queue[tuple[str, str, dict]]" = asyncio.Queue()
        self.jobs: Dict[str, JobInfo] = {}
        self._shutdown = asyncio.Event()

    async def submit_thumbnails(self, payload: ThumbnailsJobCreate) -> JobInfo:
        job_id = str(uuid.uuid4())
        info = JobInfo(job_id=job_id, kind="thumbnails", status="queued")
        self.jobs[job_id] = info
        await self.queue.put(("thumbnails", job_id, payload.model_dump()))
        return info

    async def get_job(self, job_id: str) -> Optional[JobInfo]:
        return self.jobs.get(job_id)

    async def run_workers(self, num_workers: int = 1):
        async def worker():
            while not self._shutdown.is_set():
                try:
                    kind, job_id, payload = await self.queue.get()
                except asyncio.CancelledError:
                    break
                try:
                    if kind == "thumbnails":
                        await process_thumbnails_job(self, job_id, payload)
                finally:
                    self.queue.task_done()
        tasks = [asyncio.create_task(worker()) for _ in range(max(1, num_workers))]
        try:
            await self._shutdown.wait()
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def update_job(self, job_id: str, **fields: Any):
        info = self.jobs.get(job_id)
        if not info:
            return
        for k, v in fields.items():
            setattr(info, k, v)

    async def shutdown(self):
        self._shutdown.set()
        # drain queue quickly
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception:
                break