# 企业级 RAG Agent 项目设计文档

**日期**: 2026-09-01
**状态**: 待审阅(draft)
**定位**: 求职作品集项目 —— 展示企业级 RAG 问题域理解 + Agent 编排能力 + 全栈工程能力

---

## 1. 项目概述

一个"通用企业知识库问答 + 以技术难点为主线"的 RAG Agent 系统:

- 员工/用户上传企业内部文档(PDF、Markdown),自然语言提问,系统基于知识库回答,并给出**引用溯源**。
- 技术上以**企业级 RAG 难点**为主线:多格式解析、混合检索、重排、查询改写、增量更新、RAG 质量评估。
- 核心亮点是 **Agent 化编排(LangGraph)**:意图路由、工具调用(查询文档元数据/统计)、回答后自检补充检索。
- 单用户演示部署(Docker Compose 全家桶),但数据模型预留 `tenant_id`,体现多租户意识。

## 2. 目标与非目标

### 2.1 目标

1. 可一键运行(`docker compose up`),内置企业制度样例数据,开箱可演示。
2. 完整展示 RAG 链路:上传 → 解析 → 切片 → 向量化 → 混合检索 → 重排 → 生成 → 引用。
3. 展示 Agent 能力:多轮查询改写、意图路由、工具调用、回答自检(self-verify)。
4. 展示工程化:环境变量配置、Docker 编排、错误处理、测试、RAG 评估脚本。
5. 全栈:React SPA + FastAPI 后端,前后端分离,代码结构清晰可读。

### 2.2 非目标(明确不做)

- 完整多租户权限体系 / SSO / 细粒度 ACL(仅预留字段与说明)。
- 分布式部署、高可用、K8s。
- 复杂前端(仅两个页面:聊天、文档管理)。
- 企业级监控告警(仅结构化日志)。
- 实时音视频、移动端。

## 3. 技术栈

| 层 | 选型 |
|---|---|
| 后端框架 | Python 3.11 + FastAPI + Uvicorn |
| LLM 编排 | LangChain + LangGraph |
| ORM / 迁移 | SQLAlchemy 2 + Alembic |
| 文档解析 | pypdf / pdfplumber(PDF)、markdown-it + MarkdownHeaderTextSplitter(MD) |
| 向量库 | Milvus Standalone(主检索) |
| 元数据 / 历史 / 关键词 | PostgreSQL(FTS + jieba 分词) |
| Embedding / LLM | OpenAI 兼容 API,环境变量配置(默认国产 API 直连) |
| 重排 | 可选 Cross-Encoder(bge-reranker 本地或 API),默认关闭 |
| 前端 | React 18 + Vite + TypeScript + Ant Design 5 + React Query |
| 流式 | SSE(fetch + ReadableStream 解析,前端) |
| 部署 | Docker Compose(postgres、etcd、minio、milvus-standalone、api、web) |
| 测试 | pytest(后端)、Vitest + Testing Library(前端,少量)、RAGAS(离线评估) |

## 4. 系统架构

### 4.1 分层

```
┌─────────────────────────────────────────────┐
│  React SPA (Vite + AntD)                     │
│  聊天页 / 文档管理页 / Agent Trace 展示      │
└──────────────────┬──────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼──────────────────────────┐
│  FastAPI API 层                               │
│  routers: documents / conversations / chat / eval │
└──────────────────┬──────────────────────────┘
┌──────────────────▼──────────────────────────┐
│  服务层                                       │
│  IngestionService  RetrievalService  ChatService │
└──────────────────┬──────────────────────────┘
┌──────────────────▼──────────────────────────┐
│  Agent 编排层 (LangGraph)                    │
│  rewrite → router → retrieve/tool → generate → verify │
└──────────────────┬──────────────────────────┘
┌──────────────────▼──────────────────────────┐
│  数据层                                       │
│  PostgreSQL(元数据/历史/FTS)   Milvus(向量)  │
└─────────────────────────────────────────────┘
```

### 4.2 两条核心数据流

