# 独立会话转换服务

- 目的：将备份数据转换为 tdata，供机器人端调用实现直登号的登录能力
- 技术栈：Python + FastAPI
- 端点：POST /to-tdata
- 依赖：fastapi、uvicorn、pydantic