# 项目帮助文档(一):项目深度解析 —— 技术版快速上手

> 本文面向已经能跑通 Demo、想真正理解"这个项目每一块在干嘛、数据怎么流动、代码怎么组织"的读者。
> 既有从零启动的完整步骤,也有逐模块的技术拆解。面试向的问答解析见 `docs/PROJECT_GUIDE_PART2_INTERVIEW.md`。

---

## 1. 这个项目解决什么问题?

**一句话**:把多份企业文档(PDF / Markdown)变成"可检索、可溯源、多轮对话"的知识库问答系统。

传统搜索是"关键词匹配";本项目是 **RAG(检索增强生成)**:先用**向量语义**+**关键词**双路召回相关片段,再让大模型基于这些片段生成带索引引用的回答,最后做一遍**自检**保证回答有依据。

核心诉求不是"能做出来",而是把企业场景里那些真问题做扎实:

- **多格式文档**:PDF 要按页拆,Markdown 要按标题层级拆。
- **中文检索**:PostgreSQL 的默认英文分词器对中文完全失效。
- **多轮对话**:"那审批要几天?"这种指代句必须结合历史改写。
- **回答可信**:每条回答必须带 [1][2] 编号引用,并且能自检、补检。
- **鲁棒性**:免费 API 会限流(429)、向量库可能挂,系统要能优雅降级不崩溃。

---

## 2. 总体架构与技术栈

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 React SPA (Ant Design)                                  │
│   聊天页:会话管理 + 消息流 + 引用卡片 + Agent Trace 面板       │
│   文档管理页:拖拽上传 + 状态表格                               │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTP + SSE(流式)
┌───────────────────────▼─────────────────────────────────────┐
│ FastAPI (/api/v1)                                            │
│   /health │ /documents/{upload,list,chunks,delete}           │
│   /conversations/{list,rename,delete,messages}  │ /chat      │
└───┬───────────────────────────┬─────────────────────────────┘
    │                           │
    ▼                           ▼
┌────────────────┐     ┌──────────────────────────────────────┐
│ PostgreSQL 16  │     │ LangGraph Agent 状态机                │
│  documents     │     │  rewrite → router → retrieve/tool     │
│  chunks(+FTS)  │     │          → generate → verify          │
│  conversations │     │  (查改写 / 意图路由 / 混合检索 / 生成) │
│  messages      │     └───────────┬──────────────────────────┘
│  citations     │                 │
└────────────────┘                 ▼
                    ┌──────────────────────────────────────┐
                    │ Milvus 2.4 (向量库) + LLM/Embedding API │
                    │  chunk_embeddings 集合, HNSW+COSINE      │
                    └──────────────────────────────────────┘
```

## 技术清单

| 层次 | 技术 | 作用 |
|---|---|---|
| 前端 | React 18 + Vite + Ant Design 5 | 页面与交互 |
| 状态 | TanStack React Query | 服务端数据缓存(会话列表/文档表) |
| 流式 | Fetch API + ReadableStream | 前端自行解析 SSE |
| 后端 | FastAPI + Uvicorn | REST + SSE 接口 |
| Agent | LangGraph 状态图 | 查询改写/路由/自检编排 |
| 检索 | Milvus(向量) + PG FTS(jieba) + RRF | 双路召回 + 融合 |
| 存储 | PostgreSQL 16(SQLAlchemy) | 元数据 / 正文 / 会话 / 引用 |
| LLM | langchain-openai(ChatOpenAI 等) | LLM 调用 + Embedding |
| 解析 | pdfplumber + MarkdownHeaderTextSplitter | 文档解析切分 |
| 部署 | Docker Compose(6 服务 + 健康检查) | 一键启动 |

---

## 3. 五分钟跑起来(已完成/追赶用)

### 第 1 步:配置 `.env`

```bash
# 根目录
cp .env.example .env     # PowerShell: Copy-Item .env.example .env
```

最少填四组(本项目用 chatanywhere):

```bash
# ---- LLM ----
OPENAI_API_KEY=你的Key
OPENAI_BASE_URL=https://api.chatanywhere.tech
LLM_MODEL=gpt-4o-mini

