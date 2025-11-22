from fastapi import APIRouter, HTTPException, Request
from schemas import ThumbnailsJobCreate, JobInfo

router = APIRouter(tags=["thumbnails"])


@router.post("/jobs/thumbnails", response_model=JobInfo, status_code=202)
async def create_thumbnails_job(data: ThumbnailsJobCreate, request: Request):
    if not data.src_path and not data.src_url:
        raise HTTPException(status_code=400, detail="src_path or src_url required")
    if not data.out_base_path:
        raise HTTPException(status_code=400, detail="out_base_path required")
    jm = request.app.state.job_manager
    info = await jm.submit_thumbnails(data)
    return info


@router.get("/jobs/{job_id}", response_model=JobInfo)
async def get_job(job_id: str, request: Request):
    jm = request.app.state.job_manager
    info = await jm.get_job(job_id)
    if not info:
        raise HTTPException(status_code=404, detail="job_not_found")
    return info