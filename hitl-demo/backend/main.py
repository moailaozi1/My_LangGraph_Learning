# FastAPI入口 + Checkpointer生命周期管理

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from langchain_core.messages import HumanMessage

from graph import build_graph

import sys
import os

# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 推算出根目录的绝对路径（根据你的结构，backend退两级到根目录）
root_dir = os.path.abspath(os.path.join(current_dir, "../.."))

# 将根目录插入到系统路径的最前面
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
# 获取postgresql 连接字符串
from config import DB_URI

# ── 全局变量 ──
graph = None
checkpointer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    在 FastAPI 启动时初始化 Checkpointer 和图，
    在关闭时释放连接。
    """
    global graph

    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
        await checkpointer.setup()  # ✅ 现在 checkpointer 是真正的实例
        graph = build_graph(checkpointer)

        yield  # 保持连接打开，直到应用关闭


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 开发服务器
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求模型 ──
class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None


class ResumeRequest(BaseModel):
    thread_id: str
    resume: dict  # 例如 {"type": "approve"} 或 {"type": "reject", "message": "..."}


# ── 端点 1：启动或继续对话 ──
@app.post("/chat")
async def chat(req: ChatRequest):
    import uuid

    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # 用 ainvoke 执行图（会运行到 interrupt 处暂停）
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=req.message)]},
        config,
    )

    # ★ 关键：通过 aget_state 检测是否遇到了中断
    state = await graph.aget_state(config)
    if state.next:  # 还有待执行的节点 → 说明被中断了
        interrupt_payload = state.tasks[0].interrupts[0].value
        return {
            "status": "interrupted",
            "thread_id": thread_id,
            "interrupt": interrupt_payload,
        }

    return {
        "status": "completed",
        "thread_id": thread_id,
        "messages": [m.model_dump() for m in state.values["messages"]],
    }


# ── 端点 2：恢复执行（处理前端审批结果）──
@app.post("/resume")
async def resume(req: ResumeRequest):
    config = {"configurable": {"thread_id": req.thread_id}}

    # ★ 关键：用 Command(resume=...) 恢复执行
    result = await graph.ainvoke(
        Command(resume=req.resume),
        config,
    )

    # 再次检查是否又遇到了新的中断（链式审批）
    state = await graph.aget_state(config)
    if state.next:
        interrupt_payload = state.tasks[0].interrupts[0].value
        return {
            "status": "interrupted",
            "thread_id": req.thread_id,
            "interrupt": interrupt_payload,
        }

    return {
        "status": "completed",
        "thread_id": req.thread_id,
        "messages": [m.model_dump() for m in state.values["messages"]],
    }


# ── 端点 3：获取当前状态（前端刷新后恢复用）──
@app.get("/state/{thread_id}")
async def get_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    state = await graph.aget_state(config)

    if state.next and state.tasks and state.tasks[0].interrupts:
        return {
            "status": "interrupted",
            "thread_id": thread_id,
            "interrupt": state.tasks[0].interrupts[0].value,
        }

    return {
        "status": "completed",
        "thread_id": thread_id,
        "messages": [m.model_dump() for m in state.values.get("messages", [])],
    }