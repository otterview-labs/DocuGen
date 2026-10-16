 # INSERT_YOUR_CODE
import json
import re
import logging

logger = logging.getLogger(__name__)

def extract_json_from_content(content):
    """
    从content中提取JSON字符串并转换为JSON对象。
    支持content为字符串或类似 [{'role': 'assistant', 'content': '...json...'}] 的结构。
    """
    # 如果content是列表，尝试找到'content'字段
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and 'content' in item:
                content_str = item['content']
                break
        else:
            return None
    else:
        content_str = content

    # 用正则提取第一个大括号包裹的json字符串
    match = re.search(r'(\{[\s\S]*\})', content_str)
    if not match:
        return None
    json_str = match.group(1)
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"JSON解析失败: {e}")
        return None

# 示例用法
# 假设 response_plain_text 或 chunk 是上述格式
# result = extract_json_from_content(chunk)
# print(result)
