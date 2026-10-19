#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milvus向量库实现
"""

import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from datetime import datetime

try:
    from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

from app.core.rag.vector_db.base import VectorDBBase
from app.config import settings

logger = logging.getLogger(__name__)


class MilvusVectorDB(VectorDBBase):
    """Milvus向量库实现"""

    def __init__(self):
        if not MILVUS_AVAILABLE:
            raise ImportError("pymilvus库未安装，请安装: pip install pymilvus")

        self.host = settings.vector_db.MILVUS_HOST
        self.port = settings.vector_db.MILVUS_PORT
        self.user = settings.vector_db.MILVUS_USER
        self.password = settings.vector_db.MILVUS_PASSWORD
        self.db = settings.vector_db.MILVUS_DB
        self.dimension = settings.vector_db.VECTOR_DB_DIMENSION
        self.nprobe = getattr(settings.vector_db, "MILVUS_NPROBE", 15) or 15

        # 连接Milvus
        self._connect()

    def _connect(self):
        """连接Milvus"""
        try:
            # 先断开可能存在的旧连接
            try:
                connections.disconnect("default")
            except:
                pass

            # 选择连接方式：优先使用 URI（HTTP/HTTPS），否则使用 host/port（gRPC）
            use_http = False
            uri = getattr(settings.vector_db, 'MILVUS_URI', '') or ''
            if uri.strip():
                use_http = True
            # 常见场景：端口19531为HTTP
            if int(self.port) == 19531:
                use_http = True
                if not uri.strip():
                    uri = f"http://{self.host}:{self.port}"
            # 环境强制开关
            try:
                if getattr(settings.vector_db, 'MILVUS_USE_HTTP', False) and not uri.strip():
                    uri = f"http://{self.host}:{self.port}"
                    use_http = True
            except Exception:
                pass

            if use_http:
                # 通过URI连接（PyMilvus在支持HTTP的版本中使用该参数）
                if self.user and self.password:
                    connections.connect(
                        alias="default",
                        uri=uri,
                        user=self.user,
                        password=self.password,
                        db_name=self.db
                    )
                else:
                    connections.connect(
                        alias="default",
                        uri=uri,
                        db_name=self.db
                    )
            else:
                # gRPC 连接
                if self.user and self.password:
                    connections.connect(
                        alias="default",
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        db_name=self.db
                    )
                else:
                    connections.connect(
                        alias="default",
                        host=self.host,
                        port=self.port,
                        db_name=self.db
                    )
            logger.info("Milvus连接成功")
        except Exception as e:
            logger.error(f"Milvus连接失败: {e}")
            raise

    def _get_collection_name(self, collection_name: str) -> str:
        """将业务层的 collection_id 规范化为 Milvus 可接受的名称。

        规则：
        1. 纯数字ID添加col_前缀
        2. 以数字开头的添加col_前缀
        3. 只允许字母、数字、下划线
        4. 其余字符统一替换为下划线
        """
        try:
            from app.core.rag.collection_validator import validate_and_fix_collection_name

            # 使用验证器处理集合名称
            valid_name = validate_and_fix_collection_name(collection_name or "")

            if valid_name != collection_name:
                logger.debug(f"集合名称 {collection_name} 修正为 {valid_name}")

            return valid_name
        except ImportError:
            # 如果验证器模块不存在，使用简单规则
            import re
            safe = collection_name or ""

            # 处理纯数字的情况
            if safe.isdigit():
                safe = f"col_{safe[:8]}"  # 使用前8位
            # 处理以数字开头的情况
            elif safe and safe[0].isdigit():
                safe = f"col_{safe}"

            # 替换非法字符
            safe = re.sub(r"[^A-Za-z0-9_]", "_", safe)

            return safe or "default"
        except Exception as e:
            logger.warning(f"集合名称处理异常: {e}")
            return "default"

    def create_collection(self, collection_name: str, dimension: int = 1536, **kwargs) -> bool:
        """创建集合"""
        try:
            full_collection_name = self._get_collection_name(collection_name)

            if utility.has_collection(full_collection_name):
                logger.warning(f"集合 {full_collection_name} 已存在")
                return True

            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50)
            ]

            # 创建集合模式
            schema = CollectionSchema(fields, description=f"RAG collection: {collection_name}")

            # 创建集合
            collection = Collection(full_collection_name, schema)

            # 创建索引
            index_params = {
                "metric_type": "IP",  # 内积
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            collection.create_index("vector", index_params)

            logger.info(f"创建Milvus集合 {full_collection_name} 成功")
            return True

        except Exception as e:
            logger.error(f"创建Milvus集合失败: {e}")
            return False

    def collection_exists(self, collection_name: str) -> bool:
        """检查集合是否存在"""
        try:
            # 确保连接有效
            self._ensure_connection()
            full_collection_name = self._get_collection_name(collection_name)
            return utility.has_collection(full_collection_name)
        except Exception as e:
            logger.error(f"检查集合存在性失败: {e}")
            return False

    def _ensure_connection(self):
        """确保Milvus连接有效"""
        try:
            # 尝试一个简单操作来验证连接
            utility.list_collections()
        except Exception:
            # 连接失效或不存在，重新连接
            logger.debug("Milvus连接失效，重新连接...")
            self._connect()

    def list_collections(self) -> List[str]:
        """列出所有集合（直接返回实际集合名）。"""
        try:
            # 确保连接有效
            self._ensure_connection()
            return utility.list_collections()
        except Exception as e:
            logger.error(f"列出集合失败: {e}")
            return []

    def delete_collection(self, collection_name: str) -> bool:
        """删除集合"""
        try:
            full_collection_name = self._get_collection_name(collection_name)
            if utility.has_collection(full_collection_name):
                utility.drop_collection(full_collection_name)
                logger.info(f"删除Milvus集合 {full_collection_name} 成功")
                return True
            return False
        except Exception as e:
            logger.error(f"删除Milvus集合失败: {e}")
            return False

    def add_vectors(self, collection_name: str, vectors: np.ndarray,
                   metadata: List[Dict[str, Any]], ids: Optional[List[str]] = None) -> List[str]:
        """添加向量"""
        try:
            full_collection_name = self._get_collection_name(collection_name)
            collection = Collection(full_collection_name)

            # 获取集合的schema以确定字段顺序
            schema = collection.schema
            field_names = [field.name for field in schema.fields]

            # 生成ID
            if ids is None:
                ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

            # 准备数据 - Milvus需要按列组织
            ids_list = ids
            vectors_list = [v.tolist() if hasattr(v, 'tolist') else v for v in vectors]
            metadata_list = metadata
            timestamp_list = [datetime.now().isoformat()] * len(vectors)

            # 按schema字段顺序组织数据
            data = []
            for field_name in field_names:
                if field_name == "id":
                    data.append(ids_list)
                elif field_name in ["vector", "embedding"]:  # 支持不同的向量字段名
                    data.append(vectors_list)
                elif field_name == "metadata":
                    data.append(metadata_list)
                elif field_name in ["created_at", "timestamp"]:
                    data.append(timestamp_list)

            # 插入数据
            collection.insert(data)
            collection.flush()

            logger.info(f"向Milvus集合 {full_collection_name} 添加 {len(vectors)} 个向量成功")
            return ids

        except Exception as e:
            logger.error(f"添加向量到Milvus集合失败: {e}")
            raise

    def search(self, collection_name: str, query_vector: np.ndarray,
              top_k: int = 5, filter_condition: Optional[Dict] = None) -> Tuple[List[str], List[float], List[Dict]]:
        """搜索向量"""
        try:
            # 确保连接有效
            self._ensure_connection()
            full_collection_name = self._get_collection_name(collection_name)

            # 检查集合是否存在
            if not utility.has_collection(full_collection_name):
                logger.warning(f"集合 {full_collection_name} 不存在")
                return [], [], []

            collection = Collection(full_collection_name)

            # ✅ 强制加载集合（确保可搜索）
            try:
                if utility.load_state(full_collection_name) != "Loaded":
                    collection.load()
                    logger.info(f"🔄 强制加载集合: {full_collection_name}")
            except Exception as load_e:
                logger.warning(f"⚠️ 强制加载集合失败: {load_e}")

            # ✅ 检查向量维度是否匹配
            try:
                schema = collection.schema
                for field in schema.fields:
                    if field.dtype == DataType.FLOAT_VECTOR:
                        expected_dim = field.params.get('dim', 0)
                        actual_dim = len(query_vector)
                        if expected_dim != actual_dim:
                            logger.warning(f"集合 {full_collection_name} 向量维度不匹配：期望{expected_dim}，实际{actual_dim}，跳过搜索")
                            return [], [], []
                        break
            except Exception as dim_err:
                logger.debug(f"维度检查失败: {dim_err}")

            # 检查集合状态，避免重复加载
            load_success = False
            try:
                # 在部分HTTP/URI模式下，load_state 可能不可用；尽量容错
                try:
                    load_state = utility.load_state(full_collection_name)
                except Exception:
                    load_state = None

                if load_state in (None, "Loaded"):
                    # 无法获取或已加载，直接尝试使用；按需尝试加载一次
                    try:
                        collection.load()
                    except Exception:
                        pass
                    load_success = True
                elif load_state == "NotLoad":
                    logger.info(f"🔄 集合 {full_collection_name} 未加载，正在加载到内存...")

                    # 重试机制：尝试加载5次，增加等待时间
                    import time
                    max_retries = 5
                    for retry in range(max_retries):
                        try:
                            collection.load()
                            time.sleep(2.0)  # 增加等待时间到2秒

                            # 验证加载成功
                            final_state = utility.load_state(full_collection_name)
                            if final_state == "Loaded":
                                logger.info(f"✅ 集合 {full_collection_name} 加载成功")
                                load_success = True
                                break
                            else:
                                logger.warning(f"⚠️ 集合 {full_collection_name} 加载后状态: {final_state}，重试 {retry+1}/{max_retries}")
                        except Exception as e:
                            logger.warning(f"⚠️ 集合加载失败 (尝试 {retry+1}/{max_retries}): {e}")
                            if retry < max_retries - 1:
                                time.sleep(1)  # 等待1秒后重试

                    if not load_success:
                        logger.error(f"❌ 集合 {full_collection_name} 加载失败，已重试{max_retries}次")
                elif load_state == "Loading":
                    logger.info(f"集合 {full_collection_name} 正在加载中，等待...")
                    # 等待加载完成（最多10秒）
                    import time
                    for _ in range(20):
                        time.sleep(0.5)
                        current_state = utility.load_state(full_collection_name)
                        if current_state == "Loaded":
                            logger.info(f"✅ 集合 {full_collection_name} 加载完成")
                            load_success = True
                            break
                    else:
                        logger.warning(f"⚠️ 集合 {full_collection_name} 加载超时，尝试继续搜索")
                        load_success = True  # 超时也尝试继续
                else:
                    logger.debug(f"集合 {full_collection_name} load_state={load_state}")
                    load_success = True
            except Exception as load_err:
                logger.error(f"❌ 集合加载检查失败: {load_err}")
                import traceback
                logger.debug(traceback.format_exc())
                # 不直接返回，尝试继续搜索
                load_success = True

            # 获取集合的索引信息以确定 metric_type
            metric_type = "IP"  # 默认值
            try:
                index = collection.index()
                if index and hasattr(index, 'params') and 'metric_type' in index.params:
                    metric_type = index.params['metric_type']
            except:
                # 如果无法获取索引信息，尝试两种方式
                pass

            # 构建搜索参数
            search_params = {
                "metric_type": metric_type,
                "params": {"nprobe": self.nprobe}
            }

            # 获取集合的schema以确定可用字段
            schema = collection.schema
            available_fields = [field.name for field in schema.fields]

            # 动态确定向量字段名
            vector_field_name = "vector"  # 默认值
            for field in schema.fields:
                if field.dtype == DataType.FLOAT_VECTOR:
                    vector_field_name = field.name
                    break

            # 动态确定output_fields
            output_fields = ["id"]
            if "metadata" in available_fields:
                output_fields.append("metadata")
            if "created_at" in available_fields:
                output_fields.append("created_at")
            elif "timestamp" in available_fields:
                output_fields.append("timestamp")

            # 执行搜索
            results = collection.search(
                data=[query_vector.tolist()],
                anns_field=vector_field_name,  # 使用动态检测的字段名
                param=search_params,
                limit=top_k,
                expr=self._build_filter_expr(filter_condition) if filter_condition else None,
                output_fields=output_fields
            )

            # ✅ 处理结果
            ids = []
            scores = []
            metadata_list = []

            for hits in results:
                for hit in hits:
                    try:
                        # 动态探测：兼容 pymilvus 2.3.x 和 2.4.x
                        # 获取ID
                        try:
                            vector_id = str(hit.id)  # pymilvus 2.3.x
                        except AttributeError:
                            entity = hit.entity
                            if hasattr(entity, 'get'):
                                vector_id = str(entity.get("id"))  # pymilvus 2.4.x
                            else:
                                vector_id = str(entity["id"])

                        ids.append(vector_id)

                        # 获取分数
                        scores.append(float(hit.score))

                        # 获取 metadata
                        try:
                            meta = hit.entity.metadata  # pymilvus 2.3.x
                        except AttributeError:
                            entity = hit.entity
                            if hasattr(entity, 'get'):
                                meta = entity.get("metadata", {})  # pymilvus 2.4.x
                            else:
                                meta = {}

                        # 类型安全：确保metadata是字典
                        if not isinstance(meta, dict):
                            meta = {}

                        # 确保metadata中有vector_id
                        meta["vector_id"] = vector_id
                        metadata_list.append(meta)

                    except Exception as hit_err:
                        logger.debug(f"处理搜索结果失败: {hit_err}")
                        continue

            return ids, scores, metadata_list

        except Exception as e:
            logger.error(f"在Milvus集合中搜索失败: {e}")
            # 不要raise，返回空结果
            return [], [], []

    def _build_filter_expr(self, filter_condition: Dict) -> str:
        """构建过滤表达式"""
        expressions = []
        for key, value in filter_condition.items():
            if isinstance(value, str):
                expressions.append(f'metadata["{key}"] == "{value}"')
            else:
                expressions.append(f'metadata["{key}"] == {value}')
        return " and ".join(expressions) if expressions else ""

    def delete_vectors(self, collection_name: str, ids: List[str]) -> bool:
        """删除向量"""
        try:
            full_collection_name = self._get_collection_name(collection_name)
            collection = Collection(full_collection_name)

            # 构建删除表达式
            expr = f'id in {ids}'

            # 删除向量
            collection.delete(expr)
            collection.flush()

            logger.info(f"从Milvus集合 {full_collection_name} 删除 {len(ids)} 个向量成功")
            return True

        except Exception as e:
            logger.error(f"删除Milvus向量失败: {e}")
            return False

    def delete_by_metadata(self, collection_name: str, metadata_filter: Dict[str, Any]) -> int:
        """按元数据删除向量

        Args:
            collection_name: 集合名称
            metadata_filter: 元数据过滤条件，如 {"doc_id": "xxx"}

        Returns:
            删除的向量数量
        """
        try:
            full_collection_name = self._get_collection_name(collection_name)
            if not utility.has_collection(full_collection_name):
                logger.warning(f"集合 {full_collection_name} 不存在")
                return 0

            collection = Collection(full_collection_name)
            collection.load()

            # ✅ 构建查询表达式（访问JSON字段metadata）
            expressions = []
            for key, value in metadata_filter.items():
                if isinstance(value, str):
                    expressions.append(f'metadata["{key}"] == "{value}"')  # ✅ 修正：metadata["key"]
                elif isinstance(value, (int, float)):
                    expressions.append(f'metadata["{key}"] == {value}')
                elif isinstance(value, bool):
                    expressions.append(f'metadata["{key}"] == {str(value).lower()}')
                else:
                    logger.warning(f"不支持的过滤值类型: {type(value)}")

            if not expressions:
                logger.warning("没有提供删除条件")
                return 0

            expr = " and ".join(expressions)
            logger.info(f"删除表达式: {expr}")

            # 先查询要删除的向量ID
            results = collection.query(expr, output_fields=["id"])

            if not results:
                logger.info(f"没有找到匹配的向量")
                return 0

            # 提取ID列表
            ids_to_delete = [r["id"] for r in results]
            logger.info(f"准备删除 {len(ids_to_delete)} 个向量")

            # 执行删除
            collection.delete(f'id in {ids_to_delete}')
            collection.flush()

            logger.info(f"从Milvus集合 {full_collection_name} 按条件删除 {len(ids_to_delete)} 个向量成功")
            return len(ids_to_delete)

        except Exception as e:
            logger.error(f"按元数据删除Milvus向量失败: {e}")
            return 0

    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            full_collection_name = self._get_collection_name(collection_name)
            if not utility.has_collection(full_collection_name):
                return {}

            collection = Collection(full_collection_name)
            stats = collection.get_statistics()

            return {
                "name": collection_name,
                "dimension": self.dimension,
                "index_type": "IVF_FLAT",
                "vector_count": stats.get("row_count", 0),
                "created_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"获取Milvus集合信息失败: {e}")
            return {}

    def update_metadata(self, collection_name: str, id: str, metadata: Dict[str, Any]) -> bool:
        """更新元数据"""
        try:
            full_collection_name = self._get_collection_name(collection_name)
            collection = Collection(full_collection_name)

            # 获取当前元数据
            results = collection.query(
                expr=f'id == "{id}"',
                output_fields=["metadata"]
            )

            if results:
                current_metadata = results[0].get("metadata", {})
                current_metadata.update(metadata)
                current_metadata["updated_at"] = datetime.now().isoformat()

                # 更新元数据
                collection.upsert([
                    [id, current_metadata]
                ])
                collection.flush()

                return True

            return False

        except Exception as e:
            logger.error(f"更新Milvus元数据失败: {e}")
            return False