# ---- Embedding ----
EMBEDDING_API_KEY=你的Key
EMBEDDING_BASE_URL=https://api.chatanywhere.tech
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIM=1536     # !! 必须与模型输出维度一致
```

> ⚠️ `EMBEDDING_DIM` 决定 Milvus 集合的向量维度,**启动时建集合后改不再生效**。换模型且维度不同时,需要删集合(或清空卷)重建。`text-embedding-ada-002`=1536,`bge-m3`=1024。

### 第 2 步:一键启动

```bash
docker compose up --build
```

启动 6 个容器。compose 里用**健康检查 + depends_on 条件等待**解决启动竞态:

- `milvus-standalone` 等 `etcd`、`minio` 健康后才起;
- `api` 等 `postgres`、`milvus-standalone` 健康后才起;
- `web` 等 `api` 健康后才起。

所以不需要手动等数据库,直接 `docker compose up` 即可。

### 第 3 步:导入 8 份演示文档

```bash
docker compose exec api python -m scripts.seed_sample
```

`sample_data/` 已自动挂载进 api 容器(`./sample_data:/sample_data`)。看到每行 `xxx: ready` 即成功(6 MD + 2 PDF)。

### 第 4 步:打开网页

浏览器访问 **http://localhost:5173**

测试问题:`报销差旅费需要哪些材料?` 或 `知识库里有几份文档?`。

注意:**免费 API 有每日 100 次配额**,超限后 LLM/Embedding 会返回 429,系统会自动降级(见 §7.4),第二天 00:00 恢复。

### 第 5 步:停止 / 清理

```bash
docker compose down        # 保留数据卷
docker compose down -v     # 彻底清空数据
```

---

## 4. 系统数据流全景(背下来)

理解整条链路,建议按"写入"和"问答"两条线看。

### 4.1 写入链路(ingestion):文档 → 切片 → 双写

```
上传 / seed_sample
   │
   ▼
[ingestion.ingest_bytes]             backend/app/services/ingestion.py
   │ 1. sha256 checksum 去重(同内容跳过)
   │ 2. 建 Document 记录(status=processing),文件落盘
   ▼
[parse_and_split]                    services/splitters.py
   │ PDF: pdfplumber 逐页提取文本 → RecursiveCharacterTextSplitter 按 500 字/80 重叠切
   │ MD : MarkdownHeaderTextSplitter 按 #/##/### 切(保留 heading)
   ▼
对每个切片:
   │ 1. uuid 生成 chunk_id
   │ 2. embed_texts([content]) → 向量(批量 16)
   │ 3. tokenize_cn(content) → jieba 分词得到 search_text
   ▼
双写 = 向量写 Milvus + 正文写 PG:
   ├─ Milvus.upsert_chunks(rows)     # {id,document_id,tenant_id,content,embedding}
   └─ PG: Chunk 表                    # content/heading/page/search_text
   ▼
Document.status → ready(失败则 failed + error 记录)
```

**两个数据库各自存什么?**

- **Milvus**(`chunk_embeddings` 集合):`id(chunk_id)`、`document_id`、`tenant_id`、`content`、`embedding`(1536 维 HNSW+COSINE)。只负责向量近似检索,不存正文以外的东西。
- **PostgreSQL**:
  - `documents` 元数据(title/source_type/status/checksum/metadata JSON);
  - `chunks` 正文切片(content/heading/page/**search_text** 分词列);
  - `conversations` / `messages` / `citations` 会话链路(见 §4.3);
  - 对 `search_text` 建 `to_tsvector('simple')` 表达式索引,供 FTS 用(见 §5.2)。

### 4.2 问答链路(Agent):LangGraph 状态机

```
用户输入 + conversation_id
   │
   ▼
[chat API /api/v1/chat]                 api/chat.py
   │ ① 若没会话→自动新建;存 user message
   │ ② StreamingResponse 发 SSE: start → agent_trace → token → citations → done
   ▼
[run_agent]  LangGraph 编译的状态图    agent/graph.py
   │
   ├─ rewrite      查询改写(结合 history,把指代句改写成自包含查询;LLM 失败则原样)
   ├─ router       意图路由 → retrieve / tool / direct(失败默认 retrieve)
   ├─ retrieve     混合检索 hybrid_search(query, top_k, filters) + 可选 rerank
   ├─ tools        ToolNode(仅 router 判定为 tool 时):list/count/search/get_document
   │               工具结果写回,然后继续进 retrieve
   ├─ generate     基于检索片段让 LLM 生成带 [n] 引用的回答
   └─ verify       自检:判断引用是否充分;不足则置 verify_retrieve 再补检一次(≤1 次)
   │
   ▼
