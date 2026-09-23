from urllib import response


from typing import TypedDict, Literal
from langgraph.graph import StateGraph, START, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from IPython.display import Image, display




# 1. 定义状态
class ContentState(TypedDict):
    """内容优化工作流的状态"""
    original_content: str       # 原始投稿内容
    current_content: str        # 当前版本内容
    evaluation_result: str      # LLM的评估结果文本
    scores: dict                # 各维度评分 {"完整性": 7, "逻辑性": 6}
    is_qualified: bool          # 是否达标 True
    iteration: int              # 当前迭代次数
    max_iterations: int          # 最大迭代次数（防止死循环）
    final_output: str           # 最终输出结果

# 2. 初始化模型
from config import model
llm = model

# 3. 定义节点
def initial_review(state: ContentState) -> dict:
    """
    初审节点：接受原始内容，初始化状态
    """

    print(f"📝 [初审] 收到投稿，字数: {len(state['original_content'])}")
    return {
        "current_content": state["original_content"],
        "iteration": 0,
        "is_qualified": False,
    }

def evaluate_content(state: ContentState) -> dict:
    """
    质量评估节点：调用LLM对当前内容进行多维度评分
    """

    content = state["current_content"]
    iteration  = state["iteration"] + 1     # 本轮是第几次评估

    # 构建评估prompt
    eval_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content="""你是一位资深内容质量审核专家。请从以下维度对内容进行评分（1-10分）：
        1. 完整性：信息是否完整，有没有遗漏关键点
        2. 逻辑性：逻辑是否清晰，结构是否合理
        3. 吸引力：开头是否吸引人，语言是否有感染力
        4. SEO友好度：关键词覆盖是否充分
        5. 可读性：语言是否流畅，是否易于理解
        
        请输出 JSON 格式：
        {"scores": {"完整性": X, "逻辑性": X, ...}, "is_qualified": true/false, "comment": "总体评价"}
        达标标准：所有维度 >= 7 分
        """),
        HumanMessage(content=f"请评估以下内容：\n\n{content}")
    ])

    response = llm.invoke(eval_prompt.format_messages())

    # 简单解析（生产环境建议用 Pydantic 结构化输出）
    import json
    try:
        result = json.loads(response.content)
        scores = result.get("scores", {})
        is_qualified = result.get("is_qualified", False)
        comment = result.get("comment", "")
    except:
        # 容错处理
        scores = {"完整性": 5, "逻辑性": 5, "吸引力": 5, "SEO友好度": 5, "可读性": 5}
        is_qualified = False
        comment = "解析失败，默认不达标"

    avg_score = sum(scores.values()) / len(scores) if scores else 0
    print(f"   📊 平均分: {avg_score:.1f}, 达标: {'✅' if is_qualified else '❌'}")

    return {
        "scores": scores,
        "is_qualified": is_qualified,
        "evaluation_result": comment,
        "iteration": iteration,
    }

def optimize_content(state: ContentState) -> dict:
    """
    内容优化节点：根据评估意见，调用 LLM 重写/优化内容
    """
    content = state["current_content"]
    eval_result = state["evaluation_result"]
    scores = state["scores"]
    iteration = state["iteration"]
    
    print(f"✍️  [优化] 第 {iteration} 轮优化开始...")
    
    # 找出最低分的维度
    if scores:
        lowest_dim = min(scores, key=scores.get)
        lowest_score = scores[lowest_dim]
    else:
        lowest_dim = "内容质量"
        lowest_score = 0
    
    optimize_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=f"""你是一位专业的文案优化专家。
        当前内容在「{lowest_dim}」维度得分仅为 {lowest_score}/10，需要重点改进。
        评估意见：{eval_result}
        
        请重写/优化内容，重点提升薄弱维度，同时保持原有核心信息不变。
        直接输出优化后的完整内容，不要添加额外说明。
        """),
        HumanMessage(content=f"原始内容：\n\n{content}")
    ])
    
    response = llm.invoke(optimize_prompt.format_messages())
    optimized = response.content
    
    print(f"   ✅ 优化完成，新内容长度: {len(optimized)} 字符")
    
    return {
        "current_content": optimized,
    }


def should_continue(state: ContentState) -> Literal["optimize", END]:
    """
    条件判断节点：决定是继续优化还是结束
    """
    is_qualified = state["is_qualified"]
    iteration = state["iteration"]
    max_iter = state.get("max_iterations", 5)

    print(f"🧭 [路由判断] 迭代 {iteration}/{max_iter}, 达标: {is_qualified}")
    
    # 条件1：质量达标 → 结束
    if is_qualified:
        print("   ✅ 质量达标，结束循环")
        return END
    
    # 条件2：超过最大迭代次数 → 结束（输出当前最优版本）
    if iteration >= max_iter:
        print(f"   ⚠️ 达到最大迭代次数 {max_iter}，强制结束")
        return END
    
    # 条件3：未达标且未超限 → 继续优化
    print(f"   🔄 继续优化（第 {iteration + 1} 轮）")
    return "optimize"

# 4. 构建图
def build_content_optimizer():
    builder = StateGraph(ContentState)
    
    # 添加节点
    builder.add_node("initial_review", initial_review)
    builder.add_node("evaluate", evaluate_content)
    builder.add_node("optimize", optimize_content)
    
    # 添加边
    builder.add_edge(START, "initial_review")
    builder.add_edge("initial_review", "evaluate")
    
    # ⭐ 关键：条件边实现循环
    builder.add_conditional_edges(
        source="evaluate",
        path=should_continue,        # 路由函数
        # path_map 可省略，因为路由函数直接返回节点名字符串
    )
    
    # optimize 执行完后回到 evaluate（再次评估）
    builder.add_edge("optimize", "evaluate")
    
    return builder.compile()





if __name__ == "__main__":
    app = build_content_optimizer()

    # 画一个编译后的流程图
    display(Image(app.get_graph(xray=True).draw_mermaid_png()))

    # 模拟一篇质量一般的投稿
    test_content = """
    我们的新产品智能保温杯即将上市。这款杯子采用不锈钢材质，可以保温。
    价格实惠，欢迎大家购买。具体参数请查看官网。
    """
    
    print("=" * 60)
    print("🚀 开始内容优化工作流")
    print("=" * 60)
    
    result = app.invoke({
        "original_content": test_content,
        "max_iterations": 3,  # 最多优化3轮
    })
    
    print("\n" + "=" * 60)
    print("📄 最终结果")
    print("=" * 60)
    print(f"原始内容:\n{test_content}\n")
    print(f"优化后内容:\n{result['current_content']}\n")
    print(f"迭代次数: {result['iteration']}")
    print(f"最终评分: {result.get('scores', {})}")
    print(f"是否达标: {'✅ 是' if result.get('is_qualified') else '❌ 否（已达最大迭代）'}")