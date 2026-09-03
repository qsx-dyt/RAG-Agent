# Enterprise RAG Agent

企业级 RAG(检索增强生成)Agent 系统:多格式文档解析、混合检索、LangGraph Agent 编排、引用溯源与流式问答。

## 技术亮点

- **混合检索**:Milvus 向量检索 + PostgreSQL FTS(jieba 分词)双路召回,RRF 融合,支持元数据过滤与 Milvus 故障降级。
- **Agent 编排**:LangGraph 状态图(rewrite → router → retrieve/tool → generate → verify),多轮查询改写、意图路由、工具调用、回答自检补检。
- **引用溯源**:回答带 [1][2] 编号引用,前端可点击回看原文片段。
- **会话管理**:会话新建/重命名/删除、历史消息回看,引用随消息持久化。
- **健壮降级**:LLM/Embedding 失败时,Agent 自动降级——生成阶段回退为检索片段兜底、向量检索退化为关键词检索,SSE 流始终完整结束。
- **RAG 评估**:RAGAS 脚本量化 faithfulness / answer_relevancy / context_precision。
- **全栈工程**:FastAPI + React(Ant Design)+ Docker Compose 一键启动,环境变量配置。

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + FastAPI + LangChain/LangGraph + SQLAlchemy |
| 检索 | Milvus(向量)+ PostgreSQL(FTS/jieba)|
| 前端 | React 18 + Vite|
| 部署 | Docker Compose|
| 评估 | RAGAS |

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env,填入 OPENAI_API_KEY / OPENAI_BASE_URL / LLM_MODEL 与 Embedding 配置

# 2. 一键启动全部服务(已内置健康检查,自动等待 postgres/milvus 就绪)
docker compose up --build

# 3. 打开前端
# http://localhost:5173
```

## 演示提问

导入样例数据后,可以依次尝试:

1. **事实查询**:员工报销差旅费需要哪些材料?
2. **多轮改写**:先问"报销差旅费需要哪些材料?",再问"那审批流程呢?"(自动改写为自包含查询)
3. **工具/统计**:知识库里一共有几份制度文档?
4. **跨文档多跳**:新员工入职当天要签哪些文件?和试用期考核有什么关系?
5. **拒答**:今天天气怎么样?

点击消息右侧的引用卡片可查看原文;右侧 Trace 面板展示 agent 每一步(rewrite / router / retrieve / generate)与耗时。

## RAG 评估

```bash
docker compose exec api python -m scripts.eval_ragas
```

输出 `eval_report.json`(faithfulness / answer_relevancy / context_precision 平均分)。数据集见 `eval_dataset.json`(12 条,覆盖单文档事实 / 跨文档多跳 / 统计工具 / 拒答)。

## 目录结构

```
backend/           FastAPI 后端(app: api/core/models/schemas/services/agent)
frontend/          React 前端(api/hooks/pages/components)
sample_data/       内置演示文档
eval_dataset.json  RAGAS 评估数据集
docker-compose.yml 一键编排
```
