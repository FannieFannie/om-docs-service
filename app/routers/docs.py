"""文档生成 API 路由 — 4个端点"""

import os
import io
import zipfile
import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas import GenerateResponse, TaskStatusResponse, ProjectInfo, TaskStatusEnum
from app.utils.file_manager import (
    create_task_dir, save_uploaded_files,
    get_output_dir, get_docx_files, task_exists, get_task_dir,
)
from app.utils.task_manager import create_task_status, update_task_status, get_task_status
from app.services.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate_docs(
    background_tasks: BackgroundTasks,
    project_name: str = Form(...),
    project_desc: str = Form(""),
    production_url: str = Form(""),
    kuboard_url: Optional[str] = Form(None),
    helm_url: Optional[str] = Form(None),
    has_frontend: bool = Form(True),
    backend_files: List[UploadFile] = File(...),
    frontend_files: Optional[List[UploadFile]] = File(None),
    storage_state: Optional[UploadFile] = File(None),
):
    """启动文档生成任务

    接收前端上传的源码文件和项目信息，异步执行6步流水线生成运维文档。
    """
    # 创建任务目录
    task_id, task_dir = create_task_dir()
    create_task_status(task_id)

    # 保存上传文件
    backend_dir = os.path.join(task_dir, "upload", "backend")
    frontend_dir = os.path.join(task_dir, "upload", "frontend")
    auth_dir = os.path.join(task_dir, "auth")

    backend_content = await save_uploaded_files(backend_files, backend_dir)

    frontend_content = {}
    if frontend_files:
        frontend_content = await save_uploaded_files(frontend_files, frontend_dir)

    # 保存 storageState（登录态）
    storage_state_path = None
    if storage_state:
        ss_content = await storage_state.read()
        storage_state_path = os.path.join(auth_dir, "storage_state.json")
        with open(storage_state_path, 'wb') as f:
            f.write(ss_content)

    # 构建项目信息
    project_info = ProjectInfo(
        project_name=project_name,
        project_desc=project_desc,
        production_url=production_url,
        kuboard_url=kuboard_url,
        helm_url=helm_url,
        has_frontend=has_frontend,
    )

    # 后台异步执行流水线
    background_tasks.add_task(
        run_pipeline,
        task_id=task_id,
        task_dir=task_dir,
        project_info=project_info,
        backend_files=backend_content,
        frontend_files=frontend_content or None,
        deploy_files=None,  # 部署配置可后续扩展
        storage_state_path=storage_state_path,
    )

    return GenerateResponse(task_id=task_id, message="任务已创建，正在后台处理")


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(task_id: str):
    """查询任务生成状态"""
    if not task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    status = get_task_status(task_id)
    return TaskStatusResponse(
        task_id=status["task_id"],
        status=TaskStatusEnum(status["status"]),
        progress=status["progress"],
        error=status.get("error"),
        output_files=status.get("output_files", []),
    )


@router.get("/download/{task_id}/{filename}")
async def download_docx(task_id: str, filename: str):
    """下载单个 DOCX 文件"""
    if not task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    output_dir = get_output_dir(task_id)
    filepath = os.path.join(output_dir, filename)

    # 安全检查：防止路径遍历
    filename = os.path.basename(filename)
    filepath = os.path.join(output_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在")

    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.get("/download/{task_id}/all")
async def download_all(task_id: str):
    """下载全部 DOCX 文件（zip 打包）"""
    if not task_exists(task_id):
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    output_dir = get_output_dir(task_id)
    docx_files = get_docx_files(task_id)

    if not docx_files:
        status = get_task_status(task_id)
        if status["status"] != TaskStatusEnum.COMPLETED.value:
            raise HTTPException(status_code=400, detail="文档尚未生成完成")
        raise HTTPException(status_code=404, detail="没有可下载的DOCX文件")

    # 创建 zip 包
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for docx_file in docx_files:
            filepath = os.path.join(output_dir, docx_file)
            zf.write(filepath, docx_file)
        # 同时打包 MD 文件
        md_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
        for md_file in md_files:
            filepath = os.path.join(output_dir, md_file)
            zf.write(filepath, md_file)

    zip_buffer.seek(0)

    project_name = get_task_status(task_id).get("project_name", task_id)
    zip_filename = f"{project_name}_运维文档.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"},
    )