结果写回:assistant message + citations(落库)→ SSE 结束
```

**状态对象 AgentState**(`agent/state.py`)贯穿全图:

```
query / rewritten_query / history / retrieved / tool_calls
answer / citations / verify_count / verify_retrieve / trace / route
```

**路由条件** `_route_after_router`:根据 `route` 字段走 `retrieve`(默认)、`tool`、或 `direct`(闲聊直接生成)。`_route_after_verify`:若 `verify_retrieve` 为真 → 回到 `retrieve` 再生成一次;否则到 `END`。

### 4.3 会话与引用持久化

- 每个对话一个 `Conversation`,点发送时若无 id 自动创建,标题取首条消息前 30 字。
- 每次一问一答分别落 `messages` 两行(user/assistant);assistant 的回答相关 `citations` 落 `citations` 表(snippet 截取前 500 字)。
- 前端的会话列表、历史消息、重命名、删除全部走后端 REST:`POST/GET/PATCH/DELETE /conversations` + `GET /conversations/{id}/messages`。
- 「重看历史」就是 `GET /messages`,引用同样从库里读出来还原(见 fix:历史引用对齐)。

---

## 5. 核心模块技术拆解

### 5.1 混合检索:`services/retrieval.py`

`hybrid_search` 是检索入口,内部三件事:

```
vector_search(query, top_k*2, filters)   Milvus 向量召回(embed 查询→HNSW 近邻)
keyword_search(query, top_k*2, filters)  PG FTS 关键词召回
rrf_fuse(vec, kw)[:top_k]                倒数排名融合,合并同 chunk_id
```

- **vector_search**:对 query 做一次 embedding,`milvus.search()` 取 top_k*2(留融合余量);支持 `document_ids` 过滤(转成 `document_id in [...]` 表达式)。向量检索抛异常时 `hybrid_search` 捕获并**降级为纯关键词**(§7.3)。
- **keyword_search**:关键在中文字排序下 PG 默认分词器失效,本项目用 jieba。
  - 入库时 `search_text = tokenize_cn(content)`(= `" ".join(jieba.cut(text))`,空格连接)。
  - 查询时 `tsq = " | ".join('"%s"' % w for w in jieba.cut(query))`,即 **OR 语义**:任一中文词命中即召回,`ts_rank(to_tsvector('simple', search_text), to_tsquery('simple', tsq))` 按命中度排序。
  - 好处:长问句("报销差旅费需要准备哪些材料")拆成多个词 OR 召回,覆盖更全;和向量的"整句语义"互补。
  - sqlite 测试环境用逐词 LIKE OR + 命中数降序近似(见 `_is_sqlite`)。
- **rrf_fuse**:`score += 1/(k + rank)`(k=60),对两个检索器结果按排名加权求和,天然消除"余弦相似度 vs ts_rank"两种分数尺度的差异。同 chunk_id 合并,补全缺失的 content/document_id(sources 标记 vector/keyword)。

### 5.2 PostgreSQL FTS 中文方案

```
chunks 表加 search_text 列(切片被 jieba 分词后以空格连接)
       ↓
PG 用 to_tsvector('simple', search_text) 做索引与匹配
       ↓
查询同 jieba 分词 → to_tsquery('simple', tsq)  OR 语义
       ↓
