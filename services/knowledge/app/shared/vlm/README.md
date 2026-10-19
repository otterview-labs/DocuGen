# 通用视觉语言模型（VLM）组件

## 概述

这是一个独立的、可复用的视觉理解组件，用于分析图片和视频内容，将视觉信息转换为结构化的文本描述。

## 特性

- ✅ **通用接口** - 简单易用的API，与业务逻辑解耦
- ✅ **多模型支持** - 支持千问VL、OpenAI Vision等多种VLM
- ✅ **批处理优化** - 自动批量处理大量图片
- ✅ **错误容忍** - 优雅的错误处理和重试机制
- ✅ **模拟模式** - 无需真实API也能测试

## 快速开始

### 基础使用

```python
from app.shared.vlm import VisionAnalyzer

# 创建分析器
analyzer = VisionAnalyzer()

# 分析单张图片
result = analyzer.analyze_image(
    image_path="path/to/image.jpg",
    prompt="请描述图片中的主要内容"
)

if result.success:
    print(result.data)
```

### 视频帧分析

```python
# 准备视频帧数据
frames = [
    {"path": "frame1.jpg", "time_sec": 0.0, "frame_idx": 0},
    {"path": "frame2.jpg", "time_sec": 2.0, "frame_idx": 60},
    {"path": "frame3.jpg", "time_sec": 4.0, "frame_idx": 120},
]

# 分析视频帧
result = analyzer.analyze_video_frames(
    frames_metadata=frames,
    prompt="请描述视频中发生的事件"
)

if result.success:
    for frame_result in result.data.get("images", []):
        print(f"时间 {frame_result['time_sec']}s: {frame_result['description']}")
```

### 批量图片分析

```python
# 分析多张图片
images = ["img1.jpg", "img2.jpg", "img3.jpg"]
result = analyzer.analyze_images(
    images=images,
    prompt="请识别每张图片中的物体",
    batch_process=True  # 自动批处理
)
```

## 配置

### 环境变量配置

```bash
# 模型配置
export VLM_PROVIDER=local
export VLM_MODEL_NAME=qwen3-vl-4b-instruct
export VLM_API_BASE=http://127.0.0.1:8899/v1
export VLM_API_AUTH_MODE=none
export VLM_API_KEY=

# 批处理配置
export VLM_MAX_IMAGES_PER_BATCH=10
```

### 代码配置

```python
from app.shared.vlm import VisionAnalyzer, VLMConfig

# 自定义配置
config = VLMConfig(
    provider="local",
    model_name="qwen3-vl-4b-instruct",
    api_base="http://127.0.0.1:8899/v1",
    auth_mode="none",
    max_images_per_batch=20,
    system_prompt="你是一个专业的图像分析助手"
)

analyzer = VisionAnalyzer(config=config)
```

## 集成到现有系统

### 在unified_markdown_converter.py中使用

```python
from app.shared.vlm import VisionAnalyzer

class UnifiedMarkdownConverter:
    def __init__(self):
        # 初始化VLM分析器
        self.vision_analyzer = VisionAnalyzer()

    def process_video(self, video_path):
        # 提取关键帧
        keyframes = self.extract_keyframes(video_path)

        # 使用VLM分析
        result = self.vision_analyzer.analyze_video_frames(
            frames_metadata=keyframes,
            prompt="描述视频内容，识别关键事件"
        )

        # 转换为Markdown
        if result.success:
            markdown = self.convert_to_markdown(result.data)
            return markdown
```

## API参考

### VisionAnalyzer

主要方法：

- `analyze_image(image_path, prompt)` - 分析单张图片
- `analyze_images(images, prompt, batch_process)` - 分析多张图片
- `analyze_video_frames(frames_metadata, prompt)` - 分析视频帧

### AnalysisResult

返回结果结构：

```python
@dataclass
class AnalysisResult:
    success: bool                    # 是否成功
    data: Optional[Dict[str, Any]]   # 分析结果数据
    error: Optional[str]             # 错误信息
    raw_response: Optional[str]      # 原始响应
```

### 结果数据格式

```json
{
    "images": [
        {
            "index": 0,
            "description": "图片描述",
            "objects": ["物体1", "物体2"],
            "scene": "场景描述",
            "time_sec": 0.0,  // 视频帧时间
            "frame_idx": 0    // 视频帧索引
        }
    ],
    "total_count": 3
}
```

## 优势

1. **解耦设计** - 与业务逻辑完全分离，可独立使用
2. **易于扩展** - 轻松添加新的VLM模型支持
3. **生产就绪** - 包含重试、错误处理、批处理等生产级特性
4. **测试友好** - 提供模拟模式，无需真实API即可测试

## 注意事项

- 确保图片路径可访问
- 大量图片会自动分批处理
- API调用可能产生费用
- 建议设置合理的批大小和超时时间
