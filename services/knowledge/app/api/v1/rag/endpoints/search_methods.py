#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索方法信息接口
返回系统支持的所有搜索方法及其详细说明
"""

from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from pydantic import BaseModel, Field

router = APIRouter()


class SearchMethodExample(BaseModel):
    """搜索方法示例"""
    query: str = Field(..., description="示例查询")
    expected_result: str = Field(..., description="预期结果说明")


class SearchMethodInfo(BaseModel):
    """搜索方法信息"""
    mode: str = Field(..., description="搜索模式标识")
    name: str = Field(..., description="搜索方法名称")
    description: str = Field(..., description="方法描述")
    use_case: str = Field(..., description="适用场景")
    performance: Dict[str, Any] = Field(..., description="性能指标")
    features: List[str] = Field(..., description="功能特性")
    examples: List[SearchMethodExample] = Field(..., description="使用示例")
    recommended: bool = Field(False, description="是否推荐")


class SearchMethodsResponse(BaseModel):
    """搜索方法响应"""
    total: int = Field(..., description="方法总数")
    methods: List[SearchMethodInfo] = Field(..., description="搜索方法列表")
    recommendation: str = Field(..., description="推荐说明")


@router.get("/methods", response_model=SearchMethodsResponse)
async def get_search_methods():
    """
    获取所有搜索方法信息 📚

    返回系统支持的所有搜索方法，包括：
    - 方法名称和描述
    - 适用场景
    - 性能指标
    - 使用示例
    - 推荐级别
    """

    # 对外仅保留 5 种模式：intelligent / semantic / keyword / file / image
    methods = [
        SearchMethodInfo(
            mode="intelligent",
            name="智能检索",
            description="系统自动选择最优检索策略（内部可能融合语义、关键词、图谱等增强，但无需手动选择）",
            use_case="适用于大多数场景，特别是用户不确定使用哪种检索方法时",
            performance={
                "latency": "50-500ms（自适应）",
                "accuracy": "高",
                "coverage": "全面",
            },
            features=[
                "自动策略选择",
                "语义理解 + 精确匹配",
                "（可选）跨文档图谱扩展",
                "智能降级",
            ],
            examples=[
                SearchMethodExample(
                    query="JetLinks公司的产品",
                    expected_result="自动识别实体/意图，返回相关产品与文档",
                ),
                SearchMethodExample(
                    query="如何配置MQTT协议",
                    expected_result="自动选择更合适的检索策略，返回配置教程",
                ),
                SearchMethodExample(
                    query="版本号v2.0.1",
                    expected_result="偏向精确匹配，定位包含版本号的文档/片段",
                ),
            ],
            recommended=True,
        ),
        SearchMethodInfo(
            mode="semantic",
            name="语义检索",
            description="基于向量嵌入的语义相似度检索，适合“描述性/概念性”问题",
            use_case="概念查询、同义表达、上下文相关内容查找",
            performance={
                "latency": "100-200ms",
                "accuracy": "高",
                "coverage": "广",
            },
            features=[
                "向量相似度计算",
                "同义词/上下文理解",
                "可选跨文档扩展（enable_graph_expansion）",
            ],
            examples=[
                SearchMethodExample(
                    query="物联网平台的架构设计",
                    expected_result="返回 IoT 平台架构、系统设计、技术架构等相关内容",
                ),
                SearchMethodExample(
                    query="如何提高系统性能",
                    expected_result="返回性能优化、系统调优、性能提升等相关内容",
                ),
            ],
            recommended=False,
        ),
        SearchMethodInfo(
            mode="keyword",
            name="关键词检索",
            description="传统的精确文本匹配，适合已知术语、配置项、错误码等精确定位",
            use_case="查找特定术语、代码、配置项，需要字面匹配",
            performance={
                "latency": "10-50ms",
                "accuracy": "精确",
                "coverage": "有限",
            },
            features=[
                "精确匹配",
                "快速响应",
                "多字段搜索",
            ],
            examples=[
                SearchMethodExample(
                    query="MQTT_BROKER_URL",
                    expected_result="精确找到包含该配置项的文档/片段",
                ),
                SearchMethodExample(
                    query="error code 500",
                    expected_result="找到所有提到错误代码 500 的文档/片段",
                ),
            ],
            recommended=False,
        ),
        SearchMethodInfo(
            mode="file",
            name="文件级检索",
            description="先定位相关文件，再从文件中提取相关片段，保持文档完整性",
            use_case="需要完整文档上下文、报告生成、问答需严格引用",
            performance={
                "latency": "200-400ms",
                "accuracy": "高",
                "coverage": "文件级",
            },
            features=[
                "文件优先",
                "上下文完整",
                "引用标记",
                "文档元数据",
            ],
            examples=[
                SearchMethodExample(
                    query="API文档",
                    expected_result="先找到API文档文件，再提取相关章节，保留文档结构",
                ),
                SearchMethodExample(
                    query="用户手册",
                    expected_result="定位用户手册文件，返回相关章节并保留目录结构",
                ),
            ],
            recommended=False,
        ),
        SearchMethodInfo(
            mode="image",
            name="图搜索",
            description="图片转文本再检索（base64/URL/本地路径），适合以图搜文档/截图找资料",
            use_case="截图搜索、界面/设备图片查资料、以图搜说明书",
            performance={
                "latency": "500-3000ms（取决于图片解析）",
                "accuracy": "中-高（取决于图片质量）",
                "coverage": "取决于文本化质量",
            },
            features=[
                "图片转文本（VLM）",
                "图文混合输入",
                "自动转为文本检索",
            ],
            examples=[
                SearchMethodExample(
                    query="（可选）识别这张图里设备型号并搜索说明书",
                    expected_result="提取图片关键信息后检索相关文档/片段",
                )
            ],
            recommended=False,
        ),
    ]

    return SearchMethodsResponse(
        total=len(methods),
        methods=methods,
        recommendation="推荐默认使用 'intelligent'，只有在需要“更快(关键词)/更准(语义)/文件级引用/图搜索”时再手动选择。"
    )


@router.get("/methods/{mode}", response_model=SearchMethodInfo)
async def get_search_method_by_mode(mode: str):
    """
    获取指定搜索方法的详细信息

    Args:
        mode: 搜索模式标识
    """
    # 获取所有方法
    all_methods = await get_search_methods()

    # 查找指定方法
    for method in all_methods.methods:
        if method.mode == mode:
            return method

    # 未找到
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"搜索方法 '{mode}' 不存在")
