"""6步流水线编排 — 串联文档生成全流程"""

import os
import json
import logging
import asyncio
from typing import Optional

from app.schemas import ProjectInfo, TaskStatusEnum
from app.services.claude_analyzer import analyze_all
from app.services.doc_generator import generate_docs
from app.services.screenshot_runner import run_screenshots, run_kuboard_screenshots
from app.services.md2docx_converter import convert_task
from app.utils.task_manager import update_task_status, create_task_status
from app.utils.file_manager import get_output_dir, save_uploaded_files

logger = logging.getLogger(__name__)


async def run_pipeline(
    task_id: str,
    task_dir: str,
    project_info: ProjectInfo,
    backend_files: dict[str, str],
    frontend_files: Optional[dict[str, str]] = None,
    deploy_files: Optional[dict[str, str]] = None,
    storage_state_path: Optional[str] = None,
) -> dict:
    """执行完整的6步流水线

    Args:
        task_id: 任务ID
        task_dir: 任务目录路径
        project_info: 项目信息
        backend_files: {文件名: 内容} 后端源码
        frontend_files: {文件名: 内容} 前端源码（可选）
        deploy_files: {文件名: 内容} 部署配置（可选）
        storage_state_path: Playwright 登录态文件路径（可选）

    Returns:
        最终任务状态 dict
    """
    output_dir = os.path.join(task_dir, "output")
    images_dir = os.path.join(output_dir, "images")

    try:
        # ========== Step 1: 收集信息（已在API层完成） ==========

        # ========== Step 2: Claude API 代码分析 ==========

        update_task_status(task_id, status=TaskStatusEnum.ANALYZING, progress="第2步：调用 Claude API 分析代码库...")

        analysis_results = await analyze_all(
            backend_files=backend_files,
            frontend_files=frontend_files,
            deploy_files=deploy_files,
        )
        logger.info(f"代码分析完成: backend={len(analysis_results.get('backend', {}))} keys, frontend={'有' if analysis_results.get('frontend') else '无'}")

        # 保存分析结果到任务目录
        analysis_path = os.path.join(task_dir, "analysis.json")
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, ensure_ascii=False, indent=2)

        # ========== Step 3: 生成 Markdown 文档 ==========

        update_task_status(task_id, status=TaskStatusEnum.GENERATING_MD, progress="第3步：调用 Claude API 生成7份运维文档...")

        md_files = await generate_docs(project_info, analysis_results, output_dir)
        logger.info(f"文档生成完成: {md_files}")

        update_task_status(task_id, md_files=md_files)

        # ========== Step 4: 执行 Playwright 截图 ==========

        update_task_status(task_id, status=TaskStatusEnum.RUNNING_SCREENSHOTS, progress="第4步：执行 Playwright 自动截图...")

        screenshot_files = []

        # 从前端分析结果中提取路由列表
        frontend_analysis = analysis_results.get("frontend")
        if frontend_analysis and project_info.production_url:
            routes = []
            if isinstance(frontend_analysis, dict) and "routes" in frontend_analysis:
                for route in frontend_analysis["routes"]:
                    if isinstance(route, dict) and "path" in route:
                        route_path = route["path"]
                        if route_path and route_path != "/login":  # login单独截图
                            routes.append(route_path)

            routing_mode = "hash"
            if isinstance(frontend_analysis, dict) and "routing_mode" in frontend_analysis:
                routing_mode = frontend_analysis.get("routing_mode", "hash")

            if routes:
                screenshot_files.extend(
                    await run_screenshots(
                        production_url=project_info.production_url,
                        routes=routes,
                        output_images_dir=images_dir,
                        storage_state_path=storage_state_path,
                        routing_mode=routing_mode,
                    )
                )

        # Kuboard 截图
        if project_info.kuboard_url:
            kuboard_auth = storage_state_path  # 复用同一个 storageState
            screenshot_files.extend(
                await run_kuboard_screenshots(
                    kuboard_url=project_info.kuboard_url,
                    output_images_dir=images_dir,
                    storage_state_path=kuboard_auth,
                )
            )

        update_task_status(task_id, screenshot_files=screenshot_files)
        logger.info(f"截图完成: {screenshot_files}")

        # ========== Step 5: 嵌入截图引用 ==========

        update_task_status(task_id, status=TaskStatusEnum.EMBEDDING_IMAGES, progress="第5步：校验截图引用...")

        # MD 文件中已在 Step 3 包含 ![描述](images/xxx.png) 引用
        # 这里校验图片文件是否存在，对缺失的图片添加红色占位标记
        for md_file in md_files:
            md_path = os.path.join(output_dir, md_file)
            if not os.path.exists(md_path):
                continue
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 校验图片引用中的文件名是否存在于 images/ 目录
            import re
            img_refs = re.findall(r'!\[.*?\]\(images/(.*?)\)', content)
            for img_name in img_refs:
                img_path = os.path.join(images_dir, img_name)
                if not os.path.exists(img_path):
                    logger.warning(f"图片缺失: {img_name}")

        # ========== Step 6: 转换为 DOCX ==========

        update_task_status(task_id, status=TaskStatusEnum.CONVERTING_DOCX, progress="第6步：转换 Markdown 为 DOCX...")

        docx_files = convert_task(output_dir, md_files)
        logger.info(f"DOCX转换完成: {docx_files}")

        # ========== 完成 ==========

        update_task_status(
            task_id,
            status=TaskStatusEnum.COMPLETED,
            progress="文档生成完成！",
            output_files=docx_files,
        )

        return update_task_status(task_id).get("output_files", [])

    except Exception as e:
        logger.error(f"流水线执行失败: {e}", exc_info=True)
        update_task_status(task_id, error=str(e))
        return []