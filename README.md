# My_LangGraph_Learning

LangGraph 学习实践仓库：从最小图出发，逐步实现循环、工具调用、记忆、人工审批、流式输出与结构化输出。各主题独立成目录，共用 [config/](config) 中的模型与数据库配置。

## 环境准备

```bash
# 1. 安装依赖（需要 Python >= 3.12，由 uv 管理，依赖清单见 pyproject.toml）
uv sync

# 2. 配置环境变量：复制 .env.example 为 .env，填入 DeepSeek Key 与 PostgreSQL 连接信息
cp .env.example .env        # Windows: copy .env.example .env

# 3. 需要数据库的示例（memory/、hitl-demo/）先启动带 pgvector 的 PostgreSQL
docker run -d --name pgvector-db \
  -e POSTGRES_PASSWORD=xxx \
  -e POSTGRES_DB=my_test_db \
  -p 5433:5432 \
  pgvector/pgvector:pg18
```

> - `-p 5433:5432` 的宿主机端口需与 `.env` 中的 `DB_PORT` 一致。
> - 除 [hitl-demo/](hitl-demo) 外，各示例统一用 `uv run python <入口文件>` 运行（建议在仓库根目录执行，[config/llm.py](config/llm.py) 会按绝对路径加载根目录 `.env`）。

## 已完成内容

### 1. 最小图 Hello World —— [helloworld.py](helloworld.py)

用 mock 节点返回 `hello world`，跑通 `StateGraph` 最小闭环。

- 关键 API：`StateGraph(MessagesState)` → `add_node` → `add_edge(START / END)` → `compile()` → `invoke()`
- 全流程无真实模型调用，适合作为图结构的起点参考

### 2. 图内循环 —— [example/how_to_implement_loop.py](example/how_to_implement_loop.py)

`a → b → c → d` 四个节点，再从 `d` 用条件边回跳到 `a` / `b`，演示「循环 + 退出」。

- 关键 API：`add_conditional_edges(source="d", path=route_after_d)`
- 路由规则：`counter >= 5` 返回 `END` 退出，奇数回 `a`、偶数回 `b`（奇数/偶数只是模拟业务分支）
- `compile(debug=True)` 可打印每一步流转日志

![LangGraph 实现简单循环](example/langgraph%E5%AE%9E%E7%8E%B0%E7%AE%80%E5%8D%95%E5%BE%AA%E7%8E%AF.png)

### 3. 工具调用 Agent（计算器）—— [tools/calculator.py](tools/calculator.py)

ReAct 式「LLM 决策 → 执行工具 → 结果回灌」循环。

- 3 个工具 `add` / `multiply` / `divide` 用 `@tool` 定义，`model.bind_tools()` 绑定到模型
- `llm_call` 节点调用模型并用 `llm_calls` 统计调用次数；`tool_node` 节点执行 `tool_calls` 并返回 `ToolMessage`
- `should_continue` 条件边：模型产出 `tool_calls` 就去 `tool_node`，否则 `END`
- 示例输入：「请计算3乘以123」

### 4. 内容优化 Agent —— [content_optimize_agent/content.py](content_optimize_agent/content.py)

「评估 → 优化 → 再评估」的自省循环，直到质量达标或达到迭代上限。

- `ContentState`：`scores`、`is_qualified`、`iteration`、`max_iterations`（防止死循环）
- `evaluate` 节点：LLM 输出 JSON，按完整性 / 逻辑性 / 吸引力 / SEO 友好度 / 可读性五个维度打 1-10 分，全维度 >= 7 才达标；JSON 解析失败时降级为默认低分
- `optimize` 节点：定位最低分维度并让 LLM 重写内容；`should_continue` 决定 `END` 还是回到 `optimize`（示例设置为最多 3 轮，默认 5 轮）

### 5. 记忆

#### 5.1 短期记忆 —— [memory/short_term_memory.py](memory/short_term_memory.py)

- `PostgresSaver.from_conn_string(DB_URI)` 作为 checkpointer，用 `thread_id` 隔离不同会话
- 示例：同一线程内先说 `I'm bob`，再问 `what's my name?`，验证多轮上下文被正确保留
- 顺带统计「导入依赖 / 建表 / 图编译 / 每轮对话」各阶段耗时；`checkpointer.setup()` 只需首次执行，代码中已注释

#### 5.2 长期记忆 —— [memory/long_term_memory.py](memory/long_term_memory.py)

跨线程（`chat_1` → `chat_2`，全新线程）记住用户偏好，验证长期记忆与短期记忆的分离。

- `PostgresStore` 作为 store，以 `memory` 字段建向量索引，嵌入模型为本地 vLLM 部署的 `bge-m3`（1024 维）
- `Runtime[Context]` 传入 `user_id`，长期记忆存放在命名空间 `(user_id, "memories")`
- `save_memory` 节点：LLM 从用户最新一句话中抽取值得长期保留的信息，符合条件则 `store.put()`
- `call_model` 节点：`store.search(query, limit=3)` 语义召回，把记忆作为系统提示注入后再生成回复
- 短期上下文仍用 `InMemorySaver`，长期数据落在 PostgreSQL
- 前置：本地需先启动 vLLM 的 bge-m3 服务（端口 8001），完整启动命令见该文件头部 docstring

### 6. Human-in-the-Loop 全栈 Demo —— [hitl-demo/README.md](hitl-demo/README.md)

FastAPI + LangGraph + React：AI 起草邮件 → 人工审批 → 恢复执行，是唯一带前端的完整示例。

