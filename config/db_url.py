from dotenv import load_dotenv
from urllib.parse import quote_plus
import os
# 自动加载项目根目录下的 .env 文件
load_dotenv()

# 读取配置
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT")
db_name = os.getenv("DB_NAME")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")

# 对密码进行 URL 编码（把 @ 变成 %40），再拼接成 DB_URI
# 这样你在 .env 里就能写原始密码了，代码帮你处理编码
encoded_password = quote_plus(db_password)
DB_URI = f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=disable&connect_timeout=5"