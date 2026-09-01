# 项目帮助文档(二):面试项目解析

> 本文帮你把这个作品集项目讲清楚:从"一句话"到"深挖技术细节",以及面试官最爱追问的问题和回答思路。
> 新手上手见 `docs/PROJECT_GUIDE_PART1_QUICKSTART.md`。

---

## 1. 项目速览(30 秒电梯陈述)

**"这是一个企业级 RAG Agent 系统。用户上传企业内部文档(PDF/Markdown),系统通过混合检索 + Agent 编排回答自然语言问题,并给出引用溯源。技术上是 FastAPI + LangChain/LangGraph + Milvus + PostgreSQL + React 的全栈实现,核心亮点是查询改写、意图路由、工具调用和回答自检的 Agent 状态机,以及用 RAGAS 做的质量评估体系。"**

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 React SPA(AntD)                                        │
│  聊天页:消息流 + 引用卡片 + Agent Trace 面板                  │
│  文档管理页:拖拽上传 + 状态表格                               │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP + SSE(流式)
┌──────────────────────────▼──────────────────────────────────┐
│ FastAPI API 层(/api/v1)                                     │
│  documents: 上传/列表/详情/删除/切片                         │
│  conversations: 会话 CRUD                                    │
│  chat: SSE 流式问答                                          │
└──────────────────────────┬──────────────────────────────────┘
┌──────────────────────────▼──────────────────────────────────┐
│ 服务层                                                       │
│  IngestionService(解析→切片→向量化→入库)                     │
│  RetrievalService(混合检索 + RRF)                            │
│  ChatService(会话与引用落库)                                 │
└──────────────────────────┬──────────────────────────────────┘
┌──────────────────────────▼──────────────────────────────────┐
│ Agent 编排层(LangGraph 状态图)                               │
│  rewrite → router → retrieve/tool → generate → verify       │
└──────────────────────────┬──────────────────────────────────┘
┌──────────────────────────▼──────────────────────────────────┐
│ 数据层                                                       │
│  PostgreSQL:文档元数据 / 切片 / 会话 / 引用 / FTS 关键词检索  │
│  Milvus:向量存储与 ANN 检索                                  │
└─────────────────────────────────────────────────────────────┘
```

**面试话术**:我把它分成"写入流"和"问答流"两条管线——写入流是离线的文档处理管道,问答流是在线的 Agent 推理管道。两者通过统一的检索服务解耦。

## 3. 两条核心数据流

### 写入流(文档入库)
```
上传 → 校验(类型/大小)→ 落盘 → 按类型解析 → 切片 → 计算 embedding → Milvus upsert + PG 写记录 → 状态 ready
```

关键设计:
- **MD 用标题层级切片**(MarkdownHeaderTextSplitter),保留 heading 元数据;PDF 按页切 + RecursiveCharacterTextSplitter(500 字/80 重叠,中文分隔符优先)。
- **SHA-256 去重**:相同内容不重复入库;内容变化则重建(幂等)。
- **失败隔离**:单文件失败只标 `failed`,不影响批量其他文件。
- **切片元数据**:`document_id` / `heading` / `page` 全部随向量进 Milvus,支持后续过滤检索。

### 问答流(在线问答)
```
用户提问 → 查询改写(多轮上下文)→ 意图路由 → 混合检索 → 可选重排 → 生成(带引用)→ 自检 → 返回
```

## 4. 技术难点拆解(面试重点)

### 难点 1:混合检索与 RRF 融合
- **问题**:纯向量检索对专有名词、精确条款召回差;纯关键词检索对语义相近表达召回差。
- **方案**:双路召回——Milvus 向量检索 + PostgreSQL FTS(jieba 分词),再用 **RRF(Reciprocal Rank Fusion)** 融合排序:

```
RRF_score(d) = Σ 1 / (k + rank_i)   # k=60
```

- **亮点**:RRF 不用调权重、对分数尺度不敏感,是工程上稳健的融合方案。
- **加分点**:向量检索失败时自动降级为纯关键词检索(可用性设计);支持元数据过滤(指定文档/类型)。

**可能被追问**:
- Q: 为什么不用加权平均融合?→ 两个检索器的分数尺度不同(余弦相似度 vs ts_rank),直接加权需要调优且不稳定;RRF 只用排名,天然免疫尺度差异。
- Q: jieba 分词在 FTS 里怎么用的?→ 查询和入库时用 jieba 预分词成空格连接,PG 用 `to_tsvector('simple')` 存储与匹配,避免默认英文分词器对中文失效。

### 难点 2:Agent 编排(LangGraph 状态图)
- **问题**:简单的"检索→生成"做不好三类问题:① 多轮对话指代("那审批要几天?");② 需要工具/统计的问题("库里几份文档?");③ 回答质量没有保障。
- **方案**:用 LangGraph 构建状态机,5 个节点 + 条件边:

```
rewrite(查询改写)→ router(意图路由)→ retrieve(检索)/ tools(工具调用)→ generate(生成)→ verify(自检)
```

- **rewrite**:LLM 结合对话历史把问题改写成自包含查询。
- **router**:LLM 判断走 `retrieve`(查知识库)/ `tool`(统计/元数据)/ `direct`(闲聊拒答)。
- **tools**:`list_documents` / `count_documents` / `search_documents`(带过滤检索)/ `get_document`(整篇内容),由 ToolNode 循环调用。
- **verify**:LLM 检查答案是否被引用充分支撑,不足则**回退到 retrieve 补检一次**(循环回边,最多 1 次),防幻觉。
- **trace**:每个节点记录步骤名/摘要/耗时,SSE 推给前端展示——面试演示时"可视化的 agent 思考过程"很有冲击力。

**可能被追问**:
- Q: 为什么用 LangGraph 而不是 LangChain 的 AgentExecutor?→ 需要精确控制流程(路由分支、自检回退循环),LangGraph 的状态图让每个节点独立可测、回退边显式可控;AgentExecutor 是黑盒工具循环,难以插入 verify 这类定制逻辑。
- Q: 为什么最多补检 1 次?→ 控制延迟与成本;多次补检收益递减,一次是工程上合理的折中(可配置)。
- Q: 状态里存了什么?→ query / rewritten_query / retrieved / tool_calls / answer / citations / verify_count / trace。

### 难点 3:引用溯源(可解释性)
- **问题**:RAG 回答必须可验证,否则用户无法信任。
- **方案**:检索片段按序编号 [1][2],prompt 强制要求回答引用编号;后端把编号映射到 `citations` 表(存 chunk_id/document_id/score/snippet),前端渲染成可点击引用卡片。
- **面试点**:这是企业场景"回答可审计"的落地,面试官很吃这一套。

### 难点 4:RAG 质量评估(RAGAS)
- **问题**:RAG 系统好不好不能靠感觉,需要量化。
- **方案**:`eval_dataset.json` 内置 12 条问题(单文档事实/跨文档多跳/统计工具/拒答四类),`eval_ragas.py` 跑三个指标:
  - **faithfulness**(忠实度):答案是否被检索上下文支撑(防幻觉的核心指标)
  - **answer_relevancy**(回答相关性)
  - **context_precision**(上下文精确度):检索到的内容是否够用
- **面试点**:能说出"我不仅做了 RAG,还量化了它",是明显的加分项。

### 难点 5:工程化与可维护性
- **测试**:pytest 覆盖切片/RRF/Agent 编译/API(mock Milvus 与 embedding);前端 vitest 测 SSE 解析与上传组件。
- **配置**:全部环境变量注入,`.env.example` 零密钥;embedding 维度可配置。
- **部署**:Docker Compose 一键编排 6 个服务;前后端分离,nginx 反代。
- **健壮性**:LLM 超时/重试、Milvus 降级、文档级失败隔离、流式中断处理。

## 5. 数据模型(背下来)

```sql
documents     -- 文档元数据(id/title/source_type/status/checksum/metadata)
chunks        -- 切片(id/document_id/content/heading/page/metadata)
conversations -- 会话
messages      -- 消息(role/content)
citations     -- 引用(message_id/chunk_id/document_id/score/snippet)
```

- 向量不进 PG,单独存 Milvus(chunk_id 为主键关联)。
- `tenant_id` 预留:体现多租户意识(单用户演示版,但模型层面已留扩展位)。

## 6. 项目亮点自述(1 分钟版)

"这个项目我做了三个层次的工作。第一层,完整的 RAG 链路:多格式解析、结构化切片、向量化入库,支持文档管理。第二层,企业级检索质量:混合检索 + RRF 融合、jieba 中文分词、查询改写、可选重排、故障降级。第三层,Agent 化:用 LangGraph 把问答流程做成显式状态机,有意图路由、工具调用和自检回退,并且整个思考过程可追踪、可展示。最后用 RAGAS 量化了回答质量。技术上它是 FastAPI + React 的全栈实现,Docker Compose 一键部署。"

## 7. 高频面试问答(Q&A)

**Q1: 什么是 RAG?为什么不用直接让大模型回答?**
答:RAG = 检索增强生成。大模型的知识有截止日期、且不包含私有数据;RAG 先从知识库检索相关内容,再让模型基于这些内容回答,解决"知识私有""幻觉""可溯源"三个问题。

**Q2: 向量检索和关键词检索的区别?为什么都要?**
答:向量检索语义匹配(换说法也能找到),关键词检索精确匹配(专有名词/条款更准)。两者互补,所以混合。

**Q3: 什么是 embedding?什么是向量相似度?**
答:embedding 把文本映射成高维向量(如 1536 维),语义相近的文本向量距离近。检索就是"找到和问题向量最接近的文档片段向量",用余弦相似度衡量,近似最近邻(ANN)由 Milvus 的 HNSW 索引加速。

**Q4: 为什么用 Milvus 而不是直接用 PG 的向量扩展?**
答:Milvus 是专门的向量数据库,支持亿级规模、HNSW/IVF 索引、标量过滤与向量检索混合,性能更好;PG 在这里承担元数据、会话、FTS 的职责,各司其职。

**Q5: 怎么防止幻觉?**
答:三层:1) prompt 要求"只在上下文中找答案,找不到就说不知道";2) 引用溯源让回答可验证;3) verify 自检节点 + RAGAS 的 faithfulness 指标量化。

**Q6: 多轮对话怎么处理?**
答:rewrite 节点把"那审批要几天?"结合历史改写为"差旅费报销的审批流程需要几天?",变成自包含查询再检索。

**Q7: 遇到哪些坑?怎么解决的?**
答:① 中文分词:PG 默认分词器对中文无效,用 jieba 预分词;② embedding 维度不匹配:模型换了维度就得改配置并重建集合;③ 第三方库 pymilvus 导入时会把根目录 .env 注入环境变量污染测试,在 conftest 里做了隔离;④ sqlite 无 FTS,为本地测试加了 LIKE 降级实现。

**Q8: 性能怎么样?**
答:写入流按文档批量 embedding、Milvus 批量 upsert;问答流 top_k 双路召回(各 10 条)RRF 融合后截断,LLM 生成流式返回,首 token 延迟由 LLM 决定;Agent 全链路含多次 LLM 调用,属于"质量优先"的设计,可用配置收紧(如关闭自检)。

**Q9: 如果文档量从几十份变成几十万份,哪里会先遇到瓶颈?**
答:① Milvus 检索本身能扛,瓶颈在 PG FTS(可换 ES/OpenSearch);② embedding 计算变慢(可上批量/GPU/缓存);③ 切片入库变慢(可改消息队列异步管道);④ LLM 调用成本(可加缓存与路由)。这正是我预留 `tenant_id` 和模块化服务层的原因。

## 8. 简历怎么写(项目条目模板)

```
企业级 RAG Agent 系统(全栈)| FastAPI · LangGraph · Milvus · PostgreSQL · React
- 构建文档问答系统:PDF/MD 解析、结构化切片、向量化入库、流式问答,支持引用溯源
- 混合检索:Milvus 向量 + PostgreSQL FTS(jieba)双路召回,RRF 融合,向量故障自动降级
- LangGraph Agent 编排:查询改写、意图路由、工具调用(文档统计/过滤检索)、回答自检回退(≤1 次)
- RAGAS 质量评估:faithfulness / answer_relevancy / context_precision,内置 12 条评估集
- 工程化:Docker Compose 一键部署 6 服务;pytest/vitest 测试;环境变量配置,零硬编码密钥
```

---

## 9. 如果面试官现场想看代码

| 想看什么 | 指到哪 |
|---|---|
| 整个问答流程 | `backend/app/agent/graph.py`(状态图)+ `nodes.py`(节点)|
| 混合检索 | `backend/app/services/retrieval.py`(`hybrid_search`/`rrf_fuse`)|
| 文档入库 | `backend/app/services/ingestion.py` |
| 切片策略 | `backend/app/services/splitters.py` |
| 流式接口 | `backend/app/api/chat.py`(SSE)|
| 数据模型 | `backend/app/models/entities.py` |
| 前端 SSE 解析 | `frontend/src/hooks/useChatStream.ts` |
