import uuid
import time
from typing import Any, Dict


def generate_request_id() -> str:
    """生成唯一请求ID"""
    return str(uuid.uuid4())


def format_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200
) -> Dict[str, Any]:
    """格式化API响应"""
    response = {
        "status": "success" if status_code < 400 else "error",
        "message": message,
        "timestamp": int(time.time())
    }
    if data is not None:
        response["data"] = data
    return response


def validate_input(data: Dict[str, Any], required_fields: list) -> bool:
    """验证输入数据是否包含所有必填字段"""
    for field in required_fields:
        if field not in data:
            return False
    return True
