# 1. 启动 PostgreSQL（Docker + pgvector）


docker run -d --name pgvector-db \
  -e POSTGRES_PASSWORD=xxx \
  -e POSTGRES_DB=my_test_db \
  -p 5433:5432 \
  pgvector/pgvector:pg18

# 2. 启动后端

cd backend
uv run uvicorn main:app --reload --port 8000
首次启动时会自动调用 checkpointer.setup() 创建表。之后可以在 pgAdmin 中看到新增的 checkpoints、checkpoint_writes 等表。

# 3. 启动前端

cd frontend
npm install
npm run dev
打开 http://localhost:5173，输入 “帮我起草一封给客户的订单确认邮件”。

# 4. 预期交互流程

用户: 帮我起草一封给客户的订单确认邮件
  ↓
AI: 已起草邮件：（邮件正文...）
  ↓
⏸ 待审批操作 [批准] [拒绝] [编辑后批准]
  ↓
用户点击"批准"
  ↓
AI: 邮件已发送。

测试刷新恢复：在审批卡片出现时，刷新浏览器页面。前端会通过 localStorage 中的 thread_id 调用 GET /state/{thread_id}，重新渲染审批卡片，状态不丢失。

