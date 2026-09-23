from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END



# 1. 定义状态（包含控制循环条件的字段）
class State(TypedDict):
    """
    Args:
        counter: int # 用于控制循环次数
        current_vale: str # 模拟业务数据 
    """
    counter: int
    current_value: str

# 2. 定义节点函数（接受state，返回dict更新）
def node_a(state: State) -> dict:
    print("--- Running A  ---")
    # 模拟A的逻辑
    return {"current_value": "经过A"}

def node_b(state: State) -> dict:
    print("--- Running B  ---")
    # 模拟B的逻辑
    return {"current_value": "经过B"}


def node_c(state: State) -> dict:
    print("--- Running C  ---")
    # 模拟C的逻辑
    return {"current_value": "经过C"}

def node_d(state: State) -> dict:
    print("--- Running D  ---")
    # 模拟D的逻辑
    return {"counter": state["counter"] + 1, "current_value": "经过D"}

# 3. 定义路由函数（实现有条件转移）
def route_after_d(state: State) -> Literal["a", "b", "__end__"]:
    counter = state["counter"]
    print(f"--- D节点路由判断: 当前数据为{counter} ---")

    # 添加终止条件：达到某个条件就结束，比如设置5次循环
    if counter >= 5:
        return END # 注意这里返回的是__end__
    
    # 业务逻辑 d->a 还是d->b，假设用奇数模拟转移到a，用偶数模拟转移到b
    if counter % 2 == 1:
        print("--- 去往A")
        return "a"
    else:
        print("--- 去往B")
        return "b"
    
# 4. 构建图
builder = StateGraph(State)

# 4.1 添加节点
builder.add_node("a", node_a)
builder.add_node("b", node_b)
builder.add_node("c", node_c)
builder.add_node("d", node_d)

# 4.2 添加静态边
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", "c")
builder.add_edge("c", "d")

# 4.3 添加条件边（实现循环）
builder.add_conditional_edges(
    source="d", # 从d节点出来
    path=route_after_d, # 路由函数
    )

# 5. 编译（开启debug看详细流程）
agent = builder.compile(debug=True)

# 6. 画图流程图
from IPython.display import Image, display
# Show the agent
display(Image(agent.get_graph(xray=True).draw_mermaid_png()))
        
# 7. 执行
if __name__ == "__main__":
    # 初始状态：计数器从0开始
    initial_state = {"counter": 0, "current_value": "start"}
    result = agent.invoke(initial_state)
    print(result)