**写入流(离线/上传时)**:
上传文件 → 类型与大小校验 → 磁盘落盘 → 按类型解析(PDF 保留页码 / MD 保留标题层级)→ 清洗 → 切片(结构化切片,注入 heading/page/document_id 元数据)→ 计算 embedding → upsert 到 Milvus + 写入 PG `chunks` 表 → 更新文档状态。

**问答流(在线)**:
用户消息 → 查询改写(多轮上下文)→ 意图路由 → 混合检索(Milvus 向量 + PG FTS 关键词,RRF 融合)→ 可选重排 → 可选工具调用(元数据过滤/统计)→ LLM 生成(带引用标记 [1][2])→ 自检(引用是否支撑答案,不足则补检一次)→ 返回答案 + 引用 + agent trace。

## 5. 数据模型(PostgreSQL)

```sql
-- 文档元数据
CREATE TABLE documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL DEFAULT 'default',   -- 预留多租户
    title         TEXT NOT NULL,
    source_type   TEXT NOT NULL CHECK (source_type IN ('pdf','markdown')),
    status        TEXT NOT NULL DEFAULT 'processing'
                  CHECK (status IN ('processing','ready','failed')),
    checksum      TEXT NOT NULL,                      -- 去重/增量更新
    file_path     TEXT,
    page_count    INT,
    metadata      JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 切片(文本与元数据在 PG,向量在 Milvus)
CREATE TABLE chunks (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INT NOT NULL,
    content       TEXT NOT NULL,
    heading       TEXT,                                -- MD 标题层级 / PDF 章节
    page          INT,                                 -- PDF 页码
    metadata      JSONB NOT NULL DEFAULT '{}',
    checksum      TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 会话
CREATE TABLE conversations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     TEXT NOT NULL DEFAULT 'default',
    title         TEXT NOT NULL DEFAULT '新会话',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 消息
CREATE TABLE messages (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content       TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 引用溯源:答案 ↔ 切片
CREATE TABLE citations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id    UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_id      UUID NOT NULL,
    document_id   UUID NOT NULL,
    score         REAL,
    snippet       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**索引**: `documents(status, tenant_id)`、`chunks(document_id)`、`messages(conversation_id)`、`citations(message_id)`。

**关键词检索准备**: PG 侧对 `chunks.content` 用 jieba 分词后写入 `tsvector` 列(FTS,simple 配置),支撑中文关键词检索。

## 6. Milvus 设计

- Collection 名: `chunk_embeddings`
- 字段:
  - `id`(VARCHAR,= chunk 的 UUID,主键)
  - `document_id`(VARCHAR,标量过滤)
  - `tenant_id`(VARCHAR,标量过滤,预留)
  - `content`(VARCHAR,便于展示)
  - `embedding`(FLOAT_VECTOR,维度由环境变量 `EMBEDDING_DIM` 指定,默认 1024,适配 bge-m3)
- 索引: `HNSW`, metric `COSINE`, 参数 M=16, efConstruction=200
- 操作:
  - upsert(切片入库)
  - 按 `document_id` 过滤检索(指定文档/删除文档时清理)
  - 删除文档 → `delete(expr="document_id in [...]")` 后删 PG 记录(事务性说明见 §15)

## 7. 检索策略(企业级难点 1)

### 7.1 混合检索 + RRF 融合

- 向量检索: Milvus 取 top_k(默认 10)。
- 关键词检索: PG FTS(tsvector + jieba 分词)取 top_k(默认 10)。
- 融合: **RRF(Reciprocal Rank Fusion, k=60)**,合并两条结果带,输出融合分与来源标记。

### 7.2 查询改写

- 进入检索前,LLM 基于对话历史把用户问题改写成**独立、自包含**的查询(多轮场景:如"那审批要几天?" → "报销单审批需要几个工作日")。
- 改写失败或闲聊类问题可跳过改写,直接走路由。

### 7.3 重排(可选,默认关闭)

- 融合后的候选集(约 20 条)送入重排器,取 top 5。
- 环境变量 `RERANK_ENABLED=true` 时启用;模型默认 `BAAI/bge-reranker-base`(本地 CPU 可跑)或 API 重排,二选一,均走配置。

### 7.4 元数据过滤

- 检索请求可携带过滤器: `document_ids`、`source_type`、`date_range`(metadata.created_at)、`tenant_id`。
- 过滤器来源:Agent 工具调用结果或路由判断,写入 Milvus expr 与 PG 查询。

### 7.5 空结果降级

- 向量检索失败(如 Milvus 不可用)→ 降级为纯 FTS 检索并记录警告日志(可用性展示点)。
- 两路都空 → 明确告知"知识库中未找到相关信息",不编造。

## 8. Agent 编排(核心亮点,LangGraph)

### 8.1 图结构

```
[rewrite] ──▶ [router] ──▶ [tool_node](可多轮)
                    │            │
                    ├──▶ [retrieve] ──▶ [generate] ──▶ [verify]
                    │                                 ▲       │
                    └──▶ [generate](闲聊/拒答)        └─补检─▶ [retrieve](≤1 次)
