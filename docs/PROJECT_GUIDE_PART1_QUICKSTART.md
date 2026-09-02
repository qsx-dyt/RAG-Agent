# 项目帮助文档(一):快速上手 —— 小白友好版

> 本文面向第一次接触这个项目的人。读完本文,你能在本机把它跑起来,并理解它"大概做了什么"。
> 面试向的深度解析见 `docs/PROJECT_GUIDE_PART2_INTERVIEW.md`。

---

## 1. 这个项目是什么?

一句话:**"把公司文档变成能聊天问答的 AI 助手"**。

你上传一批内部文档(PDF / Markdown),然后像用 ChatGPT 一样提问,它会基于你上传的文档回答,并且每条回答都标注"这段话来自哪份文档"。

- 例子:上传《报销制度.pdf》后,问"报销差旅费需要哪些材料?",它会回答并附上"出自《报销制度》"的引用。

## 2. 它由哪几部分组成?

```
┌──────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  前端(网页)   │ ───▶ │  后端(问答大脑)    │ ───▶ │  数据存储         │
│  React 页面   │      │  FastAPI + Agent  │      │  Milvus(向量库)   │
│  聊天/文档管理 │      │  处理你的提问      │      │  PostgreSQL(资料) │
└──────────────┘      └──────────────────┘      └──────────────────┘
```

- **前端**:浏览器里看到的界面(聊天页、文档管理页)。
- **后端**:真正的"大脑"。接收提问 → 在文档里找相关片段 → 让大模型组织答案 → 返回带引用的回答。
- **数据存储**:两块。Milvus 存"文档片段的向量"(数学表示,用于语义搜索);PostgreSQL 存文档本身、聊天记录等常规数据。

## 3. 跑起来需要什么?

| 需要的东西 | 说明 | 必备? |
|---|---|---|
| Docker Desktop | 用来一键启动 Milvus/PostgreSQL/前后端 | 是(推荐方式) |
| Python 3.11+ | 本地跑后端脚本 | 开发时 |
| Node.js 18+ | 本地跑前端 | 开发时 |
| 一个 LLM API Key | 大模型的钥匙(如 DeepSeek/通义/任何 [OI] 兼容接口) | 是 |
| 一个 Embedding API Key | 向量模型的钥匙(一般和上面同一个) | 是 |

> 本项目用的是"[OI] 兼容"接口:只要服务商提供 `/v1` 风格的 API,填上 `BASE_URL` + `API_KEY` + 模型名就能用。

## 4. 五分钟快速上手

### 第 1 步:准备配置文件

项目根目录有个 `.env.example`(模板,值都是空的)。复制一份为 `.env`(真实配置,已被 git 忽略,不会泄漏):

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

打开 `.env`,至少填这三处(以本项目使用的 chatanywhere 为例):

```bash
OPENAI_API_KEY=你的Key
OPENAI_BASE_URL=https://api.chatanywhere.tech
LLM_MODEL=gpt-4o-mini

EMBEDDING_API_KEY=你的Key
EMBEDDING_BASE_URL=https://api.chatanywhere.tech
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIM=1536        # 必须和你 embedding 模型的维度一致!
```

> ⚠️ **最容易踩的坑**:`EMBEDDING_DIM` 必须等于模型输出的维度。`text-embedding-ada-002` 是 1536,`bge-m3` 是 1024。填错了,向量库(Milvus)会报维度不匹配。

### 第 2 步:一键启动(推荐)

```bash
docker compose up --build
```

这会依次启动 6 个容器:`postgres`(资料库)、`etcd`+`minio`+`milvus-standalone`(向量库三件套)、`api`(后端)、`web`(前端)。

启动需要 1–3 分钟(Milvus 首次启动较慢)。compose 已内置**健康检查**:`api` 会自动等待 `postgres`/`milvus` 就绪后才启动,`web` 等 `api` 就绪——你不需要手动等待或反复重启。

### 第 3 步:导入演示文档

