#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM增强解析器 - 集成大语言模型实现真正的语义分析能力
支持语义分析、结构理解、内容分类、自动摘要等高级功能
兼容所有OpenAI格式的接口，支持阿里云、腾讯云、百度云等平台
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import requests

from app.shared.utils.http_auth import (
    HTTPAuthConfig,
    apply_auth_headers,
    build_requests_auth,
)

logger = logging.getLogger(__name__)


class LLMEnhancedParser:
    """LLM增强解析器 - 统一走 OpenAI-compatible 接口。"""

    def __init__(
        self,
        model_name: str = "gpt-3.5-turbo",
        api_key: str = None,
        api_base: str = None,
        auth_mode: str = None,
        username: str = None,
        password: str = None,
    ):
        """
        初始化LLM增强解析器

        Args:
            model_name: 使用的模型名称
            api_key: API密钥
            api_base: API基础URL
        """
        # 优先使用显式参数；否则从环境变量读取（兼容历史变量名）
        env_model_name = os.getenv("OPENAI_MODEL_NAME") or os.getenv("LLM_MODEL_NAME") or os.getenv("LLM_MODEL")
        self.model_name = env_model_name if (model_name == "gpt-3.5-turbo" and env_model_name) else model_name

        env_api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        env_auth_mode = os.getenv("OPENAI_API_AUTH_MODE") or os.getenv("LLM_API_AUTH_MODE")
        env_username = os.getenv("OPENAI_API_USERNAME") or os.getenv("LLM_API_USERNAME")
        env_password = os.getenv("OPENAI_API_PASSWORD") or os.getenv("LLM_API_PASSWORD")
        self.auth_config = HTTPAuthConfig.build(
            mode=auth_mode or env_auth_mode,
            api_key=api_key or env_api_key,
            username=username or env_username,
            password=password or env_password,
            default_mode="bearer",
        )
        self.api_key = self.auth_config.api_key

        # 只有在明确提供api_base时才使用环境变量
        if api_base is None:
            env_api_base = os.getenv("OPENAI_API_BASE") or os.getenv("LLM_API_BASE") or os.getenv("LLM_BASE_URL")
            # 忽略disabled值
            self.api_base = None if (env_api_base or "").strip().lower() == "disabled" else env_api_base
        else:
            self.api_base = api_base

        # 将 OPENAI_API_BASE 统一视为「API base」（通常以 /v1 结尾），这里标准化得到 chat/completions 端点
        self._openai_chat_endpoint = self._normalize_openai_chat_endpoint(
            self.api_base or "https://api.openai.com/v1"
        )
        self.platform = self._detect_platform()

        if self.auth_config.mode == "bearer" and not self.api_key:
            logger.warning("未配置LLM API密钥，LLM功能将不可用")

        logger.info(f"LLM增强解析器初始化完成，平台: {self.platform}, 模型: {self.model_name}")

    @staticmethod
    def _normalize_openai_chat_endpoint(api_base: Optional[str]) -> Optional[str]:
        """将 API base 或完整 endpoint 规范化为 `/chat/completions` 端点。"""
        if not api_base:
            return None

        u = str(api_base).strip()
        if not u:
            return None

        u = u.rstrip("/")
        # 若已经是完整端点，直接返回
        if u.endswith("/chat/completions"):
            return u

        # 处理常见 base：
        # - https://api.openai.com/v1
        # - http://host:8899/v1
        # - http://host:8899
        if u.endswith("/v1"):
            return f"{u}/chat/completions"
        return f"{u}/v1/chat/completions"

    def _detect_platform(self) -> str:
        """自动检测平台类型"""
        if self.api_base:
            # 若显式配置了 base_url，一律视为 OpenAI-compatible（本地/代理/第三方均可）
            return "custom"
        else:
            return "openai"

    def call_llm_api(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.3,
        response_format: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        调用LLM API

        Args:
            prompt: 提示词
            max_tokens: 最大token数
            temperature: 温度参数
            response_format: OpenAI-compatible response_format，例如 {"type": "json_object"}
            system_prompt: 可选系统提示词

        Returns:
            API响应结果
        """
        if self.auth_config.mode == "bearer" and not self.api_key:
            return {"error": "LLM API密钥未配置"}

        try:
            data = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt or "你是一个专业的文档分析专家，擅长深度语义分析和内容理解。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            if response_format:
                data["response_format"] = response_format
            headers = apply_auth_headers({"Content-Type": "application/json"}, self.auth_config)

            # 禁用代理，避免SSL问题
            proxies = {"http": None, "https": None}
            timeout = float(os.getenv("LLM_API_TIMEOUT", "30"))

            response = requests.post(
                self._openai_chat_endpoint,
                headers=headers,
                json=data,
                timeout=timeout,
                proxies=proxies,
                auth=build_requests_auth(self.auth_config),
            )

            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                else:
                    return {"error": "OpenAI-compatible API响应格式错误"}

                return {
                    "success": True,
                    "content": content,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            else:
                return {"error": f"API调用失败: {response.status_code} - {response.text}"}

        except Exception as e:
            logger.error(f"LLM API调用失败: {e}")
            return {"error": str(e)}

    def analyze_semantics(self, content: str) -> Dict[str, Any]:
        """
        使用LLM进行语义分析

        Args:
            content: 文档内容

        Returns:
            语义分析结果
        """
        prompt = f"""
请对以下文档内容进行深度语义分析，包括：

1. 文档主题和核心内容
2. 主要章节结构
3. 关键概念和术语
4. 文档类型和用途
5. 重要信息提取
6. 内容质量评估

文档内容：
{content[:4000]}  # 限制长度避免token超限

请以JSON格式返回分析结果，包含以下字段：
- theme: 文档主题
- main_topics: 主要话题列表
- key_concepts: 关键概念列表
- document_type: 文档类型
- purpose: 文档用途
- structure: 章节结构
- important_info: 重要信息
- quality_score: 内容质量评分(0-10)
- summary: 智能摘要
"""

        result = self.call_llm_api(prompt, max_tokens=2000, temperature=0.3)

        if result.get("success"):
            try:
                analysis_result = json.loads(result["content"])
                return {
                    "success": True,
                    "analysis": analysis_result,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "analysis": {
                        "raw_analysis": result["content"],
                        "theme": "自动提取的主题",
                        "summary": result["content"][:500]
                    },
                    "model_used": self.model_name,
                    "platform": self.platform
                }
        else:
            return result

    def understand_structure(self, content: str) -> Dict[str, Any]:
        """
        使用LLM进行结构理解

        Args:
            content: 文档内容

        Returns:
            结构理解结果
        """
        prompt = f"""
请深度分析以下文档的结构，包括：

1. 文档层次结构
2. 各部分之间的关系
3. 逻辑流程分析
4. 信息组织方式
5. 结构特点

文档内容：
{content[:3000]}

请以JSON格式返回分析结果，包含以下字段：
- hierarchy: 层次结构
- relationships: 各部分关系
- logic_flow: 逻辑流程
- organization: 信息组织方式
- structure_features: 结构特点
- complexity_score: 结构复杂度(1-10)
"""

        result = self.call_llm_api(prompt, max_tokens=1500, temperature=0.2)

        if result.get("success"):
            try:
                structure_result = json.loads(result["content"])
                return {
                    "success": True,
                    "structure": structure_result,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "structure": {
                        "raw_analysis": result["content"],
                        "hierarchy": "自动提取的层次结构",
                        "complexity_score": 5
                    },
                    "model_used": self.model_name,
                    "platform": self.platform
                }
        else:
            return result

    def classify_content(self, content: str) -> Dict[str, Any]:
        """
        使用LLM进行内容分类

        Args:
            content: 文档内容

        Returns:
            内容分类结果
        """
        prompt = f"""
请对以下文档内容进行详细分类，包括：

1. 文档类型分类
2. 内容领域分类
3. 目标受众分析
4. 写作风格分析
5. 专业程度评估
6. 内容标签

文档内容：
{content[:3000]}

请以JSON格式返回分类结果，包含以下字段：
- document_category: 文档类型
- domain: 内容领域
- target_audience: 目标受众
- writing_style: 写作风格
- expertise_level: 专业程度(初级/中级/高级)
- content_tags: 内容标签列表
- confidence_score: 分类置信度(0-1)
"""

        result = self.call_llm_api(prompt, max_tokens=1000, temperature=0.1)

        if result.get("success"):
            try:
                classification_result = json.loads(result["content"])
                return {
                    "success": True,
                    "classification": classification_result,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "classification": {
                        "raw_analysis": result["content"],
                        "document_category": "自动分类",
                        "content_tags": ["自动标签"]
                    },
                    "model_used": self.model_name,
                    "platform": self.platform
                }
        else:
            return result

    def generate_summary(self, content: str, summary_type: str = "comprehensive") -> Dict[str, Any]:
        """
        使用LLM生成智能摘要

        Args:
            content: 文档内容
            summary_type: 摘要类型 (comprehensive/executive/key_points)

        Returns:
            摘要生成结果
        """
        summary_prompts = {
            "comprehensive": "请生成一份全面的文档摘要，包含主要观点、关键信息和重要结论。",
            "executive": "请生成一份执行摘要，突出最重要的信息和建议。",
            "key_points": "请提取文档的关键要点，以列表形式呈现。"
        }

        prompt = f"""
{summary_prompts.get(summary_type, summary_prompts['comprehensive'])}

文档内容：
{content[:4000]}

请生成高质量的摘要，要求：
1. 保持原文的核心信息
2. 逻辑清晰，结构合理
3. 语言简洁准确
4. 突出重要内容

请以JSON格式返回结果，包含以下字段：
- summary: 摘要内容
- key_points: 关键要点
- word_count: 摘要字数
- coverage_score: 内容覆盖度(0-1)
"""

        result = self.call_llm_api(prompt, max_tokens=1500, temperature=0.3)

        if result.get("success"):
            try:
                summary_result = json.loads(result["content"])
                return {
                    "success": True,
                    "summary": summary_result,
                    "summary_type": summary_type,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "summary": {
                        "summary": result["content"],
                        "key_points": ["自动提取的关键要点"],
                        "word_count": len(result["content"]),
                        "coverage_score": 0.8
                    },
                    "summary_type": summary_type,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
        else:
            return result

    def extract_insights(self, content: str) -> Dict[str, Any]:
        """
        使用LLM提取深度洞察

        Args:
            content: 文档内容

        Returns:
            洞察提取结果
        """
        prompt = f"""
请对以下文档内容进行深度分析，提取有价值的洞察，包括：

1. 隐含信息和趋势
2. 潜在问题和风险
3. 机会和建议
4. 创新点和亮点
5. 改进建议

文档内容：
{content[:3500]}

请以JSON格式返回分析结果，包含以下字段：
- hidden_insights: 隐含洞察
- trends: 趋势分析
- risks: 潜在风险
- opportunities: 机会点
- innovations: 创新点
- recommendations: 改进建议
- insight_score: 洞察价值评分(0-10)
"""

        result = self.call_llm_api(prompt, max_tokens=2000, temperature=0.4)

        if result.get("success"):
            try:
                insights_result = json.loads(result["content"])
                return {
                    "success": True,
                    "insights": insights_result,
                    "model_used": self.model_name,
                    "platform": self.platform
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "insights": {
                        "raw_analysis": result["content"],
                        "hidden_insights": ["自动提取的洞察"],
                        "insight_score": 7
                    },
                    "model_used": self.model_name,
                    "platform": self.platform
                }
        else:
            return result

    def comprehensive_analysis(self, content: str) -> Dict[str, Any]:
        """
        综合LLM分析 - 包含所有高级功能

        Args:
            content: 文档内容

        Returns:
            综合分析结果
        """
        try:
            result = {
                "semantic_analysis": self.analyze_semantics(content),
                "structure_understanding": self.understand_structure(content),
                "content_classification": self.classify_content(content),
                "summary": self.generate_summary(content),
                "insights": self.extract_insights(content)
            }

            # 计算综合评分
            scores = []
            for key, analysis in result.items():
                if analysis.get("success"):
                    if "analysis" in analysis and "quality_score" in analysis["analysis"]:
                        scores.append(analysis["analysis"]["quality_score"])
                    elif "structure" in analysis and "complexity_score" in analysis["structure"]:
                        scores.append(analysis["structure"]["complexity_score"])
                    elif "classification" in analysis and "confidence_score" in analysis["classification"]:
                        scores.append(analysis["classification"]["confidence_score"] * 10)
                    elif "summary" in analysis and "coverage_score" in analysis["summary"]:
                        scores.append(analysis["summary"]["coverage_score"] * 10)
                    elif "insights" in analysis and "insight_score" in analysis["insights"]:
                        scores.append(analysis["insights"]["insight_score"])

            if scores:
                result["overall_score"] = sum(scores) / len(scores)
            else:
                result["overall_score"] = 7.0

            return {
                "success": True,
                "comprehensive_analysis": result,
                "model_used": self.model_name,
                "platform": self.platform
            }

        except Exception as e:
            logger.error(f"综合LLM分析失败: {e}")
            return {"error": str(e)}


class LocalLLMParser:
    """本地LLM解析器 - 使用开源模型"""

    def __init__(self, model_endpoint: str = None):
        """
        初始化本地LLM解析器

        Args:
            model_endpoint: 本地模型端点
        """
        self.model_endpoint = model_endpoint or os.getenv("LOCAL_LLM_ENDPOINT")
        self.available = bool(self.model_endpoint)

        if self.available:
            logger.info(f"本地LLM解析器初始化完成，端点: {self.model_endpoint}")
        else:
            logger.warning("未配置本地LLM端点，本地LLM功能不可用")

    def call_local_model(self, prompt: str) -> Dict[str, Any]:
        """
        调用本地模型

        Args:
            prompt: 提示词

        Returns:
            模型响应
        """
        if not self.available:
            return {"error": "本地LLM不可用"}

        try:
            response = requests.post(
                self.model_endpoint,
                json={
                    "prompt": prompt,
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("response", ""),
                    "model": "local_llm"
                }
            else:
                return {"error": f"本地LLM调用失败: {response.status_code}"}

        except Exception as e:
            logger.error(f"本地LLM调用失败: {e}")
            return {"error": str(e)}

    def analyze_semantics(self, content: str) -> Dict[str, Any]:
        """使用本地LLM进行语义分析"""
        prompt = f"""
请对以下文档内容进行语义分析：

{content[:3000]}

请分析：
1. 文档主题
2. 主要内容
3. 关键概念
4. 文档类型
5. 重要信息

请以JSON格式返回结果。
"""

        result = self.call_local_model(prompt)
        if result.get("success"):
            try:
                analysis = json.loads(result["response"])
                return {
                    "success": True,
                    "analysis": analysis,
                    "model": "local_llm"
                }
            except:
                return {
                    "success": True,
                    "analysis": {
                        "theme": "自动提取的主题",
                        "summary": result["response"][:500]
                    },
                    "model": "local_llm"
                }
        else:
            return result


class HybridParser:
    """混合解析器 - 结合规则和LLM"""

    def __init__(self, use_llm: bool = True, llm_parser: LLMEnhancedParser = None):
        """
        初始化混合解析器

        Args:
            use_llm: 是否使用LLM
            llm_parser: LLM解析器实例
        """
        self.use_llm = use_llm
        self.llm_parser = llm_parser or LLMEnhancedParser()
        self.local_parser = LocalLLMParser()

        logger.info("混合解析器初始化完成")

    def analyze_document(self, content: str) -> Dict[str, Any]:
        """
        混合分析文档

        Args:
            content: 文档内容

        Returns:
            混合分析结果
        """
        result = {
            "rule_based_analysis": self._rule_based_analysis(content),
            "llm_analysis": {},
            "hybrid_insights": {}
        }

        # 如果启用LLM，进行深度分析
        if self.use_llm and self.llm_parser.api_key:
            try:
                llm_result = self.llm_parser.comprehensive_analysis(content)
                if llm_result.get("success"):
                    result["llm_analysis"] = llm_result.get("comprehensive_analysis", {})

                    # 生成混合洞察
                    result["hybrid_insights"] = self._generate_hybrid_insights(
                        result["rule_based_analysis"],
                        result["llm_analysis"]
                    )
            except Exception as e:
                logger.warning(f"LLM分析失败，使用规则分析: {e}")

        # 如果LLM不可用，尝试本地LLM
        elif self.use_llm and self.local_parser.available:
            try:
                local_result = self.local_parser.analyze_semantics(content)
                if local_result.get("success"):
                    result["llm_analysis"] = {"semantic_analysis": local_result}
            except Exception as e:
                logger.warning(f"本地LLM分析失败: {e}")

        return result

    def _rule_based_analysis(self, content: str) -> Dict[str, Any]:
        """基于规则的分析"""
        return {
            "word_count": len(content),
            "sentence_count": len(re.split(r'[。！？.!?]', content)),
            "paragraph_count": len([p for p in content.split('\n\n') if p.strip()]),
            "has_tables": '|' in content or '\t' in content,
            "has_code": '```' in content or '    ' in content,
            "has_lists": bool(re.search(r'^[\s]*[•\-\*\d]+\.?\s', content, re.MULTILINE))
        }

    def _generate_hybrid_insights(self, rule_analysis: Dict, llm_analysis: Dict) -> Dict[str, Any]:
        """生成混合洞察"""
        insights = {
            "document_complexity": "medium",
            "analysis_confidence": "high",
            "recommended_actions": []
        }

        # 基于规则和LLM结果生成洞察
        if rule_analysis.get("word_count", 0) > 1000:
            insights["document_complexity"] = "high"

        if llm_analysis.get("semantic_analysis", {}).get("analysis", {}).get("quality_score", 0) > 7:
            insights["analysis_confidence"] = "high"

        return insights
