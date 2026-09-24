"""
LangChain Streaming 完整示例
场景：天气查询 Agent，同时流式传输多种粒度的更新
依赖：pip install langchain langchain-openai langgraph
"""

import asyncio

from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer


# ============================================================
# 1. 定义工具（带自定义进度输出）
# ============================================================

@tool
def get_weather(city: str) -> str:
    """Get the current weather for a given city."""
    writer = get_stream_writer()
    writer({"status": f"正在查询 {city} 的天气..."})

    # 模拟耗时操作
    import time
    time.sleep(0.5)

    writer({"status": f"已获取 {city} 的天气数据"})
    return f"It's always sunny in {city}!"


@tool
def get_forecast(city: str, days: int = 3) -> str:
    """Get the weather forecast for a city."""
    writer = get_stream_writer()
    for i in range(1, days + 1):
        writer({"status": f"获取 {city} 第 {i} 天预报..."})
        import time
        time.sleep(0.3)
    return f"{city} 未来 {days} 天都是晴天。"


# ============================================================
# 2. 创建 Agent
# ============================================================

from config import model
agent = create_agent(
    model=model,
    tools=[get_weather, get_forecast],
    checkpointer=InMemorySaver(),
)


# ============================================================
# 3. 演示 1：事件流（推荐方式）
# ============================================================

def demo_event_streaming():
    print("=" * 60)
    print("演示 1：事件流（Event Streaming）")
    print("=" * 60)

    config = {"configurable": {"thread_id": "demo-1"}}

    stream = agent.stream_events(
        {"messages": [{"role": "user", "content": "北京今天天气怎么样？"}]},
        version="v3",
        config=config
    )

    for message in stream.messages:
        # 1. 推理过程（增量）
        for delta in message.reasoning:
            print(f"[思考] {delta}", end="", flush=True)

        # 2. 正文（增量）
        for delta in message.text:
            print(delta, end="", flush=True)

        seen_ids = set()
        # 3. 工具调用，看模型如何生成工具调用参数（比如先 {"city": "北，再 {"city": "北京"}），
        for chunk in message.tool_calls:
            cid = chunk.get("id")
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                print(f"\n[工具调用] {chunk['name']} {chunk['args']}")

    # 获取最终状态
    final = stream.output
    print(f"\n\n最终状态包含 {len(final['messages'])} 条消息")


# ============================================================
# 4. 演示 2：传统多模式流
# ============================================================

def demo_multi_mode_stream():
    print("\n" + "=" * 60)
    print("演示 2：传统多模式流（updates + messages + custom）")
    print("=" * 60)

    config = {"configurable": {"thread_id": "demo-2"}}

    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "上海未来3天天气如何？"}]},
        stream_mode=["updates", "messages", "custom"],
        config=config,
    ):
        mode, data = chunk

        if mode == "updates":
            # 状态更新：哪个节点产生了什么更新
            for node_name, update in data.items():
                print(f"\n[更新] 节点 '{node_name}' 输出: {list(update.keys())}")

        elif mode == "messages":
            # LLM token 流：逐个 token 输出
            token, metadata = data
            if token.content:
                print(token.content, end="", flush=True)

        elif mode == "custom":
            # 自定义进度：工具内部发出的状态
            print(f"\n[进度] {data.get('status', data)}")


# ============================================================
# 5. 演示 3：异步流式传输
# ============================================================

async def demo_async_streaming():
    print("\n" + "=" * 60)
    print("演示 3：异步流式传输（astream_events）")
    print("=" * 60)

    config = {"configurable": {"thread_id": "demo-3"}}

    async for event in agent.astream_events(
        {"messages": [{"role": "user", "content": "广州天气如何？"}]},
        version="v2",
        config=config,

    ):
        event_type = event["event"]

        # 只关注关键事件
        if event_type == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                print(chunk.content, end="", flush=True)
        elif event_type == "on_tool_start":
            print(f"\n[工具开始] {event['name']}")
        elif event_type == "on_tool_end":
            print(f"\n[工具结束] {event['name']}: {event['data'].get('output', '')}")


# ============================================================
# 6. 运行所有演示
# ============================================================

if __name__ == "__main__":
    # 演示 1：事件流
    demo_event_streaming()

    # 演示 2：传统多模式流
    demo_multi_mode_stream()

    # 演示 3：异步流
    asyncio.run(demo_async_streaming())