ts_rank 排序
```

> 为什么不用 `zhparser/pg_jieba` 扩展?依赖较重且要装扩展。用 `simple` 配置 + 应用侧 jieba 预分词,零扩展、可移植、可插 SQLite 测试。

### 5.3 Agent 编排:`agent/`

四个 LLM prompt(`prompts.py`)分别负责一个动作:

| 节点 | 输入 | 输出 | 失败兜底 |
|---|---|---|---|
| rewrite | query+history | 自包含改写查询 | 原样 query |
| router | 改写后 query | tool/retrieve/direct 之一 | 默认 retrieve |
| generate | context 片段+query | 带 [n] 引用的回答 | 输出【生成回答失败】+原文片段 |
| verify | answer+context | yes / no | 视为 yes(避免误补检) |

工具 `tools.py` 用 langchain `@tool` 暴露四个能力讲给 LLM(经 `ToolNode`):`list_documents` / `count_documents` / `search_documents`(带过滤的混合检索)/ `get_document`(整篇取回)。

**verify 自检逻辑**:`verify_count>=1` 或没有检索片段则跳过;否则让 LLM 判"引用是否充分",不充分就 `verify_retrieve=True; verify_count+=1` 回 `retrieve` 补检一次(on top)。

### 5.4 LLM 与 Embedding 客户端:`core/llm.py`

- `get_llm()`:`ChatOpenAI(model, api_key, base_url, temperature=0.2, timeout=60, max_retries=1)`。所有节点共用同一个 OpenAI 兼容客户端,所以换模型/换厂商只要改 `.env`。
- `get_embeddings()`:`OpenAIEmbeddings(model, api_key, base_url)`。
- `embed_texts`:批量(batch 16)调 embedding,给 ingestion 和 vector_search 复用。
- key 为空时填 `"EMPTY"`(避免 langchain 抛错),配合 OpenAI 兼容网关。

### 5.5 文档解析与切片:`services/parsers.py` + `splitters.py`

- **PDF**:`pdfplumber` 逐页 `extract_text()`,记录 page 号。
- **Markdown**:`MarkdownHeaderTextSplitter` 按 `#/##/###` 分节,保留 heading 作为结构化定位。
- **统一切分**:PDF 文本进 `RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)`,分隔符优先换行/句号/分号/逗号,尽量在语义边界切断。MD 用标题切,天然语义完整。
- 配置项:`chunk_size` / `chunk_overlap` 在 `.env` 可调。

### 5.6 可选重排:`services/rerank.py`

`rerank_enabled=true` 时(默认 false),`rerank()` 用 `FlagEmbedding` 的 cross-encoder 对召回片段按 query-片段的相关性重排一遍再截取 top_k;未装依赖/出错时静默跳过(降级为不重排),核心链路不受影响。

### 5.7 SSE 流式:`api/chat.py` + 前端 `hooks/useChatStream.ts`

- 后端:`StreamingResponse(media_type="text/event-stream")`,`_emit` 生成 `event: X\ndata: {...}\n\n` 事件:
  - `start`:回传 conversation_id
  - `agent_trace`:每步 trace(step/summary/duration_ms)
  - `token`:回答按 8 字符切块流式返回
  - `citations`:最终引用列表
  - `done`:消息已入库,附 message_id
- 前端:`useChatStream` 用 `fetch + ReadableStream.getReader()` 读流,`TextDecoder` 增量解码,按 `\n\n` 分块,`parseSSE` 按行拆 `event:`/`data:`。事件分发给 `onEvent`,驱动消息气泡/引用卡片/Trace 面板增量更新。

### 5.8 前端状态与页面:`frontend/src`

- `main.tsx`:挂 React Query `QueryClientProvider`(缺失会白屏——已修) + antd `ConfigProvider(zhCN)`。
- `App.tsx`:`react-router-dom` 两个路由 `/`(聊天)、`/documents`(文档管理)。
- `ChatPage.tsx`:会话列表(新建/打开/重命名/删除)、消息流、输入框、Trace 面板；`useChatStream().send` 发请求并按收到的事件更新本地 messages。
- `DocumentsPage.tsx`:上传组件 + 状态表格(TanStack Query 缓存)。
- `nginx.conf`:本地 5173 容器里 `/api/` 反代到 api:8000,其余回 index.html(SPA 路由)。

---

## 6. 目录逐文件看懂 `backend/`

