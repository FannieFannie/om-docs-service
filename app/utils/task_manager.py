"""异步任务状态管理 — 追踪流水线各步骤进度"""

import os
import json
import logging
from typing import Optional

from app.schemas import TaskStatusEnum
from app.utils.file_manager import get_task_dir

logger = logging.getLogger(__name__)

# 任务状态文件名
STATUS_FILE = "status.json"


def _status_path(task_id: str) -> str:
    return os.path.join(get_task_dir(task_id), STATUS_FILE)


def create_task_status(task_id: str) -> dict:
    """创建初始任务状态"""
    status = {
        "task_id": task_id,
        "status": TaskStatusEnum.PENDING.value,
        "progress": "任务已创建，等待处理",
        "error": None,
        "output_files": [],
        "md_files": [],
        "screenshot_files": [],
    }
    _save_status(task_id, status)
    return status


def update_task_status(
    task_id: str,
    status: Optional[TaskStatusEnum] = None,
    progress: Optional[str] = None,
    error: Optional[str] = None,
    output_files: Optional[list[str]] = None,
    md_files: Optional[list[str]] = None,
    screenshot_files: Optional[list[str]] = None,
) -> dict:
    """更新任务状态"""
    current = get_task_status(task_id)

    if status is not None:
        current["status"] = status.value
    if progress is not None:
        current["progress"] = progress
    if error is not None:
        current["error"] = error
        current["status"] = TaskStatusEnum.FAILED.value
    if output_files is not None:
        current["output_files"] = output_files
    if md_files is not None:
        current["md_files"] = md_files
    if screenshot_files is not None:
        current["screenshot_files"] = screenshot_files

    _save_status(task_id, current)
    return current


def get_task_status(task_id: str) -> dict:
    """读取任务状态"""
    path = _status_path(task_id)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "task_id": task_id,
        "status": TaskStatusEnum.PENDING.value,
        "progress": "",
        "error": None,
        "output_files": [],
    }


def _save_status(task_id: str, status: dict):
    """保存任务状态到文件"""
    path = _status_path(task_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)