from langchain_deepseek import ChatDeepSeek
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
    temperature=0.1,
    max_retries=3,
)

# 工厂函数，如果需要得到不同温度，不同模型的deepseek, 可以使用这个函数获取
def get_model(temperature: float = 0.1, model_name: str = "deepseek-flash") -> ChatDeepSeek:
    return ChatDeepSeek(
        api_key=_api_key,
        model=model_name,
        temperature=temperature,
        max_retries=3,
    )
