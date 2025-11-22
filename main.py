import asyncio
from fastapi import FastAPI
from config import settings
from job_manager import JobManager
from routes.thumbnails_rout import router as thumbnails_router

app = FastAPI(title="YT Media Service (ytms)", version="0.1.0")

job_manager = JobManager()
app.state.job_manager = job_manager


@app.on_event("startup")
async def startup_event():
    app.state.worker_task = asyncio.create_task(job_manager.run_workers(num_workers=settings.WORKERS))


@app.on_event("shutdown")
async def shutdown_event():
    await job_manager.shutdown()


app.include_router(thumbnails_router, prefix="/api")


@app.get("/healthz")
async def health():
    return {"ok": True}