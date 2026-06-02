import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    CLAUDE_API_KEY: str = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6-20250514")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    TASK_BASE_DIR: str = os.getenv("TASK_BASE_DIR", "D:/coding/om-docs-service/tasks")
    SCREENSHOT_VIEWPORT_WIDTH: int = int(os.getenv("SCREENSHOT_VIEWPORT_WIDTH", "1920"))
    SCREENSHOT_VIEWPORT_HEIGHT: int = int(os.getenv("SCREENSHOT_VIEWPORT_HEIGHT", "1080"))


settings = Settings()