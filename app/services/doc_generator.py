"""文档生成模块 — 调用 Claude API 生成7份 MD 文档，并拆分写入文件"""

import json
import os
import re
import logging

from app.services.claude_analyzer import call_claude_async
from app.prompts.doc_templates import DOC_GENERATION_SYSTEM, DOC_GENERATION_PROMPT
from app.schemas import ProjectInfo

logger = logging.getLogger(__name__)

# 默认7份文档的文件名映射
DEFAULT_DOC_FILES = [
    "01_用户手册.md",
    "02_部署清单.md",
    "03_技术栈说明.md",
    "04_日常运维手册.md",
    "05_系统启停流程.md",
    "06_备份与恢复手册.md",
    "07_数据库设计文档.md",
]


def _build_generation_prompt(
    project_info: ProjectInfo,
    analysis_results: dict,
) -> str:
    """构建文档生成 prompt"""
    backend_analysis = json.dumps(analysis_results.get("backend", {}), indent=2, ensure_ascii=False)
    frontend_data = analysis_results.get("frontend")
    frontend_analysis = json.dumps(frontend_data, indent=2, ensure_ascii=False) if frontend_data else "无前端代码"
    deploy_data = analysis_results.get("deploy")
    deploy_analysis = json.dumps(deploy_data, indent=2, ensure_ascii=False) if deploy_data else "无部署配置"

    prompt = DOC_GENERATION_PROMPT.format(
        project_name=project_info.project_name,
        project_desc=project_info.project_desc,
        production_url=project_info.production_url,
        kuboard_url=project_info.kuboard_url or "无",
        helm_url=project_info.helm_url or "无",
        has_frontend="是" if project_info.has_frontend else "否",
        backend_analysis=backend_analysis,
        frontend_analysis=frontend_analysis,
        deploy_analysis=deploy_analysis,
    )
    return prompt


def _split_docs(claude_response: str) -> dict[str, str]:
    """从 Claude 返回的文本中按 DOC_SEPARATOR 拆分为各文件内容

    Returns:
        {文件名: Markdown内容}
    """
    docs = {}

    # 按 ---DOC_SEPARATOR--- 拆分
    segments = re.split(r'---DOC_SEPARATOR---', claude_response)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # 提取 FILE: xxx.md 标记
        file_match = re.match(r'FILE:\s*(.+\.md)\s*\n', segment)
        if file_match:
            filename = file_match.group(1).strip()
            content = segment[len(file_match.group(0)):].strip()
            docs[filename] = content
        else:
            # 没有 FILE 标记，尝试按序号分配
            logger.warning(f"文档片段缺少 FILE 标记，尝试按序号分配")

    # 如果拆分不足7份，尝试补全
    if len(docs) < 7:
        # 按 ## 标题开头的大段拆分
        logger.warning(f"仅拆分出 {len(docs)} 份文档，期望7份")

    # 将实际文件名映射为默认文件名
    result = {}
    for default_name in DEFAULT_DOC_FILES:
        # 尝试直接匹配
        if default_name in docs:
            result[default_name] = docs[default_name]
            continue

        # 尝试按序号匹配（如 "01_xxx.md" → 第1份文档）
        num = default_name.split("_")[0]
        for actual_name, content in docs.items():
            if actual_name.startswith(num + "_"):
                result[default_name] = content
                break

    # 如果映射后仍不足7份，把未映射的内容追加到最后一个已有文件
    mapped_names = set(result.keys())
    unmapped = {k: v for k, v in docs.items() if k not in mapped_names}
    if unmapped and result:
        last_key = list(result.keys())[-1]
        for name, content in unmapped.items():
            result[last_key] += "\n\n" + content

    return result


async def generate_docs(
    project_info: ProjectInfo,
    analysis_results: dict,
    output_dir: str,
) -> list[str]:
    """生成7份 MD 文档并写入 output_dir

    Args:
        project_info: 项目信息
        analysis_results: Claude 代码分析结果
        output_dir: 文档输出目录

    Returns:
        生成的 MD 文件名列表
    """
    # 构建 prompt
    prompt = _build_generation_prompt(project_info, analysis_results)

    # 调用 Claude 生成文档内容
    logger.info("调用 Claude API 生成7份文档...")
    claude_response = await call_claude_async(DOC_GENERATION_SYSTEM, prompt)
    logger.info(f"Claude 返回文档内容 {len(claude_response)} chars")

    # 拆分为各文件
    doc_contents = _split_docs(claude_response)

    # 确保 images 子目录存在
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    # 写入文件
    generated_files = []
    for filename, content in doc_contents.items():
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        generated_files.append(filename)
        logger.info(f"写入文档: {filepath} ({len(content)} chars)")

    # 补足缺失的文档（如果 Claude 没生成完整的7份）
    for default_name in DEFAULT_DOC_FILES:
        if default_name not in doc_contents:
            filepath = os.path.join(output_dir, default_name)
            placeholder = f"# {default_name.replace('.md', '').replace('_', ' ')}\n\n> 此文档因源码信息不足暂未生成，请在有更多源码信息后重新生成。\n"
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(placeholder)
            generated_files.append(default_name)
            logger.warning(f"生成占位文档: {filepath}")

    return generated_files