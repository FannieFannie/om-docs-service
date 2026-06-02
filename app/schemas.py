from enum import Enum
from typing import Optional
from pydantic import BaseModel


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING_MD = "generating_md"
    RUNNING_SCREENSHOTS = "running_screenshots"
    EMBEDDING_IMAGES = "embedding_images"
    CONVERTING_DOCX = "converting_docx"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerateResponse(BaseModel):
    task_id: str
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    message: str = "任务已创建"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: TaskStatusEnum
    progress: str = ""
    error: Optional[str] = None
    output_files: list[str] = []


class ProjectInfo(BaseModel):
    project_name: str
    project_desc: str = ""
    production_url: str = ""
    kuboard_url: Optional[str] = None
    helm_url: Optional[str] = None
    has_frontend: bool = True