```
backend/
  app/
    main.py              # 创建 FastAPI app:注册 CORS+路由,startup 时 init_db + ensure_collection
    config.py            # pydantic-settings 读根目录 .env;lru_cache 单例
    api/
      health.py          # GET /api/v1/health
      documents.py       # 上传/列表/详情/切片/删除(20MB 限制)
      conversations.py   # 会话 CRUD + 历史消息
      chat.py            # POST /chat SSE 流式问答
    agent/
      graph.py           # LangGraph 状态图编译 & 路由函数
      nodes.py           # rewrite/router/retrieve/generate/verify 五个节点实现
      prompts.py         # 四个 LLM prompt
      state.py           # AgentState TypedDict
      tools.py           # 四个 langchain tool
    services/
      ingestion.py       # 文档入库(去重/切分/embedding/双写/状态机)
      retrieval.py       # hybrid_search + vector/keyword + rrf_fuse
      splitters.py       # parse_and_split(MD 标题切 / PDF 递归切)
      parsers.py         # pdfplumber、markdown 读取
      rerank.py          # 可选 cross-encoder 重排
      chat_service.py    # 会话/消息/历史/引用落库 + 组装 AgentState
    core/
      db.py              # engine/session/init_db(create_all)
      milvus.py          # MilvusClient(集合管理/upsert/search/删除)
      llm.py             # get_llm / get_embeddings / embed_texts
    models/entities.py   # Document/Chunk/Conversation/Message/Citation ORM
    schemas/             # Pydantic 入参出参(documents/chat)
  scripts/
    seed_sample.py       # 导入 sample_data(8 份)
    make_sample_pdfs.py  # 重新生成 PDF 样例
    eval_ragas.py        # RAGAS 质量评估
  tests/                 # pytest(切片/RRF/Agent 编译/API, mock Milvus/embedding)
frontend/src/            # 见 §5.8
sample_data/             # 8 份演示文档
docker-compose.yml       # 6 服务编排 + 健康检查
.env.example             # 配置模板(零密钥)
eval_dataset.json        # RAGAS 评估问题集
```

---

## 7. 故障排查与降级机制(必读)

### 7.1 白屏 / 报错排查

| 现象 | 原因 | 定位 |
|---|---|---|
| 前端白屏 | React Query Provider 缺失/构建问题 | 强刷 `Ctrl+Shift+R`;看浏览器 Console/Network |
| 文档列表 500 | `metadata` 被 SQLAlchemy 内置遮蔽 | 用 `metadata_` 字段(已修) |
| SSE 无输出 | 配额 429 / 密钥无效 | 看 api 容器日志 `docker compose logs api` |
| Milvus 连不上 | etcd 只监听 localhost | compose 已改为 `-listen-client-urls http://0.0.0.0:2379` |

### 7.2 启动顺序

compose 健康检查 + `depends_on: condition: service_healthy` 已把所有依赖等待做完,正常使用无需手动等。若个别容器没起来,`docker compose ps` 看健康态;`docker compose up -d` 重拉依赖。

### 7.3 检索降级

- 向量检索抛异常 → `hybrid_search` 捕获 → 返回纯关键词结果,对话仍可用。
- 重排失败 → 跳过重排。
- Embedding 429(免费配额)→ 向量召回退化为关键词召回。

### 7.4 LLM 降级

- rewrite / router / verify 任一 LLM 调用失败 → 回退到安全默认(原样 query / retrieve / yes)。
- generate 调用失败(最常见:每日配额耗尽返回 429)→ 回答降级为

```
【生成回答失败】LLM 调用出错(...),以下为检索到的相关片段: ...
```

把检索原文作为兜底呈现,对话不中断;引用照常落库,SSE 流照常完整结束。
次日 00:00 配额重置或换付费 key 后即恢复完整效果。

### 7.5 常见问题 FAQ

- **上传后一直是 failed?** `EMBEDDING_DIM` 与模型不符 / Key 失效或配额用完 / 文件非 PDF/MD。
- **改模型后维度变了怎么办?** 删集重建:`docker compose down -v && docker compose up --build`(会清数据);或手动 drop 集合。
- **刷新后历史没了?** 历史在 PG 里,不是前端 localStorage;刷新后点左侧会话即可回看。
- **为什么"知识库中未找到相关信息"?** 检索无相关片段,LLM 按 prompt 诚实回答,不编造。

---

## 8. 本地开发(改代码热重载)

```bash
# 终端 1:只起依赖
docker compose up etcd minio milvus-standalone postgres

# 终端 2:后端
cd backend
pip install -e .[dev]
uvicorn app.main:app --reload        # http://localhost:8000
# 注意:本地跑需要 .env 里的 POSTGRES_HOST/MILVUS_HOST 指向 localhost

# 终端 3:前端
cd frontend
npm install
npm run dev                           # http://localhost:5173 (vite dev server 会代理 /api)
```

> 本地 vite dev 已配置 `server.proxy: { "/api": "http://localhost:8000" }`,非打包模式也能直接联调;生产容器则由 nginx 反代(见 §5.8)。

---

下一部分:面试项目解析 → `docs/PROJECT_GUIDE_PART2_INTERVIEW.md`

