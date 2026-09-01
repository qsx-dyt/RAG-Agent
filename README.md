# Enterprise RAG Agent

企业级 RAG(检索增强生成)Agent 系统:多格式文档解析、混合检索、LangGraph Agent 编排、引用溯源与流式问答。

## 技术亮点

- **混合检索**:Milvus 向量检索 + PostgreSQL FTS(jieba 分词)双路召回,RRF 融合,支持元数据过滤与 Milvus 故障降级。
- **Agent 编排**:LangGraph 状态图(rewrite → router → retrieve/tool → generate → verify),多轮查询改写、意图路由、工具调用、回答自检补检。
- **引用溯源**:回答带 [1][2] 编号引用,前端可点击回看原文片段。
- **RAG 评估**:RAGAS 脚本量化 faithfulness / answer_relevancy / context_precision。
- **全栈工程**:FastAPI + React(Ant Design)+ Docker Compose 一键启动,环境变量配置。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + FastAPI + LangChain/LangGraph + SQLAlchemy + Alembic |
| 检索 | Milvus(向量)+ PostgreSQL(FTS/jieba)|
| 前端 | React 18 + Vite + TypeScript + Ant Design 5 + React Query |
| 部署 | Docker Compose(postgres / etcd / minio / milvus / api / web)|
| 评估 | RAGAS |

## 快速开始

```bash
# 1. 配置环境变量(LLM/Embedding 密钥由你自己填写)
cp .env.example .env
# 编辑 .env,填入 OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL 与 Embedding 配置

# 2. 一键启动全部服务
docker compose up --build

# 3. 导入内置样例文档(6 份 MD + 2 份 PDF)
docker compose exec api python -m scripts.seed_sample

# 4. 打开前端
# http://localhost:5173
```

本地开发(不打包前端):

```bash
docker compose up etcd minio milvus-standalone postgres
cd backend && uvicorn app.main:app --reload      # http://localhost:8000
cd frontend && npm install && npm run dev        # http://localhost:5173(代理 /api)
```

## 演示提问

导入样例数据后,可以依次尝试:

1. **事实查询**:员工报销差旅费需要哪些材料?
2. **多轮改写**:先问"报销差旅费需要哪些材料?",再问"那审批流程呢?"(自动改写为自包含查询)
3. **工具/统计**:知识库里一共有几份制度文档?
4. **跨文档多跳**:新员工入职当天要签哪些文件?和试用期考核有什么关系?
5. **拒答**:今天天气怎么样?

点击消息右侧的引用卡片可查看原文;右侧 Trace 面板展示 agent 每一步(rewrite / router / retrieve / generate)与耗时。

## 环境变量

| 变量 | 说明 | 必填 |
|---|---|---|
| `OPENAI_API_KEY` | LLM API Key([OI] 兼容,可填 DeepSeek / 通义 / [OI])| 是 |
| `OPENAI_BASE_URL` | LLM Base URL | 是 |
| `LLM_MODEL` | 对话模型名 | 是 |
| `EMBEDDING_API_KEY` | Embedding API Key | 是 |
| `EMBEDDING_BASE_URL` | Embedding Base URL | 是 |
| `EMBEDDING_MODEL` | Embedding 模型(默认 bge-m3) | 否 |
| `EMBEDDING_DIM` | 向量维度,须与模型一致(bge-m3=1024) | 否 |
| `RERANK_ENABLED` | 是否启用重排(默认 false) | 否 |
| `RERANK_MODEL` | 重排模型(默认 BAAI/bge-reranker-base) | 否 |
| `POSTGRES_*` / `MILVUS_*` | 数据库连接(容器内默认即可) | 否 |
| `RETRIEVE_TOP_K` / `CHUNK_SIZE` / `CHUNK_OVERLAP` | 检索与切片参数 | 否 |

## RAG 评估

```bash
docker compose exec api python -m scripts.eval_ragas
```

输出 `eval_report.json`(faithfulness / answer_relevancy / context_precision 平均分)。数据集见 `eval_dataset.json`(12 条,覆盖单文档事实 / 跨文档多跳 / 统计工具 / 拒答)。

## 目录结构

```
backend/           FastAPI 后端(app: api/core/models/schemas/services/agent)
frontend/          React 前端(api/hooks/pages/components)
sample_data/       内置演示文档(6 MD + 2 PDF)
eval_dataset.json  RAGAS 评估数据集
docker-compose.yml 一键编排
.env.example       环境变量模板(全部占位)
```

## 常见问题

- **Embedding 维度不匹配**:首次启动时 Milvus 按 `EMBEDDING_DIM` 建集合,更换模型后需删掉集合重建(或清空 volume)。
- **Milvus 首次启动慢**:standalone 模式首次拉起 etcd/minio/milvus 需要 1-2 分钟,`/api/v1/health` 就绪后再上传文档。
- **中文 PDF 乱码**:样例 PDF 由 reportlab 生成,需系统含中文字体(Windows 自带微软雅黑;Linux 容器请安装 wqy 字体)。
- **重排默认关闭**:`FlagEmbedding` 为可选依赖,启用 `RERANK_ENABLED=true` 时需自行安装。

## 帮助文档

- 快速上手(小白版): `docs/PROJECT_GUIDE_PART1_QUICKSTART.md`
- 面试项目解析: `docs/PROJECT_GUIDE_PART2_INTERVIEW.md`

## 设计文档

- 设计: `docs/superpowers/specs/2026-09-01-enterprise-rag-agent-design.md`
- 实现计划: `docs/superpowers/plans/2026-09-01-enterprise-rag-agent.md`
