# Human-in-the-Loop 邮件审批 Demo

基于 **LangGraph + FastAPI + React** 的最小可运行示例，完整演示 Human-in-the-Loop（HITL）流程：

> AI 起草邮件 → 图在 `interrupt()` 处暂停 → 人工在前端审批（批准 / 拒绝 / 编辑后批准）→ 恢复执行并发送邮件

会话状态由 `AsyncPostgresSaver` 持久化到 PostgreSQL（pgvector 镜像），因此**审批过程中刷新页面也不会丢失上下文**。

## 目录结构

```text
hitl-demo/
├── backend/
│   ├── graph.py             # LangGraph 图定义：draft_email → human_review(interrupt) → send_email
│   └── main.py              # FastAPI 入口：/chat、/resume、/state + Checkpointer 生命周期管理
├── frontend/
│   └── src/
│       ├── App.tsx          # 对话界面 + 刷新恢复逻辑
│       ├── ApprovalCard.tsx # 审批卡片（批准 / 拒绝 / 编辑后批准）
│       └── api.ts           # 后端接口封装
└── README.md
```

## 环境准备

### 1. 安装依赖

```bash
# 后端依赖（在仓库根目录执行，项目由 uv 管理）
uv sync

# 前端依赖
cd frontend
npm install
```

### 2. 配置 .env（仓库根目录）

```ini
DEEPSEEK_API_KEY="xxx"

# postgres 连接信息
DB_HOST=127.0.0.1
DB_PORT=5433
DB_NAME=my_test_db
DB_USER=postgres
DB_PASSWORD=xxx
```

> `config/db_url.py` 会自动对密码做 URL 编码并拼接成 `DB_URI`，所以这里可以直接写原始密码。

## 启动步骤

### 1. 启动 PostgreSQL（Docker + pgvector）

```bash
docker run -d --name pgvector-db \
  -e POSTGRES_PASSWORD=xxx \
  -e POSTGRES_DB=my_test_db \
  -p 5433:5432 \
  pgvector/pgvector:pg18
```

> 容器端口 `5433` 必须与 `.env` 中的 `DB_PORT=5433` 保持一致。

### 2. 启动后端

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

> 首次启动时会自动调用 `checkpointer.setup()` 创建表。之后可以在 pgAdmin 中看到新增的 `checkpoints`、`checkpoint_writes` 等表。

### 3. 启动前端

```bash
cd frontend
npm run dev
```

打开 <http://localhost:5173>，输入：

```text
帮我起草一封给客户的订单确认邮件
```

## 预期交互流程

```text
用户：帮我起草一封给客户的订单确认邮件
  │
  ▼
AI：已起草邮件：（邮件正文 ...）
  │
  ▼
⏸ 待审批操作   [ ✅ 批准 ]  [ ❌ 拒绝 ]  [ ✏️ 编辑后批准 ]
  │
  │  点击「批准」
  ▼
AI：邮件已发送。
```

三种审批结果对应的行为：

| 用户操作 | 前端提交的决策 | 图内行为 | 最终回复 |
| --- | --- | --- | --- |
| ✅ 批准 | `{ type: "approve" }` | `approved = true` | `邮件已发送。` |
| ❌ 拒绝 | `{ type: "reject", message: "原因" }` | `approved = false`、`reject_reason = 原因` | `邮件未发送。原因：原因` |
| ✏️ 编辑后批准 | `{ type: "edit", editedAction: { args: { body } } }` | `approved = true`，并用编辑后的正文 | `已用编辑后的内容发送：（编辑后的正文）` |

## 测试刷新恢复

在审批卡片出现时，刷新浏览器页面：

1. 前端从 `localStorage` 中读取 `thread_id`；
2. 调用 `GET /state/{thread_id}` 重新拉取图状态；
3. 若状态为 `interrupted`，重新渲染审批卡片 —— **状态不丢失**。

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/chat` | 发起或继续对话；命中 `interrupt()` 时返回 `status: "interrupted"` |
| `POST` | `/resume` | 携带审批决策恢复执行（`Command(resume=...)`） |
| `GET` | `/state/{thread_id}` | 查询指定会话的当前状态，用于前端刷新恢复 |

## 关键实现

### 1. 在节点内暂停：`interrupt()`

```python
# backend/graph.py
decision = interrupt({
    "action": "send_email",
    "args": {"to": "customer@example.com", "subject": "关于您的订单", "body": last_ai_msg},
    "description": "请审核这封即将发送的邮件。",
})
# ↓ 只有用户审批后，下面的代码才会继续执行
if decision.get("type") == "approve":
    return {"approved": True}
```

### 2. 恢复执行：`Command(resume=...)`

```python
# backend/main.py
await graph.ainvoke(Command(resume=req.resume), config)
```

### 3. 后端如何判断「被中断了」

```python
# backend/main.py
state = await graph.aget_state(config)
if state.next:  # 还有待执行的节点 → 说明在 interrupt() 处暂停了
    interrupt_payload = state.tasks[0].interrupts[0].value
    return {"status": "interrupted", "thread_id": thread_id, "interrupt": interrupt_payload}
```

### 4. 前端刷新恢复

```ts
// frontend/src/App.tsx
const saved = localStorage.getItem("hitl_thread_id");
if (saved) {
  const res = await fetchState(saved);
  setThreadId(saved);
  handleResponse(res);
}
```

## 常见问题

- **输入框和发送按钮是灰的？** 出现审批卡片时输入会被禁用（`disabled={loading || !!interrupt}`），先处理完审批再继续对话。
- **后端启动报错 `未找到 DEEPSEEK_API_KEY`**：确认仓库根目录下已按 `.env.example` 创建 `.env` 并填好 Key。
- **前端提示「请求失败，请检查后端是否启动。」**：检查后端 8000 端口是否已启动；后端 CORS 只放行了 `http://localhost:5173`，换端口访问需要同步修改 `main.py`。
- **想开一个全新的会话**：清除浏览器 `localStorage` 中的 `hitl_thread_id`，下次发送会自动生成新的 `thread_id`。

