# My_LangGraph_Learning

LangGraph 学习实践仓库：从最小图出发，逐步实现循环、工具调用、记忆与人工审批。各主题独立成目录，共用 [config/](config) 中的模型与数据库配置。

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

### 3. 工具调用 Agent（计算器）—— [calculator/calculator.py](calculator/calculator.py)

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
├── calculator/calculator.py         # 工具调用 Agent
├── content_optimize_agent/content.py  # 评估-优化 Agent
├── memory/
│   ├── short_term_memory.py         # 短期记忆（checkpointer）
│   └── long_term_memory.py          # 长期记忆（store + 向量检索）
├── hitl-demo/                       # Human-in-the-Loop 全栈 Demo
│   ├── backend/                     # FastAPI + LangGraph
│   ├── frontend/                    # React + Vite
│   └── README.md
├── config/                          # 公共配置（模型 + 数据库连接串）
├── pyproject.toml / uv.lock         # 依赖清单与锁文件
└── .env.example                     # 环境变量模板
```

## 说明

- [example/](example)、[calculator/](calculator)、[content_optimize_agent/](content_optimize_agent) 末尾会用 `get_graph(xray=True).draw_mermaid_png()` 输出流程图：需要联网（langgraph 默认走 mermaid.ink 渲染），在普通终端只会打印对象的 repr，建议在 Jupyter / Notebook 中运行以便直接看图。
- `memory/`、`hitl-demo/` 需要 PostgreSQL；`hitl-demo/` 还需同时启动后端（8000）与前端（5173）。