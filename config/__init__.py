# config/__init__.py

# 没有这个文件，需要写到具体的文件名才能导入配置
# from config.llm import model   # 必须写到具体文件名 llm

# 有__init__.py文件
# from config import model       # 直接到包名就行，更简洁 ✅

from .llm import model, get_model
from .db_url import DB_URI

# 控制 from config import * 时导入哪些名字（这个最核心）
__all__ = ["model", "get_model","DB_URI"]