- 图定义 [hitl-demo/backend/graph.py](hitl-demo/backend/graph.py)：`draft_email → human_review(interrupt) → send_email`，支持「批准 / 拒绝 / 编辑后批准」三种决策
- 服务端 [hitl-demo/backend/main.py](hitl-demo/backend/main.py)：`AsyncPostgresSaver` 生命周期管理，提供 `/chat`、`/resume`、`/state/{thread_id}` 三个端点，用 `Command(resume=...)` 恢复中断
- 前端 [hitl-demo/frontend/src/App.tsx](hitl-demo/frontend/src/App.tsx)、[ApprovalCard.tsx](hitl-demo/frontend/src/ApprovalCard.tsx)、[api.ts](hitl-demo/frontend/src/api.ts)：对话界面、审批卡片，并用 `localStorage` 中的 `thread_id` 实现刷新后恢复
- 启动与交互说明见 [hitl-demo/README.md](hitl-demo/README.md)

### 7. 流式输出 —— [streaming/weather_search.py](streaming/weather_search.py)

用 `create_agent` 搭一个天气查询 Agent（`get_weather`、`get_forecast` 两个工具），演示三种流式方式。

- 工具内用 `get_stream_writer()` 主动推送进度（如「正在查询 北京 的天气...」），这类自定义数据走 `custom` 流
- 演示 1 事件流：`agent.stream_events(..., version="v3")`，遍历 `stream.messages` 逐个取推理增量（`message.reasoning`）、正文增量（`message.text`）和工具调用参数分片（`message.tool_calls`，可看到参数被逐步补齐），最后用 `stream.output` 拿最终状态（v3 在 langgraph 中标记为 experimental）
- 演示 2 多模式流：`agent.stream(..., stream_mode=["updates", "messages", "custom"])`，分别对应节点级状态更新 / LLM token / 工具内进度
- 演示 3 异步事件流：`agent.astream_events(..., version="v2")`，只筛 `on_chat_model_stream`、`on_tool_start`、`on_tool_end` 三类关键事件

### 8. 结构化输出 —— [structured_output/structured_output.py](structured_output/structured_output.py)

让模型直接产出符合 Pydantic Schema 的对象，结果统一从 `result["structured_response"]` 读取。

- 三个 Schema：`ContactInfo`（name / email / phone）、`ProductReview`（`rating` 为 1-5 的 `Optional[int]` 且带 `ge/le` 校验、`sentiment` 用 `Literal` 限定枚举、`key_points` 为字符串列表）、`CustomerComplaint`（`issue_type` / `severity` 都用 `Literal` 限定）
- 演示 1 原生策略：`create_agent(response_format=ContactInfo)` 直接传 Pydantic 模型，由 langchain 按模型能力自动选策略——优先 `ProviderStrategy`（原生结构化输出），模型不支持时回落 `ToolStrategy`
- 演示 2 工具调用策略：显式 `response_format=ToolStrategy(ProductReview)`，即把 Schema 当成工具调用参数来生成
- 演示 3 Union Schema：`ToolStrategy(Union[ProductReview, CustomerComplaint])`，同一个 Agent 按输入自动选择用哪个 Schema（评论分析 / 投诉处理）
- 演示 4 自定义错误处理：`handle_errors` 回调分别处理 `StructuredOutputValidationError` 与 `MultipleStructuredOutputsError`，把修正提示回灌给模型重试
- 演示 5 自定义工具消息：`tool_message_content` 替换回填给模型的 `ToolMessage` 内容
- 注意：该示例没有复用 `config.model`，而是自行构造 `ChatDeepSeek`，并用 `extra_body={"thinking": {"type": "disabled"}}` 关闭思考模式

## 公共模块

| 文件 | 作用 |
| --- | --- |
| [config/llm.py](config/llm.py) | 读取 `DEEPSEEK_API_KEY`；模块级单例 `model`（`deepseek-flash`、`temperature=0.1`、`max_retries=3`）以及可自定义参数的工厂函数 `get_model()` |
| [config/db_url.py](config/db_url.py) | 读取 `DB_*` 环境变量，用 `quote_plus` 编码密码后拼出 `DB_URI`（`sslmode=disable&connect_timeout=5`） |
| [config/__init__.py](config/__init__.py) | 统一出口，各示例只需 `from config import model, DB_URI` |

## 目录结构

```text
My_LangGraph_Learning/
├── helloworld.py                    # 最小图
├── example/
│   ├── how_to_implement_loop.py     # 条件边实现循环
│   └── langgraph实现简单循环.png      # 循环流程图
├── tools/calculator.py              # 工具调用 Agent（@tool + bind_tools）
├── content_optimize_agent/content.py  # 评估-优化 Agent
├── memory/
│   ├── short_term_memory.py         # 短期记忆（checkpointer）
│   └── long_term_memory.py          # 长期记忆（store + 向量检索）
├── streaming/weather_search.py      # 流式输出（事件流 / stream_mode / astream_events）
├── structured_output/
│   └── structured_output.py         # 结构化输出（Pydantic Schema + 两种策略）
├── hitl-demo/                       # Human-in-the-Loop 全栈 Demo
│   ├── backend/                     # FastAPI + LangGraph
│   ├── frontend/                    # React + Vite
│   └── README.md
├── config/                          # 公共配置（模型 + 数据库连接串）
├── pyproject.toml / uv.lock         # 依赖清单与锁文件
└── .env.example                     # 环境变量模板
```

## 说明

- [example/](example)、[tools/](tools)、[content_optimize_agent/](content_optimize_agent) 末尾会用 `get_graph(xray=True).draw_mermaid_png()` 输出流程图：需要联网（langgraph 默认走 mermaid.ink 渲染），在普通终端只会打印对象的 repr，建议在 Jupyter / Notebook 中运行以便直接看图。
- `memory/`、`hitl-demo/` 需要 PostgreSQL；`hitl-demo/` 还需同时启动后端（8000）与前端（5173）。
