"""Claude API 代码分析模块 — 调用 Anthropic Claude API 分析源码"""

import json
import asyncio
import logging
from typing import Optional

import anthropic

from app.config import settings
from app.prompts.backend_explore import BACKEND_EXPLORE_PROMPT, BACKEND_EXPLORE_SYSTEM
from app.prompts.frontend_explore import FRONTEND_EXPLORE_PROMPT
from app.prompts.deploy_explore import DEPLOY_EXPLORE_PROMPT
from app.prompts.doc_templates import DOC_GENERATION_SYSTEM, DOC_GENERATION_PROMPT

logger = logging.getLogger(__name__)

# Claude API 单次调用最大 token 限制
MAX_INPUT_TOKENS = 180000  # claude-sonnet 上限约 200K，留 20K 给输出
MAX_OUTPUT_TOKENS = 8192


def _truncate_content(content: str, max_chars: int = 150000) -> str:
    """截断超长内容以避免超出 token 限制"""
    if len(content) > max_chars:
        logger.warning(f"源码内容过长({len(content)} chars)，截断至 {max_chars}")
        return content[:max_chars] + "\n\n[... 内容已截断 ...]"
    return content


def _build_source_content(files: dict[str, str]) -> str:
    """将文件字典构建为 Claude 可读的源码内容字符串

    Args:
        files: {相对路径: 文件内容} 的字典
    """
    parts = []
    for path, content in files.items():
        parts.append(f"### 文件: {path}\n```\n{content}\n```\n")
    return "\n".join(parts)


def call_claude(system_prompt: str, user_prompt: str) -> str:
    """单次 Claude API 调用

    Returns:
        Claude 返回的文本内容
    """
    client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

    logger.info(f"调用 Claude API，model={settings.CLAUDE_MODEL}")
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = response.content[0].text
    logger.info(f"Claude API 返回 {len(text)} chars")
    return text


async def call_claude_async(system_prompt: str, user_prompt: str) -> str:
    """异步 Claude API 调用"""
    return await asyncio.to_thread(call_claude, system_prompt, user_prompt)


def _parse_json_response(text: str) -> dict:
    """从 Claude 返回文本中提取 JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 ```json ... ``` 中提取
    import re
    json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试找第一个 { 到最后一个 }
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"无法解析 Claude 返回为 JSON，原始文本前200字: {text[:200]}")
    return {"raw_text": text}


async def analyze_backend(files: dict[str, str]) -> dict:
    """分析后端代码"""
    source = _truncate_content(_build_source_content(files))
    user_prompt = BACKEND_EXPLORE_PROMPT.replace("{source_code}", source)
    text = await call_claude_async(BACKEND_EXPLORE_SYSTEM, user_prompt)
    return _parse_json_response(text)


async def analyze_frontend(files: dict[str, str]) -> dict:
    """分析前端代码"""
    source = _truncate_content(_build_source_content(files))
    user_prompt = FRONTEND_EXPLORE_PROMPT.replace("{source_code}", source)
    # 前端分析不需要特殊 system prompt
    text = await call_claude_async("你是前端代码分析引擎，输出JSON格式。", user_prompt)
    return _parse_json_response(text)


async def analyze_deploy(files: dict[str, str]) -> dict:
    """分析部署配置"""
    source = _truncate_content(_build_source_content(files))
    user_prompt = DEPLOY_EXPLORE_PROMPT.replace("{source_code}", source)
    text = await call_claude_async("你是部署配置分析引擎，输出JSON格式。", user_prompt)
    return _parse_json_response(text)


async def analyze_all(
    backend_files: dict[str, str],
    frontend_files: Optional[dict[str, str]] = None,
    deploy_files: Optional[dict[str, str]] = None,
) -> dict:
    """并行调用3次 Claude API 完成全部代码分析

    Returns:
        {"backend": {...}, "frontend": {...}, "deploy": {...}}
    """
    tasks = []
    task_names = []

    tasks.append(analyze_backend(backend_files))
    task_names.append("backend")

    if frontend_files:
        tasks.append(analyze_frontend(frontend_files))
        task_names.append("frontend")

    if deploy_files:
        tasks.append(analyze_deploy(deploy_files))
        task_names.append("deploy")

    results_list = await asyncio.gather(*tasks)

    results = {}
    for name, result in zip(task_names, results_list):
        results[name] = result

    # 无前端或无部署配置时填空
    if "frontend" not in results:
        results["frontend"] = None
    if "deploy" not in results:
        results["deploy"] = None

    return results