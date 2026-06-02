from fastapi import FastAPI
from app.routers import docs
from app.config import settings

app = FastAPI(
    title="OM Docs Service",
    description="运维文档生成服务 — 基于 Claude AI 分析代码，自动生成全套运维文档（DOCX格式）",
    version="1.0.0",
)

app.include_router(docs.router, prefix="/api/docs", tags=["文档生成"])


@app.get("/")
def root():
    return {"service": "om-docs-service", "version": "1.0.0", "status": "running"}