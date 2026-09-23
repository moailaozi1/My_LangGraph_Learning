import time
start_total = time.perf_counter()

# 1. 导入阶段耗时
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.checkpoint.postgres import PostgresSaver
# 初始化模型
from config import model
# PostgreSQL 连接字符串
from config import DB_URI

t_import = time.perf_counter()
print(f"【导入依赖与模型】耗时: {t_import - start_total:.2f}s")

# 2. 数据库连接与 setup 阶段
t_db_start = time.perf_counter()
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # checkpointer.setup() # 只第一次跑，之后可注掉
    t_db_ready = time.perf_counter()
    print(f"【数据库连接与 setup】耗时: {t_db_ready - t_db_start:.2f}s")



    def call_model(state: MessagesState):
        return {"messages": model.invoke(state["messages"])}


    # 编译 graph
    t_compile_start = time.perf_counter()
    builder = StateGraph(MessagesState)
    builder.add_node(call_model)
    builder.add_edge(START, "call_model")
    graph = builder.compile(checkpointer=checkpointer)
    t_compile = time.perf_counter()
    print(f"【图编译】耗时: {t_compile - t_compile_start:.2f}s")

    config = {"configurable": {"thread_id": "1"}}
    def chat(user_input):
        t = time.perf_counter()
        out = graph.invoke({"messages": [{"role": "user", "content": user_input}]}, config)
        print(f"User: {user_input}\nAI  : {out['messages'][-1].content}")
        print(f"耗时 {time.perf_counter()-t:.2f}s\n")

    chat("hi! I'm bob")
    chat("what's my name?")

# 3. 退出阶段耗时
t_end = time.perf_counter()
print(f"【退出与清理】总耗时: {t_end - start_total:.2f}s")