```

### 8.2 状态(State)

```python
class AgentState(TypedDict):
    query: str
    rewritten_query: str
    history: list[dict]          # 会话历史
    retrieved: list[Chunk]
    tool_calls: list[str]        # trace 用
    answer: str
    citations: list[Citation]
    verify_count: int
    trace: list[TraceStep]       # 每个节点记录 name/input_summary/output_summary/duration_ms
```

### 8.3 节点说明

1. **rewrite**: 多轮查询改写(LLM,提示词限定简短,失败回退原文)。
2. **router**: 轻量分类(LLM 或规则):
   - `tool` — 需要查元数据/统计(如"库里一共有几份制度?"、"2024 年的文档有哪些?")
   - `retrieve` — 需要知识库检索(默认)
   - `direct` — 闲聊/无关问题(直接礼貌回复,不检索)
3. **tool_node**: 工具循环(LangChain ToolNode + @tool),工具返回结构化结果,可带出过滤器:
   - `list_documents(limit, status)` — 列出文档
   - `count_documents(source_type, status)` — 统计
   - `search_documents(query, filters)` — 带元数据过滤的检索(供多步查询)
   - `get_document(title)` — 取整篇文档内容(供"总结这篇文档"类问题)
4. **retrieve**: 混合检索 + 可选重排(§7),结果为 Chunk 列表。
5. **generate**: 组装 prompt(系统提示 + 检索上下文 + 引用编号),要求答案引用 [1][2],并输出结构化引用列表。
6. **verify**: 自检——LLM 判断答案是否被引用充分支撑;若不足且 `verify_count < 1`,回 `retrieve` 补充检索后重新生成。

### 8.4 引用编号约定

- 上下文按序编号 [1..n],生成时引用编号;后端把编号映射到 `citations` 表与前端引用卡片。

## 9. API 设计

统一前缀 `/api/v1`,错误使用 FastAPI 标准 `{detail: ...}`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/documents/upload` | multipart 上传(支持多文件),返回各文件任务状态 |
| GET | `/documents` | 分页 + status/source_type 过滤 |
| GET | `/documents/{id}` | 文档详情(含 metadata、切片数) |
| DELETE | `/documents/{id}` | 删除文档 + 级联清理向量与切片 |
| GET | `/documents/{id}/chunks` | 查看切片(调试/展示) |
| POST | `/conversations` | 新建会话 |
| GET | `/conversations` | 会话列表 |
| GET | `/conversations/{id}/messages` | 消息历史(含引用) |
| POST | `/chat` | 问答,SSE 流式返回事件:`agent_trace` / `token` / `citations` / `done` / `error` |
| POST | `/eval/run` | 触发 RAGAS 评估(异步,返回 run_id) |
| GET | `/eval/runs/{run_id}` | 评估结果 |
| GET | `/health` | 健康检查(含各依赖状态) |

**SSE 事件格式**:
```json
event: agent_trace
data: {"step":"retrieve","summary":"检索到 5 个相关切片","duration_ms":180}

event: token
data: {"text":"根据知识库"}

event: citations
data: {"citations":[{"id":"...","document_title":"报销制度","snippet":"...","score":0.82}]}

event: done
data: {"message_id":"..."}
```

## 10. 文档处理管道(Ingestion)