```bash
docker compose exec api python -m scripts.seed_sample
```

把 `sample_data/` 里 8 份演示文档(6 份 Markdown + 2 份 PDF)解析并入库(该目录已自动挂载进 api 容器,无需手动拷贝)。看到每行 `xxx: ready` 就成功了。

### 第 4 步:打开网页开始聊天

浏览器访问 **http://localhost:5173**

- 「文档管理」页:可以上传自己的文档(支持 `.pdf` / `.md`),查看解析状态。
- 「聊天」页:提问试试:

```
问:报销差旅费需要哪些材料?
```

回答会附上引用卡片;右侧面板能看到 AI 的"思考步骤"(Agent Trace)。
- 左侧会话列表支持**会话管理**:点一下某个会话可回看历史问答;每个会话都有「重命名」和「删除」操作;点「新会话」开启新对话。

### 第 5 步:关掉

```bash
docker compose down
```

> 想保留数据就加 `-v`?不需要——本项目的 `docker compose down` 会保留数据卷。想彻底清空再 `docker compose down -v`。

## 5. 本地开发模式(改代码用)

不想每次改后端都重新构建镜像,可以用本地开发模式:

```bash
# 终端 1:只启动依赖(数据库/向量库)
docker compose up etcd minio milvus-standalone postgres

# 终端 2:启动后端(热重载)
cd backend
pip install -e .[dev]
uvicorn app.main:app --reload          # http://localhost:8000

# 终端 3:启动前端(热重载)
cd frontend
npm install
npm run dev                            # http://localhost:5173
```

## 6. 项目目录速览(先认识这些就够了)

```
backend/
  app/
    main.py            # 后端入口,创建 FastAPI 应用
    config.py          # 读取 .env 配置
    api/               # 对外接口(上传文档/聊天/健康检查)
    services/          # 核心业务:解析切片、检索、问答
    agent/             # Agent 编排(LangGraph):思考流程
    core/              # 基础设施:数据库、向量库、大模型客户端
  scripts/
    seed_sample.py     # 导入演示文档
    eval_ragas.py      # RAG 质量评估
  tests/               # 自动化测试
frontend/
  src/pages/           # 聊天页、文档管理页
  src/components/      # 消息气泡、引用卡片、Trace 面板等
sample_data/           # 8 份演示文档
docker-compose.yml     # 一键启动编排
.env.example           # 配置模板
eval_dataset.json      # 评估用的问题集
```

## 7. 常见问题(FAQ)

**Q: 报错 "no such table" 或连不上数据库?**
A: 正常情况下不用管——compose 的健康检查已让 `api` 等 `postgres` 就绪后才启动。若仍报错,执行 `docker compose ps` 看 `postgres` 是否为 `healthy`,必要时 `docker compose up -d` 重启。

**Q: 上传文档后状态一直是 failed?**
A: 常见原因:1) `EMBEDDING_DIM` 与模型不符;2) API Key 失效或配额用完(免费 key 通常有每日次数限制);3) 文件不是 PDF/MD。

**Q: 为什么回答变成了"【生成回答失败】..."?**
A: LLM 的每日免费配额用完了(返回 429)。系统会自动降级:把检索到的原文片段作为兜底回答展示,保证对话不中断。次日 00:00 配额重置,或换付费 key 后恢复正常回答。

**Q: 为什么回答"知识库中未找到相关信息"?**
A: 检索没找到相关片段。可能文档没导入成功,或问题与文档内容无关。这是系统诚实的表现——不会瞎编。

**Q: Milvus 启动特别慢?**
A: 正常。首次启动要初始化 etcd/minio/milvus 三件套,1–3 分钟都正常。

**Q: 想换一个大模型?**
A: 改 `.env` 里的 `OPENAI_BASE_URL` + `OPENAI_API_KEY` + `LLM_MODEL` 三个变量,重启 api 容器即可。代码不需要改。

---

下一部分:面试项目解析 → `docs/PROJECT_GUIDE_PART2_INTERVIEW.md`
