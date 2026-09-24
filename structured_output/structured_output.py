"""
LangChain 结构化输出完整示例
场景：联系人信息提取 + 产品评论分析
依赖：pip install langchain langchain-openai langgraph pydantic
"""

from typing import Literal, Union, Optional

from langchain_deepseek import ChatDeepSeek
from pydantic import BaseModel, Field
from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy

from dotenv import load_dotenv
from pathlib import Path
import os

# 保证无论从哪个目录运行，都能找到项目根目录的 .env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

_api_key = os.getenv("DEEPSEEK_API_KEY")
if not _api_key:
    raise ValueError("未找到 DEEPSEEK_API_KEY，请检查 .env 文件")

# 模块级单例，所有导入共享同一个实例
model = ChatDeepSeek(
    api_key=_api_key,
    model="deepseek-flash",
    extra_body={"thinking": {"type": "disabled"}} # 禁用思考模式
)
# ============================================================
# 1. 定义 Schema（Pydantic 模型，带字段验证）
# ============================================================

class ContactInfo(BaseModel):
    """Contact information for a person."""
    name: str = Field(description="The name of the person")
    email: str = Field(description="The email address of the person")
    phone: str = Field(description="The phone number of the person")


class ProductReview(BaseModel):
    """Analysis of a product review."""
    rating: Optional[int] = Field(
        description="The rating of the product (1-5)",
        ge=1, le=5
    )
    sentiment: Literal["positive", "negative"] = Field(
        description="The sentiment of the review"
    )
    key_points: list[str] = Field(
        description="The key points of the review. Lowercase, 1-3 words each."
    )


class CustomerComplaint(BaseModel):
    """A customer complaint about a product or service."""
    issue_type: Literal["product", "service", "shipping", "billing"] = Field(
        description="The type of issue"
    )
    severity: Literal["low", "medium", "high"] = Field(
        description="The severity of the complaint"
    )
    description: str = Field(description="Brief description of the complaint")


# ============================================================
# 2. 用 ProviderStrategy（原生策略）
# ============================================================

def demo_provider_strategy():
    print("=" * 60)
    print("演示 1：ProviderStrategy（原生策略）")
    print("=" * 60)

    agent = create_agent(
        model=model,
        response_format=ContactInfo,  # 自动选择 ProviderStrategy
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Extract contact info from: John Doe, john@example.com, (555) 123-4567"
        }]
    })

    contact = result["structured_response"]
    print(f"  姓名: {contact.name}")
    print(f"  邮箱: {contact.email}")
    print(f"  电话: {contact.phone}")


# ============================================================
# 3. 用 ToolStrategy（工具调用策略）
# ============================================================

def demo_tool_strategy():
    print("\n" + "=" * 60)
    print("演示 2：ToolStrategy（工具调用策略）")
    print("=" * 60)

    agent = create_agent(
        model=model,
        tools=[],
        response_format=ToolStrategy(ProductReview),
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Analyze this review: 'Great product: 5 out of 5 stars. Fast shipping, but expensive'"
        }]
    })

    review = result["structured_response"]
    print(f"  评分: {review.rating}")
    print(f"  情感: {review.sentiment}")
    print(f"  要点: {review.key_points}")


# ============================================================
# 4. 用 Union 类型（多个 schema 可选）
# ============================================================

def demo_union_schema():
    print("\n" + "=" * 60)
    print("演示 3：Union 类型（模型自动选择 schema）")
    print("=" * 60)

    agent = create_agent(
        model=model,
        tools=[],
        response_format=ToolStrategy(Union[ProductReview, CustomerComplaint]),
    )

    # 测试 1：评论分析
    result1 = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Analyze this review: 'Great product: 5 out of 5 stars. Fast shipping, but expensive'"
        }]
    })
    print(f"  评论分析: {type(result1['structured_response']).__name__}")
    print(f"  → {result1['structured_response']}")

    # 测试 2：投诉处理
    result2 = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "My package arrived damaged and the shipping took 3 weeks. This is unacceptable!"
        }]
    })
    print(f"  投诉处理: {type(result2['structured_response']).__name__}")
    print(f"  → {result2['structured_response']}")


# ============================================================
# 5. 自定义错误处理
# ============================================================

def demo_custom_error_handler():
    print("\n" + "=" * 60)
    print("演示 4：自定义错误处理")
    print("=" * 60)

    from langchain.agents.structured_output import (
        StructuredOutputValidationError,
        MultipleStructuredOutputsError,
    )

    def custom_error_handler(error: Exception) -> str:
        if isinstance(error, StructuredOutputValidationError):
            return "There was an issue with the format. Try again."
        elif isinstance(error, MultipleStructuredOutputsError):
            return "Multiple structured outputs were returned. Pick the most relevant one."
        else:
            return f"Error: {str(error)}"

    agent = create_agent(
        model=model,
        tools=[],
        response_format=ToolStrategy(
            schema=Union[ContactInfo, ProductReview],
            handle_errors=custom_error_handler,
        ),
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Extract contact info: John Doe, john@example.com"
        }]
    })
    print(f"  结果: {result['structured_response']}")

    # 打印工具消息（查看错误处理过程）
    for msg in result["messages"]:
        if type(msg).__name__ == "ToolMessage":
            print(f"  [ToolMessage] {msg.content}")


# ============================================================
# 6. 自定义工具消息内容
# ============================================================

def demo_custom_tool_message():
    print("\n" + "=" * 60)
    print("演示 5：自定义工具消息内容")
    print("=" * 60)

    agent = create_agent(
        model=model,
        tools=[],
        response_format=ToolStrategy(
            schema=ProductReview,
            tool_message_content="Review analysis complete!",
        ),
    )

    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": "Analyze this: 'Amazing product, 5/5 stars!'"
        }]
    })
    print(f"  结构化结果: {result['structured_response']}")

    for msg in result["messages"]:
        if type(msg).__name__ == "ToolMessage":
            print(f"  [ToolMessage] {msg.content}")


# ============================================================
# 7. 运行所有演示
# ============================================================

if __name__ == "__main__":
    demo_provider_strategy()
    demo_tool_strategy()
    demo_union_schema()
    demo_custom_error_handler()
    demo_custom_tool_message()