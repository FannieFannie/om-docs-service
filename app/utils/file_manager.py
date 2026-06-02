"""临时文件管理 — 上传文件存储、输出目录管理、过期清理"""

import os
import shutil
import time
import uuid
import aiofiles
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def create_task_dir() -> str:
    """创建任务专属目录，返回 task_id 和目录路径

    目录结构：
    tasks/{task_id}/
        upload/backend/     — 后端源码文件
        upload/frontend/    — 前端源码文件
        upload/deploy/      — 部署配置文件
        output/             — 生成的MD/DOCX文件
        output/images/      — 截图文件
        auth/               — storageState等认证文件
    """
    task_id = str(uuid.uuid4())[:8]
    task_dir = os.path.join(settings.TASK_BASE_DIR, task_id)

    os.makedirs(os.path.join(task_dir, "upload", "backend"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "upload", "frontend"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "upload", "deploy"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "output", "images"), exist_ok=True)
    os.makedirs(os.path.join(task_dir, "auth"), exist_ok=True)

    return task_id, task_dir


async def save_uploaded_files(
    files: list,
    target_dir: str,
) -> dict[str, str]:
    """保存上传文件到目标目录，返回 {相对路径: 文件内容} 字典

    Args:
        files: FastAPI UploadFile 列表
        target_dir: 保存目标目录
    """
    result = {}
    for upload_file in files:
        filename = upload_file.filename
        filepath = os.path.join(target_dir, filename)

        # 防止路径遍历
        filename = os.path.basename(filename)
        filepath = os.path.join(target_dir, filename)

        content = await upload_file.read()
        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)

        # 读取文本内容用于 Claude 分析
        try:
            text_content = content.decode('utf-8')
            result[filename] = text_content
        except UnicodeDecodeError:
            # 非文本文件（如图片、二进制配置），跳过内容提取
            logger.warning(f"跳过非文本文件: {filename}")

    return result


def get_task_dir(task_id: str) -> str:
    """获取任务目录路径"""
    return os.path.join(settings.TASK_BASE_DIR, task_id)


def task_exists(task_id: str) -> bool:
    """检查任务目录是否存在"""
    return os.path.isdir(get_task_dir(task_id))


def get_output_dir(task_id: str) -> str:
    """获取输出目录路径"""
    return os.path.join(get_task_dir(task_id), "output")


def get_docx_files(task_id: str) -> list[str]:
    """获取输出目录中所有 DOCX 文件名"""
    output_dir = get_output_dir(task_id)
    if not os.path.isdir(output_dir):
        return []
    return [f for f in os.listdir(output_dir) if f.endswith('.docx')]


def cleanup_old_tasks(max_age_hours: int = 24):
    """清理超过 max_age_hours 的旧任务目录"""
    if not os.path.exists(settings.TASK_BASE_DIR):
        return

    now = time.time()
    for entry in os.listdir(settings.TASK_BASE_DIR):
        task_dir = os.path.join(settings.TASK_BASE_DIR, entry)
        if not os.path.isdir(task_dir):
            continue
        # 检查目录创建时间
        dir_mtime = os.path.getmtime(task_dir)
        age_hours = (now - dir_mtime) / 3600
        if age_hours > max_age_hours:
            shutil.rmtree(task_dir)
            logger.info(f"清理旧任务: {entry} (age: {age_hours:.1f}h)")