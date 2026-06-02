  # Code-Copilot 框架已部署
  本项目使用渐进式 Spec 驱动开发框架。
  - 框架目录：.code-copilot/
  - 规则文件：.code-copilot/rules/ (alwaysApply: true 的文件自动加载)
  - 变更管理：.code-copilot/changes/
  - 知识库：.code-copilot/knowledge/

  ## 同步规则
  本项目中的 .code-copilot/ 是从源仓库 D:/coding/code-copilot 复制部署的副本。
  任何对 code-copilot 框架本身的优化变更（包括 rules、agents、knowledge 模板、changes/templates 等框架级文件），
  必须同步回源仓库 D:/coding/code-copilot，确保框架改进在所有项目中生效。
  项目级业务规则和变更内容（如 .code-copilot/rules/project-context.md、.code-copilot/changes/ 下的具体变更）不需要同步。

  启动时请执行：
  1. 读取 .code-copilot/rules/ 下所有规则
  2. 检查 .code-copilot/changes/ 下进行中的变更
  3. 读取 progress.md 的续做断点
  4. 报告当前状态
  EOF

  echo "code-copilot 已部署到 $TARGET"

---

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

om-docs-service 是一个 FastAPI 微服务，为任意 IT 系统自动生成全套运维文档（7 个 DOCX 文件）。工作流程：用户上传源码 → Claude API 并行分析后端/前端/部署代码 → Claude API 生成 7 个结构化 Markdown 文档 → Playwright 截取生产环境 UI → Markdown 转换为 Word DOCX。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium

# 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 配置环境变量（复制模板后修改）
cp .env.example .env
```

当前项目没有测试套件。

## 架构

### 6 步异步 Pipeline（核心流程）

`app/services/pipeline.py` 中的 `run_pipeline()` 通过 FastAPI BackgroundTasks 异步执行：

1. **收集信息** — API 层处理文件上传 + 项目元数据
2. **Claude API 代码分析** — `claude_analyzer.py` 的 `analyze_all()` 并行调用 3 次 Claude API（后端/前端/部署），输出结构化 JSON
3. **生成 7 个 Markdown 文档** — `doc_generator.py` 单次 Claude API 调用，用 `---DOC_SEPARATOR---` 分隔符拆分响应
4. **Playwright 截图** — `screenshot_runner.py` 对前端路由截取全页 PNG，支持 Kuboard 看板（9 页）和 storageState 认证会话
5. **嵌入/校验截图引用** — 确保 Markdown 中的 `![...](images/xxx.png)` 与实际截图文件对应
6. **转换为 DOCX** — `md2docx_converter.py` 解析 Markdown 生成带中文字体样式排版的 Word 文档

### 任务状态机

状态流转：`PENDING → ANALYZING → GENERATING_MD → RUNNING_SCREENSHOTS → EMBEDDING_IMAGES → CONVERTING_DOCX → COMPLETED`（失败时转入 `FAILED`）

每个任务有 UUID 目录：`tasks/{task_id}/` 下含 `upload/`、`output/`、`output/images/`、`auth/`、`status.json`、`analysis.json`

### 关键模块

| 模块 | 职责 |
|------|------|
| `app/routers/docs.py` | 4 个 API 端点：POST /generate, GET /status/{id}, GET /download/{id}/{file}, GET /download/{id}/all |
| `app/schemas.py` | Pydantic 数据模型：TaskStatusEnum(8 种状态)、ProjectInfo 等 |
| `app/config.py` | Settings 单例，从 .env 加载配置（API key、模型、端口、截图视口等） |
| `app/prompts/` | 4 个提示模板文件，驱动 Claude 分析和文档生成逻辑 |
| `app/utils/file_manager.py` | 任务目录创建、文件上传保存、旧任务清理（>24h） |
| `app/utils/task_manager.py` | 基于 JSON 文件的任务状态 CRUD |

### Prompt 模板设计要点

- 后端分析覆盖 10 维度（controllers、entities、mappers、config 等）
- 前端分析覆盖 7 维度（routes、menus、page components 等）
- 部署分析覆盖 5 维度（helm chart、dockerfile、nginx config 等）
- 文档生成严格规则：忽略代码注释内容、不写占位符、内容自适应项目实际情况
- Claude 输入截断上限：150K 字符

### DOCX 转换器支持的 Markdown 元素

标题、粗体/斜体/代码、代码块、表格、图片（自动计算尺寸）、有序/无序列表、引用块，使用中文字体排版。

## 编码规范（来自 .code-copilot/rules）

- 类名大驼峰，方法名小驼峰动词开头，常量全大写下划线分隔
- 业务异常用自定义 BizException 携错误码，禁止空 catch
- Controller 入口打 INFO 含关键参数，异常打 ERROR 含完整堆栈
- 写接口必须幂等，涉及并发必须说明同步策略

## 安全红线

- 禁止硬编码密钥/AK/SK/数据库密码
- 禁止日志中打印手机号、身份证、银行卡等敏感信息
- 涉及资金变更必须在 spec 中标注并人工审查
- 涉及权限变更必须显式校验操作人权限
