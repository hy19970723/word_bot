# AI Video Studio — 系统设计文档

> 多Agent协作的短视频自动化生产系统，面向抖音/TikTok内容创作
>
> **本文档面向AI辅助开发，包含足够的实现细节，可直接据此编码。**
>
> **技术栈：DeepSeek + 可灵(Kling) + Edge-TTS + MoviePy + LangGraph**

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [核心数据结构（Pydantic Schema）](#3-核心数据结构pydantic-schema)
4. [Agent接口定义](#4-agent接口定义)
5. [Prompt模板（完整版）](#5-prompt模板完整版)
6. [工作流与状态机（LangGraph）](#6-工作流与状态机langgraph)
7. [Service层实现规范](#7-service层实现规范)
8. [成本控制体系](#8-成本控制体系)
9. [错误处理策略](#9-错误处理策略)
10. [MVP方案](#10-mvp方案)
11. [完整版方案](#11-完整版方案)
12. [技术选型与依赖](#12-技术选型与依赖)
13. [配置与环境变量](#13-配置与环境变量)
14. [项目结构与实现顺序](#14-项目结构与实现顺序)
15. [测试策略](#15-测试策略)
16. [迭代路线图](#16-迭代路线图)
17. [风险与应对](#17-风险与应对)

---

## 1. 项目概述

### 1.1 项目目标

构建一个基于多Agent协作的短视频自动化生产系统，实现从**选题→脚本→素材→剪辑→审核→发布**的全链路覆盖。

### 1.2 核心价值

- **降低创作门槛**：用户只需输入主题，系统自动完成视频生产全流程
- **提升生产效率**：从数小时的人工制作缩短到分钟级自动化产出
- **保证内容质量**：内置审核Agent，多维度质量把关
- **成本可控**：模型分级路由+素材复用，单条视频成本控制在¥1-2

### 1.3 目标平台

- 抖音（竖屏 9:16，1080×1920）
- TikTok（竖屏 9:16，1080×1920）
- 可扩展：B站、小红书、视频号

### 1.4 支持的内容类型

| 类型 | 枚举值 | 说明 | 典型时长 | 默认镜头数 |
|------|--------|------|----------|-----------|
| 知识科普/解说 | `science` | 科普、历史、技术讲解 | 60-180秒 | 6-12 |
| 故事/剧情 | `story` | 短剧、故事叙述、情景剧 | 60-300秒 | 8-20 |
| 热点追踪 | `trending` | 追热点话题，快速生成内容 | 30-90秒 | 4-8 |
| 产品展示/带货 | `product` | 商品介绍、种草视频 | 30-60秒 | 4-8 |

### 1.5 自动化程度

**半自动模式**：AI生成草稿，人工在关键节点介入确认和修改。

人工介入节点（MVP阶段通过终端交互）：
- **脚本确认**：审核/修改分镜脚本（编剧Agent之后）
- **成片确认**：审核/修改最终视频（审核Agent之后）

---

## 2. 系统架构

### 2.1 MVP架构图（当前实现）

```
┌─────────────────────────────────────────────────────┐
│                   CLI 用户交互层                      │
│              src/main.py + graph.py                  │
│         收集输入 → 启动流水线 → 人工审核节点            │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│              编排调度层 (LangGraph)                    │
│                   src/graph.py                       │
│    状态机 + 条件路由 + 人工审核 + 打回循环              │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Agent 执行层                         │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 编剧Agent │ │ 导演Agent │ │ 剪辑Agent │ │审核Agent│ │
│  │screenwrit│ │ director │ │  editor  │ │reviewer│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │            │            │            │      │
└───────┼────────────┼────────────┼────────────┼──────┘
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────┐
│                  Service 服务层                       │
│                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐ │
│  │DeepSeek│ │  可灵   │ │占位图/音│ │ MoviePy合成  │ │
│  │  LLM   │ │ 视频API │ │ 频生成  │ │ 拼接+字幕   │ │
│  └────────┘ └────────┘ └────────┘ └──────────────┘ │
│                                                      │
│  ┌──────────────┐                                    │
│  │  成本追踪服务  │                                    │
│  └──────────────┘                                    │
└─────────────────────────────────────────────────────┘
```

### 2.2 完整版架构图（未来）

```
┌─────────────────────────────────────────────────────────┐
│                      用户交互层                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ Web前端   │  │ CLI终端   │  │ API接口   │              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       └──────────────┼──────────────┘                   │
└──────────────────────┼──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    编排调度层 (LangGraph)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 状态机    │  │ 预算控制器│  │ 任务队列  │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└──────────────────────┼──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     Agent 执行层                         │
│                                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │选题Agent│ │编剧Agent│ │导演Agent│ │素材Agent│           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │配音Agent│ │剪辑Agent│ │审核Agent│ │发布Agent│           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
└──────────────────────┼──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     基础设施层                            │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │LLM服务  │ │媒体生成 │ │对象存储 │ │向量数据库│           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐ ┌────────┐                      │
│  │任务队列 │ │缓存服务 │ │日志监控 │                      │
│  └────────┘ └────────┘ └────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### 2.3 分层职责

| 层 | 职责 | 关键组件 |
|----|------|----------|
| 用户交互层 | 用户输入、人工审核、数据展示 | CLI终端（MVP）/ Web前端（完整版） |
| 编排调度层 | Agent编排、状态管理、流程控制、预算控制 | LangGraph状态机 |
| Agent执行层 | 各Agent独立执行具体任务 | MVP: 4个Agent / 完整版: 8个Agent |
| 基础设施层 | LLM调用、媒体处理、存储、队列 | DeepSeek、可灵、Edge-TTS、MoviePy |

### 2.4 Agent间通信规则

- Agent之间**只通过State传递数据**，不直接调用
- 每个Agent只读取State中自己需要的字段，不传完整历史
- 所有Agent的输入输出必须符合Pydantic Schema定义
- Agent之间不共享LLM对话历史（上下文裁剪）

---

## 3. 核心数据结构（Pydantic Schema）

> 以下代码可直接复制到 `src/schemas/` 目录使用。

### 3.1 分镜脚本 Schema（`src/schemas/script.py`）

这是整个系统的**核心协议**，所有Agent围绕此结构交互。

```python
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ShotType(str, Enum):
    OPENING = "opening"
    CONTENT = "content"
    TRANSITION = "transition"
    CLOSING = "closing"


class ImageStyle(str, Enum):
    REALISTIC = "realistic"
    ILLUSTRATION = "illustration"
    ANIME = "anime"
    PHOTOGRAPHIC = "photographic"
    CINEMATIC = "cinematic"
    THREE_D = "3d_render"


class TransitionType(str, Enum):
    CUT = "cut"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    CROSSFADE = "crossfade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"


class CameraEffect(str, Enum):
    STATIC = "static"
    ZOOM_IN_SLOW = "zoom_in_slow"
    ZOOM_OUT_SLOW = "zoom_out_slow"
    PAN_LEFT = "pan_left"
    PAN_RIGHT = "pan_right"
    KEN_BURNS = "ken_burns"


class BGMMood(str, Enum):
    MYSTERIOUS = "mysterious"
    CASUAL = "casual"
    UPBEAT = "upbeat"
    DRAMATIC = "dramatic"
    EMOTIONAL = "emotional"
    TENSE = "tense"
    INSPIRING = "inspiring"


class ShotPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Shot(BaseModel):
    id: int = Field(description="镜头序号，从1开始")
    type: ShotType = Field(description="镜头类型")
    duration: float = Field(ge=2.0, le=30.0, description="镜头时长（秒）")
    image_prompt: str = Field(min_length=10, max_length=500, description="画面描述，用于AI生图/视频，要求具体、可视化")
    image_style: ImageStyle = Field(default=ImageStyle.REALISTIC, description="画面风格")
    narration: str = Field(min_length=1, max_length=200, description="旁白文案，口语化")
    subtitle: str = Field(description="字幕文本，用\\n换行，每行不超过15个字")
    transition_in: TransitionType = Field(default=TransitionType.CUT, description="进入转场")
    transition_out: TransitionType = Field(default=TransitionType.CUT, description="离开转场")
    camera_effect: CameraEffect = Field(default=CameraEffect.KEN_BURNS, description="镜头运动效果")
    bgm_mood: BGMMood = Field(default=BGMMood.CASUAL, description="该镜头的BGM情绪")
    priority: ShotPriority = Field(default=ShotPriority.NORMAL, description="素材生成优先级，high=用高质量模型")


class GlobalSettings(BaseModel):
    bgm_style: str = Field(default="轻快电子", description="BGM整体风格")
    voice_id: str = Field(default="zh-CN-YunxiNeural", description="TTS音色ID")
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="语速倍率")
    subtitle_font: str = Field(default="NotoSansSC-Bold", description="字幕字体")
    subtitle_font_size: int = Field(default=42, description="字幕字号")
    subtitle_position: str = Field(default="bottom", description="字幕位置: bottom/center/top")
    subtitle_color: str = Field(default="#FFFFFF", description="字幕颜色")
    subtitle_outline_color: str = Field(default="#000000", description="字幕描边颜色")
    subtitle_outline_width: int = Field(default=2, description="字幕描边宽度")


class ScriptMetadata(BaseModel):
    topic: str = Field(description="主题")
    target_audience: str = Field(default="", description="目标受众")
    keywords: list[str] = Field(default_factory=list, description="关键词列表")
    platform: list[str] = Field(default=["douyin", "tiktok"], description="目标平台")


class Script(BaseModel):
    script_id: str = Field(description="UUID")
    version: int = Field(default=1, description="脚本版本号，每次修改+1")
    title: str = Field(min_length=1, max_length=50, description="视频标题")
    style: str = Field(description="内容类型: science/story/trending/product")
    tone: str = Field(default="幽默通俗", description="语气风格")
    total_duration: int = Field(ge=15, le=600, description="总时长（秒）")
    aspect_ratio: str = Field(default="9:16", description="画面比例")
    resolution: str = Field(default="1080x1920", description="分辨率")
    fps: int = Field(default=30, description="帧率")
    metadata: ScriptMetadata
    shots: list[Shot] = Field(min_length=2, max_length=30, description="镜头列表")
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)
```

### 3.2 制作任务书 Schema（`src/schemas/plan.py`）

```python
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class ImageSource(str, Enum):
    AI_GENERATE = "ai_generate"
    STOCK_LIBRARY = "stock_library"
    REUSE_FROM_POOL = "reuse_from_pool"


class TTSEngine(str, Enum):
    EDGE_TTS = "edge-tts"
    FISH_AUDIO = "fish-audio"
    COSYVOICE = "cosyvoice"


class SubtitleAnimation(str, Enum):
    STATIC = "static"
    TYPEWRITER = "typewriter"
    FADE = "fade"
    SLIDE_UP = "slide_up"


class ShotSourceMapping(BaseModel):
    shot_id: int
    source: ImageSource
    search_query: str = Field(default="", description="素材库搜索关键词（source=stock/reuse时使用）")
    generate_prompt: str = Field(default="", description="AI生图/视频prompt（source=ai_generate时使用，可覆盖script中的image_prompt）")
    image_model: str = Field(default="dall-e-3", description="使用的生成模型")


class GenerationParams(BaseModel):
    image_model: str = Field(default="dall-e-3")
    image_size: str = Field(default="1024x1792")
    image_quality: str = Field(default="hd")
    fallback_model: str = Field(default="stable-diffusion-xl")


class AudioPlan(BaseModel):
    tts_engine: TTSEngine = Field(default=TTSEngine.EDGE_TTS)
    voice_id: str = Field(default="zh-CN-YunxiNeural")
    voice_speed: float = Field(default=1.0)
    bgm_track: str = Field(default="", description="BGM文件路径或名称")
    bgm_volume: float = Field(default=0.15, ge=0.0, le=1.0)
    narration_volume: float = Field(default=1.0, ge=0.0, le=1.0)


class EditPlan(BaseModel):
    default_transition: str = Field(default="crossfade")
    transition_duration: float = Field(default=0.5, ge=0.1, le=2.0)
    subtitle_animation: SubtitleAnimation = Field(default=SubtitleAnimation.TYPEWRITER)
    opening_effect: str = Field(default="fade_in")
    ending_effect: str = Field(default="fade_out")


class ProductionBudget(BaseModel):
    max_images_to_generate: int = Field(default=8)
    max_cost: float = Field(default=5.0, description="预算上限（CNY）")
    currency: str = Field(default="CNY")


class ProductionPlan(BaseModel):
    plan_id: str = Field(description="UUID")
    script_id: str
    shot_sources: list[ShotSourceMapping] = Field(description="每个镜头的素材来源策略")
    generation_params: GenerationParams = Field(default_factory=GenerationParams)
    audio_plan: AudioPlan = Field(default_factory=AudioPlan)
    edit_plan: EditPlan = Field(default_factory=EditPlan)
    budget: ProductionBudget = Field(default_factory=ProductionBudget)
```

### 3.3 审核报告 Schema（`src/schemas/review.py`）

```python
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    APPROVED = "approved"
    REVISION_NEEDED = "revision_needed"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewIssue(BaseModel):
    severity: Severity
    shot_id: Optional[int] = Field(default=None, description="关联的镜头ID，None表示全局问题")
    dimension: str = Field(description="所属审核维度")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="修改建议")


class DimensionReview(BaseModel):
    score: int = Field(ge=0, le=100)
    passed: bool
    issues: list[ReviewIssue] = Field(default_factory=list)


class ReviewReport(BaseModel):
    review_id: str = Field(description="UUID")
    script_id: str
    round: int = Field(ge=1, description="当前审核轮次")
    max_rounds: int = Field(default=2)
    verdict: Verdict
    overall_score: int = Field(ge=0, le=100)
    dimensions: dict[str, DimensionReview] = Field(description="key为维度名: compliance/technical_quality/content_quality/platform_fit")
    revision_instructions: str = Field(default="", description="打回时的总体修改指引")
```

### 3.4 成本追踪 Schema（`src/schemas/cost.py`）

```python
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


class BudgetStatus(str, Enum):
    WITHIN_BUDGET = "within_budget"
    WARNING = "warning"
    EXCEEDED = "exceeded"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    cost: float = 0.0


class ImageUsage(BaseModel):
    ai_generated: int = 0
    reused: int = 0
    local_generated: int = 0
    cost: float = 0.0


class Budget(BaseModel):
    max_tokens: int = 8000
    max_images: int = 8
    max_retry_rounds: int = 2
    cost_limit: float = 5.0
    currency: str = "CNY"


class Usage(BaseModel):
    tokens: dict[str, TokenUsage] = Field(default_factory=dict, description="key为agent名")
    images: ImageUsage = Field(default_factory=ImageUsage)
    tts_cost: float = 0.0
    total_cost: float = 0.0


class CostTracker(BaseModel):
    video_id: str
    budget: Budget = Field(default_factory=Budget)
    usage: Usage = Field(default_factory=Usage)
    status: BudgetStatus = BudgetStatus.WITHIN_BUDGET
```

---

## 4. Agent接口定义

> 每个Agent是一个Python类，继承自 `BaseAgent`，实现 `execute` 方法。
> Agent的输入输出通过LangGraph State传递。

### 4.1 State定义（`src/state.py`）

```python
from __future__ import annotations
from typing import Optional
from typing_extensions import TypedDict
from src.schemas.script import Script
from src.schemas.plan import ProductionPlan
from src.schemas.review import ReviewReport
from src.schemas.cost import CostTracker


class VideoState(TypedDict):
    video_id: str
    user_input: str
    content_type: str
    tone: str
    duration: int

    script: Optional[Script]
    production_plan: Optional[ProductionPlan]

    generated_clips: dict[int, str]
    generated_images: dict[int, str]
    generated_audios: dict[int, str]
    video_draft_path: Optional[str]
    final_video_path: Optional[str]

    review_report: Optional[ReviewReport]
    review_round: int

    cost_tracker: CostTracker

    human_feedback: Optional[str]
    human_action: Optional[str]

    status: str
    error: Optional[str]
```

**State字段说明**：

| 字段 | 类型 | 说明 | 写入者 |
|------|------|------|--------|
| `video_id` | str | 视频唯一ID（UUID） | 初始化 |
| `user_input` | str | 用户输入的原始主题 | 初始化 |
| `content_type` | str | 内容类型枚举值 | 初始化 |
| `tone` | str | 语气风格 | 初始化 |
| `duration` | int | 目标时长（秒） | 初始化 |
| `script` | Script | 分镜脚本 | 编剧Agent |
| `production_plan` | ProductionPlan | 制作任务书 | 导演Agent |
| `generated_clips` | dict[int, str] | 镜头ID→可灵视频片段路径 | 剪辑Agent |
| `generated_images` | dict[int, str] | 镜头ID→图片文件路径（占位图回退） | 剪辑Agent |
| `generated_audios` | dict[int, str] | 镜头ID→音频文件路径 | 剪辑Agent |
| `video_draft_path` | str | 成片初稿路径 | 剪辑Agent |
| `final_video_path` | str | 最终视频路径 | 审核通过后 |
| `review_report` | ReviewReport | 审核报告 | 审核Agent |
| `review_round` | int | 当前审核轮次 | 审核Agent |
| `cost_tracker` | CostTracker | 成本追踪器 | 所有Agent |
| `human_feedback` | str | 人工反馈内容 | 人工审核节点 |
| `human_action` | str | 人工操作类型 | 人工审核节点 |
| `status` | str | 流水线状态 | 全局 |
| `error` | str | 错误信息 | 异常时 |

**status 枚举值**：

| 值 | 含义 |
|----|------|
| `pending` | 等待开始 |
| `awaiting_script_review` | 等待人工审核脚本 |
| `directing` | 导演规划中 |
| `editing` | 剪辑合成中 |
| `reviewing` | 自动审核中 |
| `awaiting_video_review` | 等待人工审核成片 |
| `completed` | 完成 |
| `cancelled` | 用户取消 |

### 4.2 Agent基类（`src/agents/base.py`）

```python
from abc import ABC, abstractmethod
from src.state import VideoState
from src.services.cost_tracker import CostTrackerService
import structlog

logger = structlog.get_logger()


class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logger.bind(agent=name)

    @abstractmethod
    def execute(self, state: VideoState) -> dict:
        pass

    def check_budget(self, state: VideoState) -> None:
        tracker = CostTrackerService(state["cost_tracker"])
        if tracker.is_exceeded():
            raise BudgetExceededError(
                f"Agent {self.name}: 预算超限，当前花费 {tracker.tracker.usage.total_cost}"
            )

    def get_cost_tracker(self, state: VideoState) -> CostTrackerService:
        return CostTrackerService(state["cost_tracker"])


class AgentError(Exception):
    def __init__(self, agent_name: str, message: str, recoverable: bool = True):
        self.agent_name = agent_name
        self.recoverable = recoverable
        super().__init__(f"[{agent_name}] {message}")


class BudgetExceededError(AgentError):
    def __init__(self, message: str):
        super().__init__("budget", message, recoverable=False)
```

### 4.3 编剧Agent（`src/agents/screenwriter.py`）

```python
class ScreenwriterAgent(BaseAgent):
    """
    编剧Agent：将用户主题转化为结构化分镜脚本。

    输入State字段：user_input, content_type, tone, duration
    输出State字段：script, cost_tracker
    使用模型：deepseek-chat（creative tier, temperature=0.8）
    """

    def __init__(self):
        super().__init__("screenwriter")
        self.llm = LLMService(model_tier="creative")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 根据content_type选择对应的prompt模板（config/templates/screenwriter/{type}.txt）
        2. 计算shot_count（基于content_type和duration）
        3. 填充模板变量（topic, tone, duration, target_audience, shot_count, json_schema）
        4. 如果有human_feedback，追加到prompt末尾
        5. 调用LLM，强制JSON Schema输出
        6. 解析并校验返回的JSON（LLMService内部重试最多2次）
        7. 记录token消耗到cost_tracker

        Returns:
            {"script": Script, "cost_tracker": CostTracker, "status": "awaiting_script_review"}
        """
        pass
```

**shot_count计算规则**（`_calculate_shot_count`函数）：

| content_type | duration范围 | shot_count |
|-------------|-------------|------------|
| science | 30-60s | 4-6 |
| science | 60-120s | 6-10 |
| science | 120-180s | 10-12 |
| story | 60-120s | 6-10 |
| story | 120-300s | 10-20 |
| trending | 30-60s | 3-5 |
| trending | 60-90s | 5-8 |
| product | 30-60s | 4-8 |

公式：`shot_count = max(min_shots, min(max_shots, duration // 10))`

### 4.4 导演Agent（`src/agents/director.py`）

```python
class DirectorAgent(BaseAgent):
    """
    导演Agent：将分镜脚本转化为可执行的制作任务书。

    输入State字段：script
    输出State字段：production_plan, status
    使用模型：不调用LLM，纯规则引擎
    """

    def __init__(self):
        super().__init__("director")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程（纯规则，不调LLM）：
        1. 遍历script.shots，根据priority决策素材来源和质量
        2. 根据tone决策BGM风格
        3. 根据style决策字幕动画和转场
        4. 生成ProductionPlan

        Returns:
            {"production_plan": ProductionPlan, "status": "editing"}
        """
        pass
```

**导演Agent的决策规则**：

```
素材质量决策（_decide_quality_for_shot）:
  if shot.priority == "high":
      model = "dall-e-3", quality = "hd"
  else:
      model = "dall-e-3", quality = "standard"

BGM风格决策（_decide_bgm_style）:
  if tone包含("幽默" or "轻松" or "通俗") → "轻快电子"
  elif tone包含("严肃" or "专业") → "简约钢琴"
  elif tone包含("悬疑" or "紧张") → "暗黑氛围"
  else → "轻快电子"

字幕动画决策（_decide_subtitle_animation）:
  science → TYPEWRITER
  story → FADE
  trending → SLIDE_UP
  product → SLIDE_UP

转场决策（_decide_transition）:
  trending/product → "cut"（快节奏）
  其他 → "crossfade"
```

### 4.5 剪辑Agent（`src/agents/editor.py`）

```python
class EditorAgent(BaseAgent):
    """
    剪辑Agent：可灵视频生成 + Edge-TTS配音 + MoviePy合成。

    输入State字段：script, production_plan, cost_tracker
    输出State字段：generated_clips, generated_images, generated_audios, video_draft_path, cost_tracker
    使用模型：不调用LLM
    """

    def __init__(self):
        super().__init__("editor")
        self.kling_service = KlingService() if settings.kling_access_key else None
        self.image_service = ImageGenService()
        self.tts_service = TTSService()
        self.video_composer = VideoComposeService()

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 遍历script.shots，对每个镜头：
           a. 如果有kling_service（配置了Kling Key）：
              - 调用kling_service.text_to_video()生成视频片段
              - 成功 → 记录到generated_clips，追踪成本
              - 失败 → 回退到占位图
           b. 如果没有kling_service或Kling失败：
              - 调用image_service.generate()生成占位图
              - 记录到generated_images，追踪成本（cost=0.0）
        2. 遍历script.shots，为每个镜头调用tts_service.synthesize_sync()生成配音
           - 使用script.global_settings中的voice_id和voice_speed
           - Edge-TTS失败时自动降级为静音音频
        3. 调用video_composer.compose()合成最终视频（MoviePy）
           - 优先使用clips（可灵视频），其次使用images（占位图）
           - 叠加字幕（TextClip）
        4. 保存script.json和plan.json到output目录

        Returns:
            {
                "generated_clips": {shot_id: clip_path, ...},
                "generated_images": {shot_id: image_path, ...},
                "generated_audios": {shot_id: audio_path, ...},
                "video_draft_path": "output/{video_id}/draft.mp4",
                "cost_tracker": CostTracker,
                "status": "reviewing"
            }
        """
        pass
```

**剪辑Agent的文件命名规范**：

```
output/
└── {video_id}/
    ├── script.json                    # 分镜脚本
    ├── plan.json                      # 制作任务书
    ├── assets/
    │   ├── clip_01.mp4               # 镜头1可灵视频片段
    │   ├── clip_02.mp4               # 镜头2可灵视频片段
    │   ├── shot_01.png               # 镜头1占位图（Kling失败时）
    │   ├── narration_01.mp3          # 镜头1配音（Edge-TTS）
    │   ├── narration_02.mp3          # 镜头2配音
    │   └── ...
    └── draft.mp4                      # 成片初稿
```

### 4.6 审核Agent（`src/agents/reviewer.py`）

```python
class ReviewerAgent(BaseAgent):
    """
    审核Agent：多维度质量检查，通过或打回修改。

    输入State字段：script, video_draft_path, review_round
    输出State字段：review_report, review_round, final_video_path(通过时), cost_tracker
    使用模型：deepseek-chat（efficient tier, temperature=0.3）
    """

    PASS_SCORE = 60

    def __init__(self):
        super().__init__("reviewer")
        self.llm = LLMService(model_tier="efficient")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程（3步审核）：
        1. 合规检查（规则，不调LLM）：
           - 敏感词库匹配（check_sensitive_words）
           - 检查title + narration + subtitle全文
        2. 技术检查（规则，不调LLM）：
           - 每个镜头duration是否在2-30秒范围
           - 字幕每行是否≤15字（split("\n")逐行检查）
           - 总时长是否≥15秒
        3. 内容审核（调LLM）：
           - 使用reviewer模板，发送完整script给LLM评估
           - LLM评估：叙事连贯性、画面-旁白匹配度、吸引力、平台适配
           - LLM不可用时降级为默认评分（70分）
        4. 合并结果，计算加权总分
        5. 判定verdict

        Returns:
            {
                "review_report": ReviewReport,
                "review_round": int,
                "final_video_path": str(通过时),
                "cost_tracker": CostTracker,
                "status": "awaiting_video_review" 或 "reviewing"
            }
        """
        pass
```

**审核评分权重与判定**：

| 维度 | 权重 | 检查方式 | 一票否决 |
|------|------|----------|----------|
| compliance（合规） | — | 规则（敏感词） | 是 |
| technical_quality（技术质量） | 30% | 规则检查 | 否 |
| content_quality（内容质量） | 40% | LLM评估 | 否 |
| platform_fit（平台适配） | 30% | LLM评估 | 否 |

```
overall_score = technical_quality * 0.3 + content_quality * 0.4 + platform_fit * 0.3
如果compliance不通过 → verdict直接为revision_needed，不论总分
如果overall_score >= 60 且 compliance通过 → verdict为approved
否则 → verdict为revision_needed
```

---

## 5. Prompt模板（完整版）

> 模板文件存放在 `config/templates/` 目录，使用Python `str.format()` 填充变量。

### 5.1 编剧Agent - 科普类（`config/templates/screenwriter/science.txt`）

```
你是一个专业的抖音短视频编剧，擅长将复杂知识转化为通俗易懂、引人入胜的短视频脚本。

请根据以下信息创作分镜脚本：

【主题】{topic}
【风格】{tone}
【目标时长】{duration}秒
【目标受众】{target_audience}
【镜头数量】{shot_count}个

创作要求：
1. 开头（第1个镜头）必须有强吸引力的hook，用提问、反常识或惊人数据抓住注意力
2. 中间镜头按照"是什么→为什么→怎么样"的逻辑展开
3. 最后一个镜头要有总结或引导互动（如"你觉得呢？评论区告诉我"）
4. 每个镜头时长5-15秒
5. image_prompt必须具体、可视化，描述一个明确的画面场景，不要抽象概念
6. narration要口语化，像在跟朋友聊天，避免书面语
7. subtitle用\n换行，每行不超过15个字
8. 合理分配transition和camera_effect，让视频有节奏感

请严格按照以下JSON格式输出，不要输出任何其他内容：
{json_schema}
```

### 5.2 编剧Agent - 故事类（`config/templates/screenwriter/story.txt`）

```
你是一个专业的抖音短视频编剧，擅长创作引人入胜的短故事脚本。

请根据以下信息创作分镜脚本：

【故事主题】{topic}
【风格】{tone}
【目标时长】{duration}秒
【目标受众】{target_audience}
【镜头数量】{shot_count}个

创作要求：
1. 开头必须有悬念或冲突，立刻抓住观众
2. 中间有转折或高潮
3. 结尾要有反转或情感共鸣
4. 每个镜头的image_prompt要描述具体的场景画面，包含人物动作、表情、环境
5. narration要像讲故事一样，有节奏感，适当停顿
6. subtitle用\n换行，每行不超过15个字
7. 利用transition和camera_effect增强叙事效果

请严格按照以下JSON格式输出，不要输出任何其他内容：
{json_schema}
```

### 5.3 编剧Agent - 热点类（`config/templates/screenwriter/trending.txt`）

```
你是一个专业的抖音短视频编剧，擅长快速追踪热点并创作相关内容。

请根据以下热点话题创作分镜脚本：

【热点话题】{topic}
【风格】{tone}
【目标时长】{duration}秒
【目标受众】{target_audience}
【镜头数量】{shot_count}个

创作要求：
1. 开头直接切入热点核心，不拖泥带水
2. 提供独特视角或深度分析，区别于普通评论
3. 结尾引导讨论和互动
4. image_prompt要描述与话题相关的具体画面
5. narration要简洁有力，观点鲜明
6. subtitle用\n换行，每行不超过15个字

请严格按照以下JSON格式输出，不要输出任何其他内容：
{json_schema}
```

### 5.4 编剧Agent - 带货类（`config/templates/screenwriter/product.txt`）

```
你是一个专业的抖音短视频编剧，擅长创作文案带货/种草视频脚本。

请根据以下产品信息创作分镜脚本：

【产品/主题】{topic}
【风格】{tone}
【目标时长】{duration}秒
【目标受众】{target_audience}
【镜头数量】{shot_count}个

创作要求：
1. 开头用痛点/场景切入，引起共鸣
2. 中间展示产品亮点和使用效果
3. 结尾引导购买或关注
4. image_prompt要描述产品使用场景、产品特写等画面
5. narration要真实自然，像用户分享体验，避免硬广感
6. subtitle用\n换行，每行不超过15个字

请严格按照以下JSON格式输出，不要输出任何其他内容：
{json_schema}
```

### 5.5 导演Agent模板（`config/templates/director/default.txt`）

> 注意：当前MVP实现中导演Agent为纯规则引擎，不调用LLM，此模板保留作为未来LLM化导演Agent的参考。

```
你是一个短视频导演，负责将编剧的分镜脚本转化为可执行的制作方案。

以下是分镜脚本：
{script_json}

请为每个镜头决策素材生成策略：

决策规则：
- priority为high的镜头：使用高质量AI生图（dall-e-3, hd质量）
- priority为normal的镜头：使用标准AI生图（dall-e-3, standard质量）
- priority为low的镜头：使用标准AI生图（dall-e-3, standard质量）
- 你可以优化image_prompt使其更适合AI生图（更具体、更有视觉冲击力）

同时决策：
- BGM风格选择（基于整体tone）
- 转场节奏（快节奏内容用cut，舒缓内容用crossfade）
- 字幕动画（科普用typewriter，故事用fade，带货用slide_up）

请严格按照以下JSON格式输出：
{json_schema}
```

### 5.6 审核Agent（`config/templates/reviewer/default.txt`）

```
你是一个短视频内容审核专家。请对以下视频脚本进行多维度审核。

视频标题：{title}
视频类型：{style}
总时长：{total_duration}秒
镜头数：{shot_count}个

分镜脚本：
{script_json}

请从以下维度评分（0-100分）并指出问题：

1. **技术质量**（权重30%）：
   - 每个镜头时长是否合理（2-30秒）
   - 字幕每行是否≤15字
   - 总时长是否适合短视频平台（15-300秒）
   - 转场是否合理（不能全部用cut，也不能全部用crossfade）

2. **内容质量**（权重40%）：
   - 叙事是否连贯，镜头之间是否有逻辑
   - image_prompt与narration是否匹配（画面是否对应旁白内容）
   - 开头是否有吸引力（hook）
   - 信息密度是否适中（不空洞也不过载）

3. **平台适配**（权重30%）：
   - 标题是否有吸引力
   - 内容是否适合抖音/TikTok用户
   - 是否有引导互动的元素

4. **合规检查**（一票否决）：
   - 是否包含敏感词或违规内容
   - 是否有明显的版权风险
   - 是否有虚假信息

请严格按照以下JSON格式输出：
{json_schema}
```

### 5.7 JSON Schema注入变量

所有Prompt模板中的 `{json_schema}` 变量，在运行时替换为对应Pydantic模型的JSON Schema字符串：

```python
json_schema = json.dumps(Script.model_json_schema(), ensure_ascii=False)  # 编剧Agent
json_schema = json.dumps(ReviewReport.model_json_schema(), ensure_ascii=False)  # 审核Agent
```

---

## 6. 工作流与状态机（LangGraph）

### 6.1 MVP工作流

```
用户输入主题(如"黑洞是什么")
       │
       ▼
   编剧Agent ──→ 分镜脚本JSON (DeepSeek)
       │
       ▼ (终端人工确认/修改)
   导演Agent ──→ 制作指令 (纯规则引擎)
       │
       ▼
   剪辑Agent ──→ 可灵视频生成 + Edge-TTS配音 + MoviePy合成 → 成片.mp4
       │
       ▼
   审核Agent ──→ 通过 → 输出最终视频 (DeepSeek + 规则)
               → 不通过 → 打回剪辑Agent(最多2轮)
       │
       ▼ (终端人工确认成片)
   成本报告输出
```

### 6.2 LangGraph状态机完整实现（`src/graph.py`）

```python
from langgraph.graph import StateGraph, START, END
from src.state import VideoState
from src.agents.screenwriter import ScreenwriterAgent
from src.agents.director import DirectorAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent


def build_graph():
    graph = StateGraph(VideoState)

    screenwriter = ScreenwriterAgent()
    director = DirectorAgent()
    editor = EditorAgent()
    reviewer = ReviewerAgent()

    graph.add_node("screenwriting", screenwriter.execute)
    graph.add_node("human_script_review", human_script_review_node)
    graph.add_node("directing", director.execute)
    graph.add_node("editing", editor.execute)
    graph.add_node("reviewing", reviewer.execute)
    graph.add_node("human_video_review", human_video_review_node)

    graph.add_edge(START, "screenwriting")
    graph.add_edge("screenwriting", "human_script_review")
    graph.add_conditional_edges(
        "human_script_review",
        route_after_script_review,
        {
            "approved": "directing",
            "revision": "screenwriting",
            "cancelled": END,
        }
    )
    graph.add_edge("directing", "editing")
    graph.add_edge("editing", "reviewing")
    graph.add_conditional_edges(
        "reviewing",
        route_after_review,
        {
            "approved": "human_video_review",
            "revision_needed": "editing",
            "max_rounds_reached": "human_video_review",
        }
    )
    graph.add_conditional_edges(
        "human_video_review",
        route_after_video_review,
        {
            "approved": END,
            "revision": "editing",
            "cancelled": END,
        }
    )

    return graph.compile()


def route_after_script_review(state: VideoState) -> str:
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def route_after_review(state: VideoState) -> str:
    report = state["review_report"]
    if report.verdict.value == "approved":
        return "approved"
    if state["review_round"] >= report.max_rounds:
        return "max_rounds_reached"
    return "revision_needed"


def route_after_video_review(state: VideoState) -> str:
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def human_script_review_node(state: VideoState) -> dict:
    script = state["script"]
    print("\n" + "=" * 60)
    print("  分镜脚本审核")
    print("=" * 60)
    print(f"标题: {script.title}")
    print(f"风格: {script.style} | 语气: {script.tone}")
    print(f"总时长: {script.total_duration}秒 | 镜头数: {len(script.shots)}")
    print("-" * 60)
    for shot in script.shots:
        print(f"\n镜头 {shot.id} [{shot.type.value}] ({shot.duration}秒)")
        print(f"  画面: {shot.image_prompt[:80]}...")
        print(f"  旁白: {shot.narration}")
        print(f"  字幕: {shot.subtitle}")
    print("\n" + "=" * 60)
    print("操作: [a]确认  [r]修改后重新生成  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break
        print("无效输入，请重新选择")

    if choice == "a":
        return {"human_action": "approve", "status": "directing"}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "screenwriting"}
    else:
        return {"human_action": "cancel", "status": "cancelled"}


def human_video_review_node(state: VideoState) -> dict:
    video_path = state.get("final_video_path") or state.get("video_draft_path")
    report = state.get("review_report")

    print("\n" + "=" * 60)
    print("  成片审核")
    print("=" * 60)
    print(f"视频文件: {video_path}")
    if report:
        print(f"自动审核评分: {report.overall_score}/100")
        print(f"审核结论: {report.verdict.value}")
        if report.revision_instructions:
            print(f"修改建议: {report.revision_instructions}")
    print("=" * 60)
    print("操作: [a]确认  [r]重新剪辑  [q]取消")

    while True:
        choice = input("请选择: ").strip().lower()
        if choice in ("a", "r", "q"):
            break

    if choice == "a":
        return {"human_action": "approve", "status": "completed"}
    elif choice == "r":
        feedback = input("请输入修改意见: ").strip()
        return {"human_action": "revise", "human_feedback": feedback, "status": "editing"}
    else:
        return {"human_action": "cancel", "status": "cancelled"}
```

---

## 7. Service层实现规范

### 7.1 LLM服务（`src/services/llm.py`）

通过OpenAI SDK调用DeepSeek（兼容OpenAI API协议）。

```python
from openai import OpenAI
from pydantic import BaseModel
import json
import structlog
from config.settings import settings

logger = structlog.get_logger()

MODEL_ROUTING = {
    "creative": {
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": 4096,
    },
    "efficient": {
        "model": "deepseek-chat",
        "temperature": 0.3,
        "max_tokens": 2048,
    },
}

TOKEN_PRICES = {
    "deepseek-chat": {"prompt": 1.0 / 1_000_000, "completion": 2.0 / 1_000_000},
    "deepseek-reasoner": {"prompt": 4.0 / 1_000_000, "completion": 16.0 / 1_000_000},
}

USD_TO_CNY = 7.2


class LLMService:
    def __init__(self, model_tier: str = "efficient"):
        self.tier = model_tier
        self.config = MODEL_ROUTING[model_tier]
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        max_retries: int = 2,
    ) -> tuple[BaseModel, dict]:
        """
        调用LLM生成结构化JSON输出。

        Returns:
            tuple: (解析后的Pydantic实例, usage信息dict)
                   usage格式: {"prompt_tokens": int, "completion_tokens": int, "model": str, "cost": float(CNY)}

        Raises:
            LLMOutputError: 重试耗尽后仍无法获得有效输出
        """
        schema_str = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        full_prompt = f"{prompt}\n\n请严格按照以下JSON Schema输出：\n{schema_str}"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                current_prompt = full_prompt
                if attempt > 0:
                    current_prompt += f"\n\n[第{attempt+1}次尝试] 上次输出格式有误：{last_error}，请修正后重新输出。"

                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=[{"role": "user", "content": current_prompt}],
                    temperature=self.config["temperature"],
                    max_tokens=self.config["max_tokens"],
                    response_format={"type": "json_object"},
                )

                content = response.choices[0].message.content
                parsed = response_model.model_validate_json(content)
                usage = self._calculate_usage(response.usage)
                return parsed, usage

            except (json.JSONDecodeError, ValueError) as e:
                last_error = str(e)
                logger.warning("llm_parse_failed", attempt=attempt + 1, error=str(e))
                continue

        raise LLMOutputError(f"LLM输出解析失败，已重试{max_retries}次: {last_error}")

    def _calculate_usage(self, usage) -> dict:
        model = self.config["model"]
        prices = TOKEN_PRICES.get(model, {"prompt": 0, "completion": 0})
        cost_usd = (usage.prompt_tokens * prices["prompt"]
                    + usage.completion_tokens * prices["completion"])
        cost_cny = round(cost_usd * USD_TO_CNY, 4)
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "model": model,
            "cost": cost_cny,
        }


class LLMOutputError(Exception):
    pass
```

### 7.2 可灵视频生成服务（`src/services/kling.py`）

通过可灵API生成AI视频片段，使用JWT认证。

```python
import time
import jwt
import httpx
from pathlib import Path
import structlog
from config.settings import settings

logger = structlog.get_logger()

KLING_PRICES = {
    "kling-v2-5-turbo": {"5s": 0.35},
    "kling-v2-6-std": {"5s": 0.28},
    "kling-v2-6-pro": {"5s": 0.49, "10s": 0.98},
}

TASK_POLL_INTERVAL = 5
TASK_MAX_WAIT = 300


class KlingService:
    def __init__(self):
        self.access_key = settings.kling_access_key
        self.secret_key = settings.kling_secret_key
        self.base_url = settings.kling_base_url

    def _generate_jwt(self) -> str:
        now = int(time.time())
        payload = {"iss": self.access_key, "exp": now + 1800, "nbf": now - 5}
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def text_to_video(
        self,
        prompt: str,
        output_path: str,
        duration: int = 5,
        aspect_ratio: str = "9:16",
        model: str = "",
        negative_prompt: str = "",
    ) -> dict:
        """
        调用可灵text2video API生成视频。

        流程：提交任务 → 轮询状态 → 下载视频

        Returns:
            dict: {"path": str, "cost": float(CNY), "model": str}

        Raises:
            KlingError: API调用失败、任务失败或超时
        """
        pass


class KlingError(Exception):
    pass
```

### 7.3 占位图生成服务（`src/services/image_gen.py`）

当前MVP实现：生成带prompt文字的纯色占位图（Pillow）。未来可替换为DALL-E 3/通义万相。

```python
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import structlog

logger = structlog.get_logger()

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


class ImageGenService:
    def generate(
        self,
        prompt: str,
        output_path: str,
        model: str = "placeholder",
        size: str = "1024x1792",
        quality: str = "hd",
    ) -> dict:
        """
        生成占位图（1080x1920深色背景+prompt文字）。

        Returns:
            dict: {"path": str, "cost": 0.0, "model": "placeholder"}
        """
        pass


class ImageGenError(Exception):
    pass
```

### 7.4 TTS服务（`src/services/tts.py`）

使用Edge-TTS合成语音，失败时自动降级为静音音频。

```python
import asyncio
from pathlib import Path
import structlog

logger = structlog.get_logger()


class TTSService:
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str = "zh-CN-YunxiNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        duration: float = 5.0,
    ) -> dict:
        """
        使用Edge-TTS合成语音。edge-tts不可用或失败时降级为静音WAV。

        Returns:
            dict: {"path": str, "cost": 0.0}
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
            await communicate.save(output_path)
            return {"path": output_path, "cost": 0.0}
        except ImportError:
            logger.warning("edge_tts_not_installed, falling_back to silence")
            return self._generate_silence(output_path, duration)
        except Exception as e:
            logger.warning("edge_tts_failed", error=str(e), fallback="silence")
            return self._generate_silence(output_path, duration)

    def synthesize_sync(
        self, text: str, output_path: str,
        voice: str = "zh-CN-YunxiNeural", rate: str = "+0%",
        volume: str = "+0%", duration: float = 5.0,
    ) -> dict:
        """同步包装器，供EditorAgent调用"""
        return asyncio.run(self.synthesize(text, output_path, voice, rate, volume, duration))

    @staticmethod
    def _generate_silence(output_path: str, duration: float) -> dict:
        """生成静音WAV文件作为降级方案"""
        import struct, wave
        sample_rate = 44100
        num_samples = int(sample_rate * duration)
        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            silence = struct.pack(f"<{num_samples}h", *([0] * num_samples))
            wf.writeframes(silence)
        return {"path": output_path, "cost": 0.0}

    @staticmethod
    def speed_to_rate(speed: float) -> str:
        """将speed倍率转换为Edge-TTS的rate格式。1.0→+0%, 1.1→+10%, 0.9→-10%"""
        pct = int((speed - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"


class TTSError(Exception):
    pass
```

### 7.5 视频合成服务（`src/services/video_compose.py`）

使用MoviePy合成最终视频。支持可灵视频片段和占位图两种输入。

```python
from pathlib import Path
import structlog

logger = structlog.get_logger()

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30


class VideoComposeService:
    def compose(
        self,
        shots: list[dict],
        clips: dict[int, str],
        images: dict[int, str],
        audios: dict[int, str],
        output_path: str,
        global_settings: dict,
    ) -> str:
        """
        使用MoviePy合成最终视频。

        对每个镜头：
        1. 优先使用clips中的可灵视频片段（VideoFileClip）
           - 如果视频比镜头长 → subclipped裁剪
           - 如果视频比镜头短 → with_speed_scaled减速
           - resized到1080x1920
        2. 如果没有视频片段，使用images中的占位图（ImageClip）
           - resized到1080x1920
        3. 叠加音频（AudioFileClip）
        4. 叠加字幕（TextClip + CompositeVideoClip）
           - 支持bottom/center/top三种位置
        5. concatenate_videoclips拼接所有镜头
        6. write_videofile输出（libx264 + aac）

        Raises:
            ComposeError: 没有可用素材时
        """
        pass

    def _generate_srt(self, shots: list[dict], output_path: str) -> str:
        """生成SRT字幕文件"""
        pass

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """将秒数转换为SRT时间格式 HH:MM:SS,mmm"""
        pass


class ComposeError(Exception):
    pass
```

### 7.6 成本追踪服务（`src/services/cost_tracker.py`）

```python
from src.schemas.cost import CostTracker, BudgetStatus, TokenUsage


class CostTrackerService:
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def record_token_usage(self, agent_name: str, usage: dict) -> None:
        token_usage = TokenUsage(**usage)
        self.tracker.usage.tokens[agent_name] = token_usage
        self.tracker.usage.total_cost += token_usage.cost
        self._update_status()

    def record_image_generation(self, count: int = 1, cost: float = 0.0) -> None:
        self.tracker.usage.images.ai_generated += count
        self.tracker.usage.images.cost += cost
        self.tracker.usage.total_cost += cost
        self._update_status()

    def record_tts_cost(self, cost: float) -> None:
        self.tracker.usage.tts_cost += cost
        self.tracker.usage.total_cost += cost
        self._update_status()

    def is_exceeded(self) -> bool:
        u = self.tracker.usage
        b = self.tracker.budget
        total_tokens = sum(t.prompt_tokens + t.completion_tokens for t in u.tokens.values())
        return (
            total_tokens > b.max_tokens
            or u.images.ai_generated > b.max_images
            or u.total_cost > b.cost_limit
        )

    def _update_status(self) -> None:
        if self.is_exceeded():
            self.tracker.status = BudgetStatus.EXCEEDED
        elif self.tracker.usage.total_cost > self.tracker.budget.cost_limit * 0.8:
            self.tracker.status = BudgetStatus.WARNING

    def get_tracker(self) -> CostTracker:
        return self.tracker

    def print_report(self) -> str:
        u = self.tracker.usage
        lines = [
            "=" * 40,
            "成本报告",
            "=" * 40,
            "Token消耗:",
        ]
        for agent, t in u.tokens.items():
            lines.append(f"  {agent}: {t.prompt_tokens}+{t.completion_tokens} tokens ({t.model}) = ¥{t.cost:.4f}")
        lines.extend([
            f"图片/视频生成: {u.images.ai_generated}张 = ¥{u.images.cost:.4f}",
            f"TTS: ¥{u.tts_cost:.4f}",
            f"{'─' * 40}",
            f"总计: ¥{u.total_cost:.4f} / 预算 ¥{self.tracker.budget.cost_limit:.2f}",
            f"状态: {self.tracker.status.value}",
            "=" * 40,
        ])
        return "\n".join(lines)
```

---

## 8. 成本控制体系

### 8.1 Token花费控制

| 策略 | 做法 | 预估节省 |
|------|------|----------|
| **模型分级路由** | 编剧用creative(temperature=0.8)，审核用efficient(temperature=0.3)，导演/剪辑不调LLM | ~60% |
| **Prompt模板化** | 预定义分镜模板(科普/剧情/带货)，LLM只填充差异部分 | ~30% |
| **结构化输出** | 强制JSON Schema输出（response_format=json_object），避免冗余文本 | ~15% |
| **上下文裁剪** | Agent间只传必要字段，不传完整对话历史 | ~20% |

### 8.2 模型分级策略

```
┌──────────────────────────────────────────────────────────┐
│                    模型路由表                              │
├────────────────┬─────────────────────────────────────────┤
│ 高创意任务      │ deepseek-chat (temperature=0.8)        │
│ (编剧)         │ 成本: $1/M prompt, $2/M completion     │
├────────────────┼─────────────────────────────────────────┤
│ 结构化任务      │ deepseek-chat (temperature=0.3)        │
│ (审核)         │ 成本: 同上                              │
├────────────────┼─────────────────────────────────────────┤
│ 机械任务        │ 规则引擎 / MoviePy / Edge-TTS          │
│ (导演/剪辑/TTS) │ 成本: 免费                             │
├────────────────┼─────────────────────────────────────────┤
│ 视频生成        │ 可灵 kling-v2-5-turbo                  │
│ (剪辑Agent)    │ 成本: $0.35/5s, $0.49/5s(pro)          │
└────────────────┴─────────────────────────────────────────┘
```

### 8.3 生成花费控制

| 策略 | 做法 |
|------|------|
| **可灵视频生成** | 优先使用可灵生成视频片段，Kling失败回退到占位图 |
| **条件初始化** | Kling Key未配置时跳过Kling，直接使用占位图，避免无效API调用 |
| **成本追踪** | 每个镜头生成后立即记录成本，占位图cost=0.0 |
| **素材复用池** | 生成过的素材入库，后续视频优先检索复用（完整版） |

### 8.4 预算控制器

每个视频任务初始化时创建预算控制器：

```python
from src.schemas.cost import CostTracker, Budget

tracker = CostTracker(
    video_id=video_id,
    budget=Budget(
        max_tokens=8000,
        max_images=8,
        max_retry_rounds=2,
        cost_limit=5.0,
        currency="CNY",
    )
)
```

**超限降级策略**：

| 超限类型 | 检测条件 | 降级动作 |
|----------|----------|----------|
| Token超限 | total_tokens > max_tokens | 缩减shot_count |
| 图片/视频超限 | ai_generated > max_images | 使用占位图 |
| 重试超限 | review_round > max_retry_rounds | 停止审核循环，输出当前最佳版本 |
| 总成本超限 | total_cost > cost_limit | 立即停止，输出中间结果和成本报告 |

### 8.5 成本预估（单条视频）

| 环节 | 成本 |
|------|------|
| 编剧Agent (DeepSeek, ~2000 tokens) | ~¥0.01 |
| 审核Agent (DeepSeek, ~1500 tokens) | ~¥0.01 |
| 可灵视频生成 (6个镜头×5s×turbo) | ~¥15.12 (6×$0.35×7.2) |
| 占位图回退（Kling不可用时） | ¥0.00 |
| TTS (Edge-TTS) | ¥0.00 |
| **合计（可灵）** | **~¥15.14** |
| **合计（占位图）** | **~¥0.02** |

> 注意：可灵视频生成成本较高，预算控制器默认cost_limit=5.0 CNY可能不够。
> 建议根据实际需求调整cost_limit，或在Kling不可用时使用占位图模式。

---

## 9. 错误处理策略

### 9.1 错误分类

| 类别 | 示例 | 处理方式 |
|------|------|----------|
| **可重试错误** | LLM返回非法JSON、API超时 | LLMService内部重试最多2次 |
| **可恢复错误** | 审核不通过、Kling生成失败、Edge-TTS失败 | 继续流程（降级或打回） |
| **不可恢复错误** | 预算超限、API Key无效、MoviePy合成失败 | 立即停止，输出中间结果 |
| **用户取消** | 人工审核时选择取消 | 退出 |

### 9.2 LLM输出错误处理

```
调用DeepSeek
  │
  ├─ 返回有效JSON → 解析成功 → 继续
  │
  ├─ 返回非法JSON → 重试(最多2次)
  │   ├─ 第2次成功 → 继续
  │   └─ 第2次失败 → 追加错误提示重试
  │       ├─ 成功 → 继续
  │       └─ 失败 → 抛出LLMOutputError → 流水线停止
  │
  └─ API异常 → OpenAI SDK自动重试 → 仍失败则抛出异常
```

### 9.3 视频/图片生成错误处理

```
生成素材（每个镜头）
  │
  ├─ 有Kling Key:
  │   ├─ Kling成功 → 记录clip，追踪成本
  │   └─ Kling失败 → 回退到占位图，cost=0.0
  │
  └─ 无Kling Key:
      └─ 直接生成占位图，cost=0.0
```

### 9.4 TTS错误处理

```
Edge-TTS合成
  │
  ├─ 成功 → 返回音频路径
  │
  ├─ edge-tts未安装 → 降级为静音WAV
  │
  └─ 合成异常 → 降级为静音WAV（不中断流水线）
```

### 9.5 全局错误处理（`src/main.py`）

```python
try:
    result = graph.invoke(initial_state)
    tracker_service = CostTrackerService(result["cost_tracker"])
    print(tracker_service.print_report())
    if result.get("final_video_path"):
        print(f"\n最终视频: {result['final_video_path']}")
except BudgetExceededError as e:
    print("预算超限，流水线停止。")
    print(CostTrackerService(initial_state["cost_tracker"]).print_report())
except AgentError as e:
    if not e.recoverable:
        print(f"不可恢复错误: {e}")
    else:
        print(f"Agent错误: {e}")
except KeyboardInterrupt:
    print("\n用户中断")
except Exception as e:
    logger.exception("unexpected_error")
    print(f"\n流水线执行失败: {e}")
```

---

## 10. MVP方案

### 10.1 MVP目标

**输入一个主题 → 输出一条可发布的短视频**，验证核心链路可行性。

### 10.2 MVP Agent精简

| Agent | MVP状态 | 说明 |
|-------|---------|------|
| 选题Agent | 不做 | 用户直接输入主题 |
| 编剧Agent | 保留 | DeepSeek生成，输出分镜脚本 |
| 导演Agent | 保留 | **纯规则引擎**，不调LLM |
| 素材Agent | 合并 | 合并进剪辑Agent（可灵+占位图） |
| 配音Agent | 合并 | 合并进剪辑Agent（Edge-TTS） |
| 剪辑Agent | 保留 | 可灵视频+Edge-TTS+MoviePy合成 |
| 审核Agent | 保留 | 规则检查+DeepSeek内容评估 |
| 发布Agent | 不做 | 输出本地文件，手动发布 |

**MVP = 4个Agent：编剧 + 导演 + 剪辑 + 审核**

### 10.3 MVP技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Agent框架 | LangGraph | 状态机天然支持审核打回循环 |
| LLM | DeepSeek (deepseek-chat) | 成本低，中文能力强，兼容OpenAI API |
| AI视频生成 | 可灵 (Kling) | 文生视频，支持9:16竖屏，JWT认证 |
| 图片生成 | Pillow占位图 | MVP阶段免费，未来替换为DALL-E 3 |
| TTS | Edge-TTS | 免费、中文效果好、零成本 |
| 视频合成 | MoviePy | Python原生，支持视频/图片/字幕合成 |
| 人工审核 | 终端 input() | MVP不需要前端 |
| 配置管理 | Pydantic Settings | 类型安全的配置 |
| 日志 | structlog | 结构化日志，便于追踪 |

### 10.4 MVP验证指标

| 指标 | 目标值 |
|------|--------|
| 端到端耗时 | ≤ 5分钟（含可灵视频生成轮询） |
| 视频完整性 | 画面+配音+字幕全部具备 |
| 审核有效性 | 能识别敏感词并打回低质量内容 |
| 人工修改生效 | 修改脚本后正确影响成片 |
| 视频分辨率 | 1080×1920, 30fps |

### 10.5 MVP入口程序（`src/main.py`）

```python
import sys
import uuid
import logging
import structlog

from src.graph import build_graph
from src.schemas.cost import CostTracker
from src.services.cost_tracker import CostTrackerService
from src.agents.base import AgentError, BudgetExceededError
from config.settings import settings

logger = structlog.get_logger()

LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def main():
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            LOG_LEVEL_MAP.get(settings.log_level.upper(), logging.INFO)
        ),
    )

    print("=" * 60)
    print("  AI Video Studio - MVP")
    print("=" * 60)

    if not settings.deepseek_api_key:
        print("错误: 请在.env文件中配置 DEEPSEEK_API_KEY")
        sys.exit(1)

    user_input = input("请输入视频主题: ").strip()
    if not user_input:
        print("主题不能为空")
        sys.exit(1)

    print("\n内容类型:")
    print("  [1] 知识科普  [2] 故事/剧情  [3] 热点追踪  [4] 产品带货")
    type_choice = input("请选择 (默认1): ").strip() or "1"
    content_type_map = {"1": "science", "2": "story", "3": "trending", "4": "product"}
    content_type = content_type_map.get(type_choice, "science")

    tone_input = input("语气风格 (默认: 幽默通俗): ").strip() or "幽默通俗"
    duration_input = input("目标时长/秒 (默认: 60): ").strip() or "60"
    duration = int(duration_input)

    video_id = str(uuid.uuid4())[:8]

    initial_state = {
        "video_id": video_id,
        "user_input": user_input,
        "content_type": content_type,
        "tone": tone_input,
        "duration": duration,
        "script": None,
        "production_plan": None,
        "generated_clips": {},
        "generated_images": {},
        "generated_audios": {},
        "video_draft_path": None,
        "final_video_path": None,
        "review_report": None,
        "review_round": 0,
        "cost_tracker": CostTracker(video_id=video_id),
        "human_feedback": None,
        "human_action": None,
        "status": "pending",
        "error": None,
    }

    graph = build_graph()

    try:
        result = graph.invoke(initial_state)
        tracker_service = CostTrackerService(result["cost_tracker"])
        print(tracker_service.print_report())
        if result.get("final_video_path"):
            print(f"\n最终视频: {result['final_video_path']}")
    except BudgetExceededError as e:
        logger.error("budget_exceeded", error=str(e))
        print("预算超限，流水线停止。")
        print(CostTrackerService(initial_state["cost_tracker"]).print_report())
    except AgentError as e:
        logger.error("agent_error", agent=e.agent_name, error=str(e))
        if not e.recoverable:
            print(f"不可恢复错误: {e}")
        else:
            print(f"Agent错误: {e}")
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        logger.exception("unexpected_error")
        print(f"\n流水线执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## 11. 完整版方案

### 11.1 完整版新增能力

| 模块 | 能力 | 优先级 |
|------|------|--------|
| 选题Agent | 热点追踪、竞品分析、选题推荐 | P0 |
| 发布Agent | 抖音/TikTok API发布、定时发布 | P0 |
| AI生图 | DALL-E 3 / 通义万相替换占位图 | P0 |
| 素材复用池 | 向量检索+素材管理 | P1 |
| Web前端 | 可视化编辑器、时间线、审核界面 | P1 |
| 多账号管理 | 多平台多账号发布管理 | P1 |
| BGM混音 | MoviePy合成时混入BGM | P1 |
| 数据复盘 | 发布后数据追踪、效果分析 | P2 |
| A/B测试 | 标题/封面多版本测试 | P2 |
| 批量生产 | 批量选题、批量生成、队列管理 | P2 |

### 11.2 完整版技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 前端 | Next.js + TailwindCSS | 可视化编辑器、时间线 |
| 后端API | FastAPI | 高性能异步API |
| Agent框架 | LangGraph | 状态机+人机协作 |
| LLM | DeepSeek + Qwen | 多模型路由 |
| AI视频生成 | 可灵 / Sora / Runway | 按场景选择 |
| AI生图 | DALL-E 3 + SD-XL + 通义万相 | 分级生成 |
| TTS | Edge-TTS + Fish Audio | 免费+高质量 |
| 视频处理 | MoviePy | 程序化剪辑 |
| 数据库 | PostgreSQL | 元数据、用户、任务 |
| 缓存 | Redis | 缓存+消息队列 |
| 对象存储 | MinIO | 素材、视频文件 |
| 向量数据库 | Milvus | 素材语义检索 |
| 任务队列 | Celery + Redis | 异步任务处理 |
| 监控 | Prometheus + Grafana | 系统+成本监控 |
| 部署 | Docker + Docker Compose | 容器化部署 |

### 11.3 完整版数据模型

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │     │  Project    │     │  Video      │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │────<│ id          │────<│ id          │
│ name        │     │ user_id     │     │ project_id  │
│ email       │     │ name        │     │ script      │
│ api_keys    │     │ created_at  │     │ status      │
└─────────────┘     └─────────────┘     │ cost        │
                                        │ video_url   │
                                        │ created_at  │
                                        └──────┬──────┘
                                               │
                    ┌─────────────┐     ┌──────┴──────┐
                    │  Asset      │     │  Review     │
                    ├─────────────┤     ├─────────────┤
                    │ id          │     │ id          │
                    │ video_id    │     │ video_id    │
                    │ type        │     │ round       │
                    │ url         │     │ score       │
                    │ embedding   │     │ verdict     │
                    │ reuse_count │     │ issues      │
                    │ created_at  │     │ created_at  │
                    └─────────────┘     └─────────────┘
```

---

## 12. 技术选型与依赖

### 12.1 pyproject.toml

```toml
[project]
name = "ai-video-studio"
version = "0.1.0"
description = "Multi-agent video production system"
requires-python = ">=3.11"

dependencies = [
    "langgraph>=0.2.0",
    "openai>=1.50.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "moviepy>=2.0.0",
    "Pillow>=10.0",
    "numpy>=1.24.0",
    "httpx>=0.27.0",
    "PyJWT>=2.8.0",
    "edge-tts>=6.1.0",
    "structlog>=24.0",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "ruff>=0.5.0",
]

[project.scripts]
ai-video-studio = "src.main:main"

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 12.2 系统依赖

| 依赖 | 安装方式 | 用途 |
|------|----------|------|
| Python 3.11+ | pyenv / 系统安装 | 运行环境 |
| FFmpeg | `apt install ffmpeg` / `brew install ffmpeg` | MoviePy底层依赖 |

---

## 13. 配置与环境变量

### 13.1 .env.example

```env
# DeepSeek LLM配置
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 可灵视频生成配置 (https://klingai.com/global/dev/api)
KLING_ACCESS_KEY=your_access_key
KLING_SECRET_KEY=your_secret_key
KLING_BASE_URL=https://api.klingai.com
KLING_MODEL=kling-v2-5-turbo

# 预算控制
MAX_TOKENS_PER_VIDEO=8000
MAX_IMAGES_PER_VIDEO=8
MAX_RETRY_ROUNDS=2
COST_LIMIT_PER_VIDEO=5.0

# 输出目录
OUTPUT_DIR=./output

# 日志级别
LOG_LEVEL=INFO

# 视频默认配置
DEFAULT_RESOLUTION=1080x1920
DEFAULT_FPS=30
DEFAULT_ASPECT_RATIO=9:16
```

### 13.2 配置类（`config/settings.py`）

```python
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepseek_api_key: str = Field(default="", description="DeepSeek API Key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com")

    kling_access_key: str = Field(default="", description="可灵 Access Key")
    kling_secret_key: str = Field(default="", description="可灵 Secret Key")
    kling_base_url: str = Field(default="https://api.klingai.com")
    kling_model: str = Field(default="kling-v2-5-turbo", description="可灵模型")

    max_tokens_per_video: int = Field(default=8000)
    max_images_per_video: int = Field(default=8)
    max_retry_rounds: int = Field(default=2)
    cost_limit_per_video: float = Field(default=5.0)

    output_dir: str = Field(default="./output")
    log_level: str = Field(default="INFO")

    default_voice_speed: float = Field(default=1.0)

    default_resolution: str = Field(default="1080x1920")
    default_fps: int = Field(default=30)
    default_aspect_ratio: str = Field(default="9:16")


settings = Settings()
```

---

## 14. 项目结构与实现顺序

### 14.1 完整项目结构

```
ai-video-studio/
├── pyproject.toml
├── .env.example
├── .env                          # 本地配置（gitignore）
├── .gitignore
├── README.md
├── CODE_STRUCTURE.md             # 代码结构说明文档
│
├── config/
│   ├── __init__.py
│   ├── settings.py               # Pydantic Settings配置
│   └── templates/                # Prompt模板文件
│       ├── screenwriter/
│       │   ├── science.txt
│       │   ├── story.txt
│       │   ├── trending.txt
│       │   └── product.txt
│       ├── director/
│       │   └── default.txt       # 保留，未来LLM化导演Agent使用
│       └── reviewer/
│           └── default.txt
│
├── src/
│   ├── __init__.py
│   ├── main.py                   # CLI入口
│   ├── graph.py                  # LangGraph状态机定义
│   ├── state.py                  # VideoState类型定义
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py               # BaseAgent + 异常类
│   │   ├── screenwriter.py       # 编剧Agent（调DeepSeek）
│   │   ├── director.py           # 导演Agent（纯规则引擎）
│   │   ├── editor.py             # 剪辑Agent（可灵+TTS+MoviePy）
│   │   └── reviewer.py           # 审核Agent（规则+DeepSeek）
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py                # DeepSeek LLM调用（OpenAI SDK）
│   │   ├── kling.py              # 可灵视频生成API（JWT认证）
│   │   ├── image_gen.py          # 占位图生成（Pillow）
│   │   ├── tts.py                # Edge-TTS语音合成（含静音降级）
│   │   ├── video_compose.py      # MoviePy视频合成
│   │   └── cost_tracker.py       # 成本追踪服务
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── script.py             # Script Pydantic模型
│   │   ├── plan.py               # ProductionPlan模型
│   │   ├── review.py             # ReviewReport模型
│   │   └── cost.py               # CostTracker模型
│   │
│   └── utils/
│       ├── __init__.py
│       ├── media.py              # 媒体工具（获取视频时长/分辨率）
│       └── sensitive_words.py    # 敏感词检测
│
├── output/                       # 运行时输出（gitignore）
│
└── tests/
    ├── __init__.py
    ├── conftest.py               # pytest fixtures
    ├── test_schemas.py           # Schema校验测试
    ├── test_screenwriter.py      # 编剧Agent测试
    ├── test_director.py          # 导演Agent测试
    ├── test_editor.py            # 剪辑Agent测试
    ├── test_reviewer.py          # 审核Agent测试
    ├── test_kling.py             # 可灵API测试
    ├── test_cost_tracker.py      # 成本追踪测试
    └── test_graph.py             # 状态机路由测试
```

### 14.2 推荐实现顺序

```
Step 1: 项目骨架
├── pyproject.toml、.env.example、config/settings.py
├── 所有__init__.py、src/state.py
└── 验证: pip install -e . 能成功

Step 2: Schema定义
├── src/schemas/cost.py、script.py、plan.py、review.py
└── 验证: test_schemas.py 全部通过

Step 3: Service层
├── cost_tracker.py、llm.py、kling.py、image_gen.py、tts.py、video_compose.py
└── 验证: 每个service单元测试通过

Step 4: 编剧Agent
├── config/templates/screenwriter/*.txt
├── src/agents/base.py、screenwriter.py
└── 验证: Mock LLM后能输出合法Script JSON

Step 5: 导演Agent
├── src/agents/director.py（纯规则，不调LLM）
└── 验证: 输入Script能输出合法ProductionPlan

Step 6: 剪辑Agent
├── src/agents/editor.py、src/utils/media.py
└── 验证: 输入Script+Plan能输出可播放的.mp4

Step 7: 审核Agent
├── config/templates/reviewer/default.txt
├── src/agents/reviewer.py、src/utils/sensitive_words.py
└── 验证: 输入Script能输出ReviewReport

Step 8: LangGraph状态机 + 入口
├── src/graph.py、src/main.py
└── 验证: 端到端运行，输入主题→输出视频

Step 9: 测试 + 优化
├── tests/test_graph.py（集成测试）
├── 错误处理完善
└── 验证: 完整流程跑通
```

---

## 15. 测试策略

### 15.1 测试层次

| 层次 | 范围 | Mock策略 | 工具 |
|------|------|----------|------|
| Schema测试 | Pydantic模型校验 | 无需Mock | pytest |
| Service单元测试 | 各Service方法 | Mock外部API | pytest + pytest-mock |
| Agent单元测试 | 各Agent逻辑 | Mock Service层 | pytest + pytest-mock |
| 路由测试 | 状态机路由函数 | 构造State dict | pytest |
| 端到端测试 | 真实API调用 | 不Mock | 手动运行 |

### 15.2 测试文件清单

| 测试文件 | 测试内容 | 用例数 |
|----------|----------|--------|
| test_schemas.py | Script/Plan/Review/Cost Schema校验、序列化、边界值 | 11 |
| test_screenwriter.py | shot_count计算、Agent执行（Mock LLM）、feedback追加 | 9 |
| test_director.py | 质量决策、BGM风格、字幕动画、转场决策 | 10 |
| test_editor.py | SRT时间格式、SRT文件生成 | 2 |
| test_reviewer.py | 敏感词检测 | 4 |
| test_kling.py | JWT生成、Headers格式、价格查找 | 3 |
| test_cost_tracker.py | 初始状态、token/图片记录、超限检测、warning状态、报告输出 | 8 |
| test_graph.py | 脚本审核路由、自动审核路由、成片审核路由 | 9 |

### 15.3 conftest.py fixtures

```python
@pytest.fixture
def sample_shot() -> Shot:
    """提供一个合法的示例Shot"""

@pytest.fixture
def sample_script(sample_shot) -> Script:
    """提供一个包含2个镜头的合法Script"""

@pytest.fixture
def sample_cost_tracker() -> CostTracker:
    """提供一个默认预算的CostTracker"""

@pytest.fixture
def mock_llm():
    """Mock LLM服务"""

@pytest.fixture
def mock_image_gen():
    """Mock图片生成服务"""
```

---

## 16. 迭代路线图

```
Phase 1 — MVP (当前) ✅
├── 编剧Agent (DeepSeek) + 导演Agent (规则) + 剪辑Agent + 审核Agent
├── 可灵视频生成 + Edge-TTS配音 + MoviePy合成
├── 终端人工审核
├── 成本追踪
└── 输出: 本地1080×1920视频文件

Phase 2 — 素材增强
├── DALL-E 3 / 通义万相替换占位图
├── BGM混音（MoviePy合成时混入）
├── 素材复用池（向量检索）
├── 更多转场效果和字幕样式
└── 输出: 更高质量的视频

Phase 3 — 选题+发布
├── 选题Agent（热点追踪、竞品分析）
├── 发布Agent（抖音/TikTok API）
├── 定时发布
├── 封面自动生成
└── 输出: 从选题到发布的完整闭环

Phase 4 — Web平台
├── Web前端（可视化编辑器、时间线）
├── 多账号管理
├── 项目管理
├── 批量生产
└── 输出: 可多人协作的Web平台

Phase 5 — 数据驱动
├── 数据复盘（播放、点赞、评论追踪）
├── A/B测试（标题/封面）
├── 内容策略优化建议
├── 成本分析看板
└── 输出: 数据驱动的内容优化系统
```

---

## 17. 风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|----------|
| DeepSeek生成质量不稳定 | 脚本质量差，影响成片 | 模板化约束+审核Agent把关+人工兜底 |
| 可灵视频与内容不匹配 | 画面和旁白脱节 | 精细化image_prompt+审核Agent检查匹配度 |
| 可灵API成本较高 | 6个镜头约¥15 | 预算控制器+占位图降级模式 |
| 可灵API不可用/超时 | 视频生成失败 | 条件初始化+自动降级为占位图 |
| Edge-TTS不可用 | 无配音 | 自动降级为静音音频 |
| 平台API限制 | 无法自动发布 | 先支持本地导出，手动发布 |
| 内容合规风险 | 账号封禁 | 审核Agent敏感词检查+LLM合规评估 |
| LLM返回非法JSON | 流水线中断 | LLMService重试机制+错误提示追加 |
| MoviePy合成失败 | 无成片输出 | 跳过失败镜头+ComposeError异常处理 |
