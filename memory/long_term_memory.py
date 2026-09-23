"""
LangGraph 长期记忆（PostgresStore + 本地 vLLM bge-m3）完整示例
场景：跨对话窗口记住用户偏好，数据持久化到 PostgreSQL
依赖：uv add "psycopg[binary,pool]" langgraph langgraph-checkpoint-postgres langchain langchain-openai
前置：
  1. docker启动pgvector:pg18 带pgvector的postgresql环境
  docker run -d --name pgvector-db   -e POSTGRES_PASSWORD=xxx   -e POSTGRES_DB=my_test_db   -p 5433:5432   pgvector/pgvector:pg18
  2. vLLM 已启动 bge-m3：
vllm serve seansitter/bge-m3-safetensors \
  --runner pooling \
  --load-format safetensors \
  --model-impl transformers \
  --trust-remote-code \
  --max-model-len 8192 \
  --port 8001 \
  --gpu-memory-utilization 0.3 \
  --enforce-eager  # 纯pytorch模式运行
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from typing_extensions import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.postgres import PostgresStore
from langgraph.runtime import Runtime


# ============================================================
# 1. 初始化模型和嵌入模型
# ============================================================

from config import model
llm = model

# 嵌入模型用于语义搜索：把文字转成向量，按"含义"而非"字面"检索
embeddings = OpenAIEmbeddings(
    model="seansitter/bge-m3-safetensors",                          # 与 --served-model-name 一致
    openai_api_base="http://localhost:8001/v1",  # vLLM 服务地址
    openai_api_key="EMPTY",                  # vLLM 不校验 key，填任意值即可
)

# ============================================================
# 2. PostgreSQL 连接字符串
# ============================================================
from config import DB_URI


# ============================================================
# 3. 定义 Context（携带 user_id，用于构建命名空间）
# ============================================================
@dataclass
class Context:
    user_id: str


# ============================================================
# 4. 定义 State
# ============================================================
class State(TypedDict):
    messages: Annotated[list, add_messages]


# ============================================================
# 5. 节点一：从对话中提取并保存记忆
# ============================================================
def save_memory(state: State, runtime: Runtime[Context]):
    """把用户最新一句话中值得记住的信息存入 Store"""
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")

    # 取最近一条用户消息
    last_user_msg = None
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    if not last_user_msg:
        return {}

    # 用 LLM 判断这句话里有没有值得长期记住的信息
    extraction_prompt = f"""从下面这句话中提取用户偏好或个人信息。
如果没有值得长期记住的信息，回复"无"。
只输出提取到的信息，不要解释。

用户说：{last_user_msg}"""

    extracted = llm.invoke([HumanMessage(content=extraction_prompt)]).content.strip()

    if extracted and extracted != "无":
        # 写入 Store：命名空间 + 唯一键 + 值
        runtime.store.put(
            namespace,
            str(uuid.uuid4()),          # 每条记忆一个唯一 key
            {"memory": extracted},       # value 是字典
        )
        print(f"  [已保存记忆] {extracted}")

    return {}


# ============================================================
# 6. 节点二：检索相关记忆并生成回复
# ============================================================
def call_model(state: State, runtime: Runtime[Context]):
    """先检索长期记忆，再结合当前对话生成回复"""
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")

    # 取最新一条用户消息作为查询
    query = state["messages"][-1].content

    # 语义搜索：按含义找回最相关的 3 条记忆
    memories = runtime.store.search(
        namespace,
        query=query,
        limit=3,
    )

    # 拼接记忆文本
    memory_text = "\n".join([m.value["memory"] for m in memories]) if memories else "（暂无记忆）"
    if memory_text != "（暂无记忆）":
        print(f"  [召回记忆]\n{memory_text}")

    # 把记忆作为系统提示注入
    system_msg = SystemMessage(
        content=f"""你是一个贴心的助手。以下是关于用户的长期记忆：

{memory_text}

请结合这些记忆回答用户问题。如果记忆为空，就正常回答。"""
    )

    response = llm.invoke([system_msg, *state["messages"]])
    return {"messages": [response]}


# ============================================================
# 7. 构建图
# ============================================================
builder = StateGraph(State, context_schema=Context)

builder.add_node("save_memory", save_memory)
builder.add_node("call_model", call_model)

builder.add_edge(START, "save_memory")
builder.add_edge("save_memory", "call_model")
builder.add_edge("call_model", END)




# ============================================================
# 8. 运行演示
# ============================================================
def chat(thread_id: str, user_id: str, message: str):
    """封装一次对话调用"""
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=config,
        context=Context(user_id=user_id),
    )
    reply = result["messages"][-1].content
    print(f"用户: {message}")
    print(f"助手: {reply}\n")
    return reply


if __name__ == "__main__":
    USER_ID = "user_001"

    # 用 PostgresStore 作为长期记忆，启用语义搜索
    with PostgresStore.from_conn_string(
            DB_URI,
            index={
                "embed": embeddings,  # 本地 vLLM 的 bge-m3
                "dims": 1024,  # bge-m3 输出 1024 维
                "fields": ["memory"],  # 只嵌入 memory 字段
            },
    ) as store:
        # 首次运行时取消注释，建表 + 迁移
        store.setup()

        checkpointer = InMemorySaver()
        graph = builder.compile(checkpointer=checkpointer, store=store)

        print("=" * 60)
        print("对话窗口 1（thread_id = 'chat_1'）")
        print("=" * 60)
        chat("chat_1", USER_ID, "你好，我叫小明，我喜欢吃披萨，讨厌香菜")
        chat("chat_1", USER_ID, "我最近在学 Python")

        print("=" * 60)
        print("对话窗口 2（thread_id = 'chat_2'）—— 全新线程")
        print("=" * 60)
        chat("chat_2", USER_ID, "你还记得我喜欢吃什么吗？")
        chat("chat_2", USER_ID, "我在学什么来着？")