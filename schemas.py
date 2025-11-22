from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "succeeded", "failed"]


class ThumbnailsJobCreate(BaseModel):
    video_id: str
    out_base_path: str
    src_path: Optional[str] = None
    src_url: Optional[str] = None

    interval_sec: Optional[float] = Field(None, ge=0.2, le=120.0)
    tile_w: Optional[int] = Field(None, ge=16, le=2048)
    tile_h: Optional[int] = Field(None, ge=16, le=2048)
    cols: Optional[int] = Field(None, ge=1, le=500)
    rows: Optional[int] = Field(None, ge=1, le=500)

    callback_url: Optional[str] = None
    auth_token: Optional[str] = None


class SpriteInfo(BaseModel):
    path: str
    index: int


class VTTInfo(BaseModel):
    path: str
    meta: Dict[str, Any]


class ThumbnailsJobResult(BaseModel):
    sprites: List[SpriteInfo]
    vtt: VTTInfo


class JobInfo(BaseModel):
    job_id: str
    kind: Literal["thumbnails"]
    status: JobStatus
    error: Optional[str] = None
    result: Optional[ThumbnailsJobResult] = None