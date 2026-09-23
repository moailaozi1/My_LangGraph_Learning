# LangGraph图定义（含interrupt节点）
from typing_extensions import TypedDict, Annotated
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import interrupt


# 1. 定义图状态
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    approved: bool
    reject_reason: str


# 2. 导入llm
import sys
import os

# 获取当前文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 推算出根目录的绝对路径（根据你的结构，backend退两级到根目录）
root_dir = os.path.abspath(os.path.join(current_dir, "../.."))

# 将根目录插入到系统路径的最前面
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)
from config import model
llm = model

def draft_email(state: State):
    """AI 起草一封邮件"""
    user_msg = state["messages"][-1].content
    response = llm.invoke([
        SystemMessage(content="你是一个邮件助手。根据用户请求起草一封邮件，只输出邮件正文。"),
        HumanMessage(content=user_msg),
    ])
    return {
        "messages": [AIMessage(content=f"已起草邮件：\n\n{response.content}")],
    }


def human_review(state: State):
    """
    人工审核节点 —— 这里会暂停。
    interrupt() 的返回值就是前端传来的决策。
    """
    last_ai_msg = state["messages"][-1].content

    # ★ 关键：调用 interrupt() 让图暂停
    decision = interrupt({
        "action": "send_email",
        "args": {
            "to": "customer@example.com",
            "subject": "关于您的订单",
            "body": last_ai_msg,
        },
        "description": "请审核这封即将发送的邮件。",
    })

    # ⬇️ 以下代码只有在用户审批后才会执行
    decision_type = decision.get("type")

    if decision_type == "approve":
        return {"approved": True}
    elif decision_type == "reject":
        return {"approved": False, "reject_reason": decision.get("message", "")}
    elif decision_type == "edit":
        edited_body = decision.get("editedAction", {}).get("args", {}).get("body", "")
        return {
            "approved": True,
            "messages": [AIMessage(content=f"已用编辑后的内容发送：\n\n{edited_body}")],
        }
    else:
        return {"approved": False}


def send_email(state: State):
    """真正发送邮件（仅在批准后执行）"""
    if state.get("approved"):
        return {"messages": [AIMessage(content="邮件已发送。")]}
    else:
        reason = state.get("reject_reason", "")
        return {"messages": [AIMessage(content=f"邮件未发送。原因：{reason}")]}


def build_graph(checkpointer):
    builder = StateGraph(State)
    builder.add_node("draft_email", draft_email)
    builder.add_node("human_review", human_review)
    builder.add_node("send_email", send_email)

    builder.add_edge(START, "draft_email")
    builder.add_edge("draft_email", "human_review")
    builder.add_edge("human_review", "send_email")
    builder.add_edge("send_email", END)

    return builder.compile(checkpointer=checkpointer)