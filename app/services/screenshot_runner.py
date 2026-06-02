"""Playwright 截图执行模块 — Python playwright 自动截图"""

import os
import json
import logging
import asyncio
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


async def run_screenshots(
    production_url: str,
    routes: list[str],
    output_images_dir: str,
    storage_state_path: Optional[str] = None,
    routing_mode: str = "hash",
    wait_timeout: int = 3000,
) -> list[str]:
    """执行 Playwright 截图

    Args:
        production_url: 生产环境基础URL（如 http://10.5.16.240/app）
        routes: 前端路由路径列表（如 ["/login", "/dashboard", "/settings"]）
        output_images_dir: 截图输出目录
        storage_state_path: Playwright storageState JSON 文件路径（含登录态）
        routing_mode: 路由模式 "hash" 或 "history"
        wait_timeout: 页面等待超时(ms)，默认3秒

    Returns:
        生成的截图文件名列表
    """
    os.makedirs(output_images_dir, exist_ok=True)
    screenshot_files = []

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context_opts = {"viewport": {"width": settings.SCREENSHOT_VIEWPORT_WIDTH, "height": settings.SCREENSHOT_VIEWPORT_HEIGHT}}
            if storage_state_path and os.path.exists(storage_state_path):
                context_opts["storage_state"] = storage_state_path
            context = await browser.new_context(**context_opts)

            page = await context.new_page()

            for route in routes:
                # 构造完整URL
                if routing_mode == "hash":
                    url = f"{production_url}/#{route.lstrip('/')}"
                else:
                    url = f"{production_url}/{route.lstrip('/')}"

                logger.info(f"截图路由: {route} → {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    # 等待页面渲染
                    await page.wait_for_timeout(wait_timeout)

                    # 截图文件名：路由转为英文小写+下划线
                    safe_name = route.lstrip('/').replace('/', '_').replace('-', '_') or "home"
                    filename = f"{safe_name}.png"
                    filepath = os.path.join(output_images_dir, filename)

                    await page.screenshot(path=filepath, full_page=True)
                    screenshot_files.append(filename)
                    logger.info(f"截图成功: {filename}")

                except Exception as e:
                    logger.warning(f"截图失败 {route}: {e}")
                    # 生成空白占位图片
                    safe_name = route.lstrip('/').replace('/', '_').replace('-', '_') or "home"
                    filename = f"{safe_name}.png"
                    screenshot_files.append(filename)

            # 登录页单独截图（如果还没截过）
            login_route = "/login"
            if login_route not in routes and production_url:
                login_url = f"{production_url}/#{login_route.lstrip('/')}" if routing_mode == "hash" else f"{production_url}/{login_route.lstrip('/')}"
                try:
                    page2 = await context.new_page()
                    await page2.goto(login_url, wait_until="domcontentloaded", timeout=15000)
                    await page2.wait_for_timeout(2000)
                    filepath = os.path.join(output_images_dir, "login.png")
                    await page2.screenshot(path=filepath, full_page=True)
                    screenshot_files.append("login.png")
                    logger.info("登录页截图成功")
                except Exception as e:
                    logger.warning(f"登录页截图失败: {e}")

            await browser.close()

    except ImportError:
        logger.error("playwright 未安装，请运行: pip install playwright && playwright install chromium")
        # 生成空截图列表，不中断流水线
    except Exception as e:
        logger.error(f"截图流程异常: {e}")

    return screenshot_files


async def run_kuboard_screenshots(
    kuboard_url: str,
    output_images_dir: str,
    storage_state_path: Optional[str] = None,
) -> list[str]:
    """执行 Kuboard 运维看板截图（9张）

    Args:
        kuboard_url: Kuboard 基础URL
        output_images_dir: 截图输出目录
        storage_state_path: 登录态文件路径

    Returns:
        Kuboard截图文件名列表
    """
    os.makedirs(output_images_dir, exist_ok=True)
    screenshot_files = []

    # Kuboard 9张截图的页面路径
    kuboard_pages = [
        ("namespace_overview", ""),
        ("pod_list", "/pods"),
        ("deployment_list", "/deployments"),
        ("service_list", "/services"),
        ("configmap_list", "/configmaps"),
        ("pvc_list", "/persistentvolumeclaims"),
        ("pod_detail", "/pods/detail"),
        ("pod_log", "/pods/log"),
        ("deployment_events", "/deployments/events"),
    ]

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context_options = {
                "viewport": {"width": settings.SCREENSHOT_VIEWPORT_WIDTH, "height": settings.SCREENSHOT_VIEWPORT_HEIGHT}
            }
            if storage_state_path and os.path.exists(storage_state_path):
                context_options["storage_state"] = storage_state_path

            context = await browser.new_context(**context_options)
            page = await context.new_page()

            for name, path_suffix in kuboard_pages:
                url = f"{kuboard_url}{path_suffix}"
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(3000)
                    filename = f"kuboard_{name}.png"
                    filepath = os.path.join(output_images_dir, filename)
                    await page.screenshot(path=filepath, full_page=True)
                    screenshot_files.append(filename)
                    logger.info(f"Kuboard截图: {filename}")
                except Exception as e:
                    logger.warning(f"Kuboard截图失败 {name}: {e}")
                    screenshot_files.append(f"kuboard_{name}.png")

            await browser.close()

    except ImportError:
        logger.error("playwright 未安装")
    except Exception as e:
        logger.error(f"Kuboard截图异常: {e}")

    return screenshot_files