1. **校验**: 扩展名(仅 `.pdf` / `.md` / `.markdown`)、大小上限 20MB。
2. **去重**: 计算文件 SHA-256;与已有 `documents.checksum` 相同 → 跳过(幂等);内容变化 → 删除旧切片与向量后重建。
3. **解析**:
   - PDF: pdfplumber 提取文本 + 页码;每页附加 `page` 元数据。
   - MD: markdown-it 解析,保留标题层级(用于结构化切片)。
4. **切片**:
   - MD: MarkdownHeaderTextSplitter(标题层级)→ 每个切片带 `heading` 链。
   - PDF: RecursiveCharacterTextSplitter(chunk_size=500, overlap=80, 中文分隔符优先)。
5. **向量化与入库**: 逐切片 embedding → Milvus upsert;同批写 PG `chunks`;文档状态置 `ready`。
6. **失败隔离**: 单文件解析/向量化失败 → 该文档 `status=failed` 并记录错误,不影响批次内其他文件。

## 11. 前端设计

### 11.1 页面

- **聊天页**(主): 左侧会话列表 + 新建会话;中部消息流(气泡、markdown 渲染、引用卡片 [1][2] 可点击);右侧 Agent Trace 折叠面板(展示 rewrite → route → retrieve → generate 步骤与耗时)。
- **文档管理页**: 拖拽上传区、文档表格(标题/类型/状态/切片数/时间/操作)、上传进度与失败提示。

### 11.2 关键组件

```
src/
├─ api/client.ts            # fetch 封装 + SSE 解析(fetch ReadableStream)
├─ hooks/useChatStream.ts   # 聊天流式 hook
├─ pages/ChatPage.tsx
├─ pages/DocumentsPage.tsx
├─ components/
│  ├─ MessageItem.tsx       # 气泡 + 引用
│  ├─ CitationCard.tsx
│  ├─ TracePanel.tsx        # agent 步骤时间线
│  ├─ UploadDropzone.tsx
│  └─ DocumentTable.tsx
└─ App.tsx                  # 布局 + 路由(react-router)
```

### 11.3 状态管理

- 服务端状态: React Query;客户端 UI 状态: 轻量 useState + context,不引入 Redux。

## 12. RAG 质量评估(亮点)

- `scripts/eval_ragas.py`: 读取 `eval_dataset.json`(问题 + 参考答案 + 关联文档),跑 RAGAS 指标 **faithfulness / answer_relevancy / context_precision**,输出 JSON + 可读报告。
- 内置 10–15 条评估问题,覆盖:单文档事实查询、跨文档多跳、无答案拒答、统计类(工具)。
- 可选通过 API `/eval/run` 触发,结果入库 `eval_runs`(表结构见实现计划阶段补充,可先用 JSON 落盘简化)。

## 13. 配置与部署

### 13.1 环境变量(`.env.example`,全部占位)

```bash
# LLM(OpenAI 兼容,可填 DeepSeek / 通义 / OpenAI)
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_MODEL=

# Embedding(OpenAI 兼容)
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024

# 重排(可选)
RERANK_ENABLED=false
RERANK_MODEL=BAAI/bge-reranker-base

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=rag
POSTGRES_PASSWORD=
POSTGRES_DB=rag

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530

# 检索参数
RETRIEVE_TOP_K=10
CHUNK_SIZE=500
CHUNK_OVERLAP=80
```

### 13.2 Docker Compose 服务

```yaml
services:
  etcd, minio, milvus-standalone   # Milvus 依赖
  postgres                          # 元数据/FTS
  api                               # backend(Dockerfile,uvicorn)
  web                               # frontend(Dockerfile,构建后 nginx 托管 + 反代 /api)
```

- 本地开发: `docker compose up etcd minio milvus-standalone postgres`,后端 `uvicorn --reload`,前端 `vite dev`(代理 /api)。
- 一键演示: `docker compose up --build`。

## 14. 测试策略

- **后端 pytest**:
  - 单元: 切片器(MD 层级/PDF 页码)、RRF 融合公式、查询改写(mock LLM)、工具函数(mock DB)。
  - 集成: 上传 → 解析 → 入库(mock embedding/Milvus client)、chat 全流程(mock LLM 固定输出)。
  - 测试数据: `tests/fixtures/` 内置小 MD/PDF。
- **前端 Vitest**: 引用渲染、SSE 解析、上传表单(少量)。
- **RAGAS**: 离线脚本,不阻塞 CI(仅文档记录)。
- **端到端**: 人工演示脚本(README),不引入 Playwright(控制范围)。

## 15. 错误处理与健壮性

- 上传: 类型/大小校验失败返回 400 + 可读中文提示。
- 解析失败: 文档级隔离,`status=failed` + 错误信息可查。
- LLM 调用: 超时(60s)+ 重试 1 次;连续失败返回友好错误,并附 trace 中失败步骤。
- Milvus 不可用: 降级纯 FTS(§7.5),健康检查暴露状态。
- 删除文档: 先删 Milvus 向量,再删 PG(记录补偿日志;本项目单机可接受最终一致)。
- 流式中断: 前端断线提示,已生成消息落库;后端生成完成前崩溃 → 该消息不落库,用户可重发。

## 16. 目录结构

```
F:\Agent\RAG
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ config.py                    # pydantic-settings 读环境变量
│  │  ├─ api/                         # routers
│  │  ├─ core/                        # db、milvus、llm/embedding client、logging
│  │  ├─ models/                      # SQLAlchemy ORM
│  │  ├─ schemas/                     # Pydantic
│  │  ├─ services/                    # ingestion、retrieval、rerank、chat
│  │  └─ agent/                       # graph、nodes、tools、state、prompts
│  ├─ tests/ + fixtures/
│  ├─ scripts/                        # eval_ragas.py、seed_sample.py
│  ├─ alembic/
│  ├─ Dockerfile
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/                            # 见 §11.2
│  ├─ Dockerfile
│  └─ package.json
├─ sample_data/                       # 内置演示文档(5–8 份 MD + 2–3 份 PDF)
├─ docs/superpowers/specs/
├─ eval_dataset.json
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## 17. 实现里程碑(MVP 切分)

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| M1 骨架 | docker-compose、PG schema + Alembic、Milvus collection、health | `docker compose up` 后 health 全绿 |
| M2 上传管道 | 解析/切片/embedding/入库 | 上传样例 → 文档 ready、Milvus 有向量 |
| M3 检索问答 | 混合检索 + RRF + 改写 + 引用 | API 问答带引用可演示 |
| M4 Agent | LangGraph 路由/工具/自检 + trace | 统计类、多跳类问题正确回答 |
| M5 前端 | 聊天页 + 文档页 + 流式 + trace 面板 | 浏览器全流程可演示 |
| M6 打磨 | RAGAS 评估、样例数据、README 演示脚本 | 按 README 能跑通演示与评估 |

## 18. 演示脚本(README 中的 Demo 流程)

1. `docker compose up --build` 一键启动。
2. 文档页拖拽上传 `sample_data/`(或直接 seed 脚本导入)。
3. 依次提问演示:
   - 事实查询: "员工报销差旅费需要哪些材料?"
   - 多轮改写: "那审批流程呢?"(自动改写为 "差旅费报销的审批流程是什么")
   - 工具/统计: "知识库里一共有几份制度文档?"
   - 跨文档多跳: "新员工入职当天要签哪些文件?和试用期考核有什么关系?"
   - 拒答: "今天天气怎么样?"
4. 打开 Trace 面板展示 agent 步骤;点击引用卡片回看原文。
5. `python scripts/eval_ragas.py` 展示评估报告。

## 19. 风险与开放问题

- **中文关键词检索**: 倾向 PG FTS + jieba 预分词;若效果不佳可换 rank_bm25(语料小,Python 侧可跑)。实现阶段以 M3 实测为准。
- **embedding 维度**: Milvus collection 维度在首次建集合时按 `EMBEDDING_DIM` 创建,与所选模型一致(1024=bge-m3,1536=OpenAI text-embedding-3-small)。
- **bge-m3 本地 vs API**: 默认 OpenAI 兼容 embedding API(直连国产);如用户偏好本地,增加可选 Ollama 配置(非本期必需)。
- **流式 + agent trace 的编排**: SSE 事件顺序约定见 §9,前端按事件类型增量渲染。

---

*以上为待确认设计。确认后进入 writing-plans 生成详细实现计划。*