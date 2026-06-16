# AI Video Studio — 系统设计文档

> 多Agent协作的短视频自动化生产系统，面向抖音/TikTok内容创作
>
> **本文档面向AI辅助开发，包含足够的实现细节，可直接据此编码。**

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

### 2.1 整体架构图

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

### 2.2 分层职责

| 层 | 职责 | 关键组件 |
|----|------|----------|
| 用户交互层 | 用户输入、人工审核、数据展示 | Web前端 / CLI / API |
| 编排调度层 | Agent编排、状态管理、流程控制、预算控制 | LangGraph状态机 |
| Agent执行层 | 各Agent独立执行具体任务 | 8个专职Agent |
| 基础设施层 | LLM调用、媒体处理、存储、队列 | 各类外部服务 |

### 2.3 Agent间通信规则

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
from typing import Optional
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
    image_prompt: str = Field(min_length=10, max_length=500, description="画面描述，用于AI生图，要求具体、可视化")
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
    generate_prompt: str = Field(default="", description="AI生图prompt（source=ai_generate时使用，可覆盖script中的image_prompt）")
    image_model: str = Field(default="dall-e-3", description="使用的生图模型")


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
from typing import Optional, Annotated
from typing_extensions import TypedDict
from langgraph.graph import add_messages
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
| `generated_images` | dict[int, str] | 镜头ID→图片文件路径 | 剪辑Agent |
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
| `screenwriting` | 编剧中 |
| `awaiting_script_review` | 等待人工审核脚本 |
| `directing` | 导演规划中 |
| `editing` | 剪辑合成中 |
| `reviewing` | 自动审核中 |
| `awaiting_video_review` | 等待人工审核成片 |
| `completed` | 完成 |
| `failed` | 失败 |
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
        """
        执行Agent逻辑。

        Args:
            state: 当前LangGraph状态

        Returns:
            dict: 需要更新的State字段（部分更新，不是完整State）

        Raises:
            AgentError: Agent执行失败时抛出
            BudgetExceededError: 预算超限时抛出
        """
        pass

    def check_budget(self, state: VideoState) -> None:
        """检查预算是否超限，超限则抛出BudgetExceededError"""
        tracker = CostTrackerService(state["cost_tracker"])
        if tracker.is_exceeded():
            raise BudgetExceededError(
                f"Agent {self.name}: 预算超限，当前花费 {tracker.total_cost}"
            )

    def update_cost(self, state: VideoState, **kwargs) -> CostTracker:
        """更新成本追踪器，返回更新后的CostTracker"""
        tracker = CostTrackerService(state["cost_tracker"])
        tracker.record(self.name, **kwargs)
        return tracker.get_tracker()


class AgentError(Exception):
    def __init__(self, agent_name: str, message: str, recoverable: bool = True):
        self.agent_name = agent_name
        self.recoverable = recoverable
        super().__init__(f"[{agent_name}] {message}")


class BudgetExceededError(AgentError):
    def __init__(self, message: str):
        super().__init__("budget", message, recoverable=False)
```

### 4.3 编剧Agent接口（`src/agents/screenwriter.py`）

```python
class ScreenwriterAgent(BaseAgent):
    """
    编剧Agent：将用户主题转化为结构化分镜脚本。

    输入State字段：user_input, content_type, tone, duration
    输出State字段：script
    使用模型：GPT-4o（高创意任务）
    """

    def __init__(self):
        super().__init__("screenwriter")
        self.llm = LLMService(model_tier="creative")
        self.prompt_templates = load_prompt_templates("screenwriter")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 根据content_type选择对应的prompt模板
        2. 填充模板变量（topic, tone, duration, shot_count）
        3. 调用LLM，强制JSON Schema输出
        4. 解析并校验返回的JSON
        5. 如果解析失败，重试最多2次（每次追加错误提示）
        6. 记录token消耗到cost_tracker

        Returns:
            {"script": Script实例, "cost_tracker": 更新后的CostTracker}
        """
        pass
```

**编剧Agent的shot_count计算规则**：

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

### 4.4 导演Agent接口（`src/agents/director.py`）

```python
class DirectorAgent(BaseAgent):
    """
    导演Agent：将分镜脚本转化为可执行的制作任务书。

    输入State字段：script
    输出State字段：production_plan
    使用模型：GPT-4o-mini（决策型任务）
    """

    def __init__(self):
        super().__init__("director")
        self.llm = LLMService(model_tier="efficient")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 分析script中每个shot的priority和image_prompt
        2. 决策每个shot的素材来源（ai_generate/stock/reuse）
           - priority=high → ai_generate
           - priority=normal → 50%概率ai_generate, 50%stock
           - priority=low → stock/reuse
        3. 选择BGM风格（基于global_settings.bgm_style和整体tone）
        4. 确定转场策略和剪辑节奏
        5. 生成ProductionPlan

        MVP简化：所有镜头都用ai_generate，不做素材库检索。

        Returns:
            {"production_plan": ProductionPlan实例, "cost_tracker": 更新后的CostTracker}
        """
        pass
```

**导演Agent的决策规则（MVP简化版）**：

```
对于每个shot:
  if shot.priority == "high":
      source = AI_GENERATE
      image_model = "dall-e-3"
      image_quality = "hd"
  elif shot.priority == "normal":
      source = AI_GENERATE
      image_model = "dall-e-3"
      image_quality = "standard"
  else:  # low
      source = AI_GENERATE
      image_model = "dall-e-3"
      image_quality = "standard"

BGM选择规则:
  if tone包含("幽默" or "轻松" or "通俗"):
      bgm_style = "轻快电子"
  elif tone包含("严肃" or "专业"):
      bgm_style = "简约钢琴"
  elif tone包含("悬疑" or "紧张"):
      bgm_style = "暗黑氛围"
  else:
      bgm_style = "轻快电子"
```

### 4.5 剪辑Agent接口（`src/agents/editor.py`）

```python
class EditorAgent(BaseAgent):
    """
    剪辑Agent：生成素材 + TTS配音 + FFmpeg合成视频。

    输入State字段：script, production_plan, review_report(可选，打回时)
    输出State字段：generated_images, generated_audios, video_draft_path
    使用模型：不调用LLM
    """

    def __init__(self):
        super().__init__("editor")
        self.image_service = ImageGenService()
        self.tts_service = TTSService()
        self.video_composer = VideoComposeService()

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 遍历production_plan.shot_sources，按策略生成/获取图片
           - 对每个shot调用image_service.generate()
           - 图片保存到 output/assets/{video_id}/shot_{id:02d}.png
        2. 遍历script.shots，为每个shot生成TTS音频
           - 对每个shot调用tts_service.synthesize()
           - 音频保存到 output/assets/{video_id}/narration_{id:02d}.mp3
        3. 调用video_composer.compose()合成最终视频
           - 输入：所有图片+音频+脚本信息
           - 输出：output/videos/{video_id}/draft.mp4
        4. 如果有review_report（打回场景），根据revision_instructions调整

        Returns:
            {
                "generated_images": {shot_id: file_path, ...},
                "generated_audios": {shot_id: file_path, ...},
                "video_draft_path": "output/videos/{video_id}/draft.mp4",
                "cost_tracker": 更新后的CostTracker
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
    │   ├── shot_01.png               # 镜头1图片
    │   ├── shot_02.png               # 镜头2图片
    │   ├── ...
    │   ├── narration_01.mp3          # 镜头1配音
    │   ├── narration_02.mp3          # 镜头2配音
    │   ├── ...
    │   ├── bgm.mp3                   # 背景音乐
    │   └── subtitles.srt             # 字幕文件
    ├── segments/
    │   ├── segment_01.mp4            # 镜头1视频片段
    │   ├── segment_02.mp4            # 镜头2视频片段
    │   └── ...
    ├── draft.mp4                      # 成片初稿
    ├── review.json                    # 审核报告
    └── final.mp4                      # 最终视频
```

### 4.6 审核Agent接口（`src/agents/reviewer.py`）

```python
class ReviewerAgent(BaseAgent):
    """
    审核Agent：多维度质量检查，通过或打回修改。

    输入State字段：script, video_draft_path, review_round
    输出State字段：review_report, review_round, final_video_path(通过时)
    使用模型：GPT-4o-mini（结构化评估任务）
    """

    PASS_SCORE = 60

    def __init__(self):
        super().__init__("reviewer")
        self.llm = LLMService(model_tier="efficient")

    def execute(self, state: VideoState) -> dict:
        """
        执行流程：
        1. 规则检查（不调LLM）：
           - 视频文件是否存在且可播放
           - 分辨率是否为1080x1920
           - 时长是否在合理范围
           - 字幕每行是否≤15字
        2. 内容审核（调LLM）：
           - 将script发送给LLM评估
           - 评估维度：叙事连贯性、信息密度、画面-旁白匹配度、吸引力
        3. 合规检查（规则+LLM）：
           - 敏感词库匹配（本地规则）
           - LLM判断是否有版权风险/虚假信息
        4. 计算加权总分
        5. 判定verdict

        Returns:
            {
                "review_report": ReviewReport实例,
                "review_round": 当前轮次+1,
                "final_video_path": 通过时为video_draft_path,
                "cost_tracker": 更新后的CostTracker
            }
        """
        pass
```

**审核评分权重**：

| 维度 | 权重 | 检查方式 | 一票否决 |
|------|------|----------|----------|
| compliance（合规） | — | 规则+LLM | 是 |
| technical_quality（技术质量） | 30% | 规则检查 | 否 |
| content_quality（内容质量） | 40% | LLM评估 | 否 |
| platform_fit（平台适配） | 30% | LLM评估 | 否 |

**加权总分计算**：
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

### 5.5 导演Agent（`config/templates/director/default.txt`）

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
json_schema = Script.model_json_schema()  # 编剧Agent
json_schema = ProductionPlan.model_json_schema()  # 导演Agent
json_schema = ReviewReport.model_json_schema()  # 审核Agent
```

---

## 6. 工作流与状态机（LangGraph）

### 6.1 MVP工作流

```
用户输入主题(如"黑洞是什么")
       │
       ▼
   编剧Agent ──→ 分镜脚本JSON
       │
       ▼ (终端人工确认/修改)
   导演Agent ──→ 制作指令(风格/节奏/素材策略)
       │
       ▼
   剪辑Agent ──→ AI生图 + Edge-TTS + FFmpeg合成 → 成片.mp4
       │
       ▼
   审核Agent ──→ 通过 → 输出最终视频
               → 不通过 → 打回剪辑Agent(最多2轮)
       │
       ▼ (终端人工确认成片)
   成本报告输出
```

### 6.2 完整版工作流

```
用户输入(选题/热点/产品链接)
       │
       ▼
  ┌──────────┐
  │ 选题Agent │ ──→ 选题报告
  └────┬─────┘
       │
       ▼ (人工确认选题方向)
  ┌──────────┐
  │ 编剧Agent │ ──→ 分镜脚本JSON
  └────┬─────┘
       │
       ▼ (人工确认/修改脚本 ✏️)
  ┌──────────┐
  │ 导演Agent │ ──→ 制作任务书
  └────┬─────┘
       │
       ├───────────────┐
       ▼               ▼
  ┌──────────┐   ┌──────────┐
  │ 素材Agent │   │ 配音Agent │
  └────┬─────┘   └────┬─────┘
       │               │
       └───────┬───────┘
               ▼
         ┌──────────┐
         │ 剪辑Agent │ ──→ 成片初稿
         └────┬─────┘
              │
              ▼ (人工确认成片 ✏️)
         ┌──────────┐
         │ 审核Agent │
         └────┬─────┘
              │
         ┌────┴────┐
         ▼         ▼
       通过      不通过
         │         │
         ▼         ▼ (打回剪辑Agent，最多2轮)
    ┌──────────┐
    │ 发布Agent │ ──→ 抖音 / TikTok
    └────┬─────┘
         │
         ▼
    成本报告 + 数据追踪
```

### 6.3 LangGraph状态机完整实现（`src/graph.py`）

```python
from langgraph.graph import StateGraph, START, END
from src.state import VideoState
from src.agents.screenwriter import ScreenwriterAgent
from src.agents.director import DirectorAgent
from src.agents.editor import EditorAgent
from src.agents.reviewer import ReviewerAgent


def build_graph() -> StateGraph:
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
    """人工脚本审核后的路由"""
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def route_after_review(state: VideoState) -> str:
    """自动审核后的路由"""
    report = state["review_report"]
    if report.verdict == "approved":
        return "approved"
    if state["review_round"] >= report.max_rounds:
        return "max_rounds_reached"
    return "revision_needed"


def route_after_video_review(state: VideoState) -> str:
    """人工成片审核后的路由"""
    action = state.get("human_action")
    if action == "approve":
        return "approved"
    elif action == "revise":
        return "revision"
    else:
        return "cancelled"


def human_script_review_node(state: VideoState) -> dict:
    """人工审核脚本的交互节点"""
    script = state["script"]
    print("\n" + "=" * 60)
    print("📝 分镜脚本审核")
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
    """人工审核成片的交互节点"""
    video_path = state.get("final_video_path") or state["video_draft_path"]
    report = state.get("review_report")

    print("\n" + "=" * 60)
    print("🎬 成片审核")
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

```python
from openai import OpenAI
from pydantic import BaseModel
import json
import structlog

logger = structlog.get_logger()

MODEL_ROUTING = {
    "creative": {
        "model": "gpt-4o",
        "temperature": 0.8,
        "max_tokens": 4096,
    },
    "efficient": {
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 2048,
    },
}

TOKEN_PRICES = {
    "gpt-4o": {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
    "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
}


class LLMService:
    def __init__(self, model_tier: str = "efficient"):
        self.tier = model_tier
        self.config = MODEL_ROUTING[model_tier]
        self.client = OpenAI()

    def generate_structured(
        self,
        prompt: str,
        response_model: type[BaseModel],
        max_retries: int = 2,
    ) -> tuple[BaseModel, dict]:
        """
        调用LLM生成结构化JSON输出。

        Args:
            prompt: 完整的prompt文本
            response_model: Pydantic模型类，用于校验输出
            max_retries: JSON解析失败时的重试次数

        Returns:
            tuple: (解析后的Pydantic实例, usage信息dict)
                   usage格式: {"prompt_tokens": int, "completion_tokens": int, "model": str, "cost": float}

        Raises:
            LLMOutputError: 重试耗尽后仍无法获得有效输出
        """
        schema_str = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        full_prompt = f"{prompt}\n\n请严格按照以下JSON Schema输出：\n{schema_str}"

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    full_prompt += f"\n\n[第{attempt+1}次尝试] 上次输出格式有误：{last_error}，请修正后重新输出。"

                response = self.client.chat.completions.create(
                    model=self.config["model"],
                    messages=[{"role": "user", "content": full_prompt}],
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
        prices = TOKEN_PRICES[model]
        cost = (usage.prompt_tokens * prices["prompt"]
                + usage.completion_tokens * prices["completion"])
        cost_cny = cost * 7.2
        return {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "model": model,
            "cost": round(cost_cny, 4),
        }


class LLMOutputError(Exception):
    pass
```

### 7.2 AI生图服务（`src/services/image_gen.py`）

```python
from openai import OpenAI
import httpx
from pathlib import Path
import structlog

logger = structlog.get_logger()

IMAGE_PRICES = {
    "dall-e-3": {
        "1024x1792": {"hd": 0.08, "standard": 0.04},
    },
}


class ImageGenService:
    def __init__(self):
        self.client = OpenAI()

    def generate(
        self,
        prompt: str,
        output_path: str,
        model: str = "dall-e-3",
        size: str = "1024x1792",
        quality: str = "hd",
    ) -> dict:
        """
        调用AI生图API生成图片。

        Args:
            prompt: 图片描述prompt
            output_path: 保存路径（如 output/assets/xxx/shot_01.png）
            model: 模型名称
            size: 图片尺寸
            quality: 质量等级 hd/standard

        Returns:
            dict: {"path": str, "cost": float(CNY), "model": str}

        Raises:
            ImageGenError: 生成失败时
        """
        try:
            response = self.client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )

            image_url = response.data[0].url
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            with httpx.stream("GET", image_url, timeout=60) as r:
                r.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)

            usd_cost = IMAGE_PRICES.get(model, {}).get(size, {}).get(quality, 0.04)
            cny_cost = round(usd_cost * 7.2, 4)

            logger.info("image_generated", path=output_path, model=model, cost=cny_cost)
            return {"path": output_path, "cost": cny_cost, "model": model}

        except Exception as e:
            raise ImageGenError(f"图片生成失败: {e}")


class ImageGenError(Exception):
    pass
```

### 7.3 TTS服务（`src/services/tts.py`）

```python
import edge_tts
from pathlib import Path
import structlog

logger = structlog.get_logger()

AVAILABLE_VOICES = {
    "zh-CN-YunxiNeural": "男声-年轻-活泼",
    "zh-CN-YunyangNeural": "男声-成熟-新闻",
    "zh-CN-XiaoxiaoNeural": "女声-年轻-温暖",
    "zh-CN-XiaoyiNeural": "女声-年轻-甜美",
}


class TTSService:
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str = "zh-CN-YunxiNeural",
        rate: str = "+0%",
        volume: str = "+0%",
    ) -> dict:
        """
        使用Edge-TTS合成语音。

        Args:
            text: 要合成的文本
            output_path: 输出文件路径（.mp3）
            voice: 音色ID
            rate: 语速调整，如"+10%", "-10%"
            volume: 音量调整

        Returns:
            dict: {"path": str, "cost": 0.0}

        Raises:
            TTSError: 合成失败时
        """
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
            await communicate.save(output_path)

            logger.info("tts_synthesized", path=output_path, voice=voice)
            return {"path": output_path, "cost": 0.0}

        except Exception as e:
            raise TTSError(f"TTS合成失败: {e}")

    @staticmethod
    def speed_to_rate(speed: float) -> str:
        """将speed倍率转换为Edge-TTS的rate格式。1.0→+0%, 1.1→+10%, 0.9→-10%"""
        pct = int((speed - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"


class TTSError(Exception):
    pass
```

### 7.4 视频合成服务（`src/services/video_compose.py`）

```python
import subprocess
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
        images: dict[int, str],
        audios: dict[int, str],
        bgm_path: str | None,
        subtitle_path: str,
        output_path: str,
        global_settings: dict,
    ) -> str:
        """
        合成最终视频。

        执行流程：
        1. 为每个镜头生成视频片段（图片+音频+转场效果）
        2. 生成SRT字幕文件
        3. 拼接所有片段
        4. 叠加BGM
        5. 烧录字幕

        Args:
            shots: 镜头列表（从Script.shots序列化）
            images: {shot_id: 图片路径}
            audios: {shot_id: 音频路径}
            bgm_path: BGM文件路径（可选）
            subtitle_path: SRT字幕文件路径
            output_path: 最终输出路径
            global_settings: 全局设置

        Returns:
            str: 输出视频文件路径

        Raises:
            ComposeError: 合成失败时
        """
        pass

    def _generate_segment(
        self,
        shot: dict,
        image_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        """
        为单个镜头生成视频片段。

        FFmpeg命令逻辑：
        1. 将图片缩放到1080x1920（保持比例+填充黑边）
        2. 应用camera_effect（zoompan实现Ken Burns等效果）
        3. 设置时长为shot.duration
        4. 混入音频
        """
        duration = shot["duration"]
        frames = int(duration * FPS)

        camera_effect = shot.get("camera_effect", "ken_burns")
        zoompan = self._get_zoompan_filter(camera_effect, frames)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-vf", f"{zoompan},scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-r", str(FPS),
            "-shortest",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise ComposeError(f"片段生成失败: {result.stderr}")
        return output_path

    def _get_zoompan_filter(self, effect: str, frames: int) -> str:
        """将camera_effect转换为FFmpeg zoompan滤镜"""
        w, h = VIDEO_WIDTH, VIDEO_HEIGHT
        filters = {
            "static": f"scale={w}:{h}:force_original_aspect_ratio=increase",
            "zoom_in_slow": f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,zoompan=z='min(zoom+0.0005,1.3)':d={frames}:s={w}x{h}:fps={FPS}",
            "zoom_out_slow": f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,zoompan=z='if(eq(on,1),1.3,max(zoom-0.0005,1.0))':d={frames}:s={w}x{h}:fps={FPS}",
            "ken_burns": f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,zoompan=z='min(zoom+0.0008,1.4)':x='iw/2-(iw/zoom/2)+({frames}-on)*0.3':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}",
            "pan_left": f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,zoompan=z='1.2':x='({frames}-on)*0.5':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}",
            "pan_right": f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,zoompan=z='1.2':x='on*0.5':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={FPS}",
        }
        return filters.get(effect, filters["ken_burns"])

    def _generate_srt(self, shots: list[dict], output_path: str) -> str:
        """
        生成SRT字幕文件。

        格式：
        1
        00:00:00,000 --> 00:00:05,000
        字幕第一行
        字幕第二行

        2
        00:00:05,000 --> 00:00:15,000
        ...
        """
        pass

    def _concat_segments(self, segment_paths: list[str], output_path: str) -> str:
        """使用FFmpeg concat协议拼接视频片段"""
        pass

    def _mix_bgm(self, video_path: str, bgm_path: str, output_path: str, bgm_volume: float) -> str:
        """混合BGM到视频中"""
        pass

    def _burn_subtitles(self, video_path: str, srt_path: str, output_path: str, settings: dict) -> str:
        """烧录字幕到视频中"""
        pass


class ComposeError(Exception):
    pass
```

### 7.5 成本追踪服务（`src/services/cost_tracker.py`）

```python
from src.schemas.cost import CostTracker, BudgetStatus, TokenUsage, ImageUsage, Usage


class CostTrackerService:
    def __init__(self, tracker: CostTracker):
        self.tracker = tracker

    def record_token_usage(self, agent_name: str, usage: dict) -> None:
        """记录token使用"""
        token_usage = TokenUsage(**usage)
        self.tracker.usage.tokens[agent_name] = token_usage
        self.tracker.usage.total_cost += token_usage.cost
        self._update_status()

    def record_image_generation(self, count: int = 1, cost: float = 0.0) -> None:
        """记录图片生成"""
        self.tracker.usage.images.ai_generated += count
        self.tracker.usage.images.cost += cost
        self.tracker.usage.total_cost += cost
        self._update_status()

    def is_exceeded(self) -> bool:
        """检查是否超预算"""
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
        """生成可读的成本报告"""
        u = self.tracker.usage
        lines = [
            "=" * 40,
            "💰 成本报告",
            "=" * 40,
            f"Token消耗:",
        ]
        for agent, t in u.tokens.items():
            lines.append(f"  {agent}: {t.prompt_tokens}+{t.completion_tokens} tokens ({t.model}) = ¥{t.cost:.4f}")
        lines.extend([
            f"图片生成: {u.images.ai_generated}张 = ¥{u.images.cost:.4f}",
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
| **模型分级路由** | 高创意任务用GPT-4o，结构化任务用GPT-4o-mini，机械任务不调LLM | ~60% |
| **Prompt模板化** | 预定义分镜模板(科普/剧情/带货)，LLM只填充差异部分 | ~30% |
| **结构化输出** | 强制JSON Schema输出，避免冗余文本 | ~15% |
| **上下文裁剪** | Agent间只传必要字段，不传完整对话历史 | ~20% |
| **缓存层** | 相似选题命中缓存，复用已有脚本框架 | 视场景 |

### 8.2 模型分级策略

```
┌──────────────────────────────────────────────────┐
│                  模型路由表                        │
├────────────────┬─────────────────────────────────┤
│ 高创意任务      │ GPT-4o / Claude / Qwen-Max     │
│ (编剧、画面描述) │ 成本: $$$                       │
├────────────────┼─────────────────────────────────┤
│ 结构化任务      │ GPT-4o-mini / Qwen-Turbo       │
│ (审核、导演决策) │ 成本: $                         │
├────────────────┼─────────────────────────────────┤
│ 机械任务        │ 规则引擎 / 正则 / 模板           │
│ (剪辑、合成)    │ 成本: 免费                      │
└────────────────┴─────────────────────────────────┘
```

### 8.3 生成花费控制

| 策略 | 做法 |
|------|------|
| **图片分级生成** | 关键帧（priority=high）用DALL-E 3 hd，过渡帧用standard质量 |
| **素材复用池** | 生成过的图片入库，后续视频优先检索复用（完整版） |
| **分辨率按需** | 脚本阶段低分辨率预览，确认后再升高清（完整版） |
| **批量生成** | 同一视频的多张图片合并为batch API调用（完整版） |

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
| Token超限 | total_tokens > max_tokens | 降级到gpt-4o-mini / 缩减shot_count |
| 图片超限 | ai_generated > max_images | 降低quality为standard / 复用已有图片 |
| 重试超限 | review_round > max_retry_rounds | 停止审核循环，输出当前最佳版本 |
| 总成本超限 | total_cost > cost_limit | 立即停止，输出中间结果和成本报告 |

### 8.5 成本预估（单条视频）

| 环节 | 优化前 | 优化后 |
|------|--------|--------|
| 编剧Agent (GPT-4o) | ~¥0.80 | ~¥0.50 (模板化) |
| 导演Agent (GPT-4o-mini) | ~¥0.30 | ~¥0.05 |
| 审核Agent (GPT-4o-mini) | ~¥0.30 | ~¥0.05 |
| AI生图 (8张) | ~¥1.60 | ~¥0.60 (4张hd+4张standard) |
| TTS (Edge-TTS) | 免费 | 免费 |
| **合计** | **~¥3.00** | **~¥1.20** |

---

## 9. 错误处理策略

### 9.1 错误分类

| 类别 | 示例 | 处理方式 |
|------|------|----------|
| **可重试错误** | API超时、网络错误、LLM返回非法JSON | 自动重试，最多3次，指数退避 |
| **可恢复错误** | 审核不通过、单张图片生成失败 | 继续流程（跳过或打回） |
| **不可恢复错误** | 预算超限、API Key无效、FFmpeg未安装 | 立即停止，输出中间结果 |
| **用户取消** | 人工审核时选择取消 | 清理临时文件，退出 |

### 9.2 LLM输出错误处理

```
调用LLM
  │
  ├─ 返回有效JSON → 解析成功 → 继续
  │
  ├─ 返回非法JSON → 重试(最多2次)
  │   ├─ 第2次成功 → 继续
  │   └─ 第2次失败 → 第3次追加few-shot示例
  │       ├─ 成功 → 继续
  │       └─ 失败 → 抛出LLMOutputError → 流水线停止
  │
  ├─ API超时 → 重试(最多3次，指数退避: 2s, 4s, 8s)
  │   ├─ 重试成功 → 继续
  │   └─ 重试失败 → 抛出LLMServiceError → 流水线停止
  │
  └─ 429限流 → 读取Retry-After头 → 等待后重试
```

### 9.3 图片生成错误处理

```
生成图片
  │
  ├─ 成功 → 继续下一张
  │
  ├─ API错误 → 重试1次
  │   ├─ 成功 → 继续
  │   └─ 失败 → 使用fallback:
  │       ├─ 降低quality到standard → 重试
  │       └─ 仍失败 → 使用纯色占位图 + 文字标注 → 记录warning
  │
  └─ 预算超限 → 剩余图片使用占位图
```

### 9.4 视频合成错误处理

```
FFmpeg合成
  │
  ├─ 成功 → 继续
  │
  ├─ FFmpeg未安装 → 抛出不可恢复错误，提示安装
  │
  ├─ 单个片段失败 → 跳过该镜头，用黑屏+字幕替代 → 记录warning
  │
  └─ 拼接失败 → 尝试降低编码参数重试 → 仍失败则停止
```

### 9.5 全局错误处理（在graph.py中）

```python
def run_pipeline(user_input: str, content_type: str, tone: str, duration: int):
    graph = build_graph()
    initial_state = {
        "video_id": str(uuid.uuid4()),
        "user_input": user_input,
        "content_type": content_type,
        "tone": tone,
        "duration": duration,
        "script": None,
        "production_plan": None,
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

    try:
        result = graph.invoke(initial_state)
        print_cost_report(result["cost_tracker"])
        return result
    except BudgetExceededError as e:
        logger.error("budget_exceeded", error=str(e))
        print("预算超限，流水线停止。")
        print_cost_report(initial_state["cost_tracker"])
    except AgentError as e:
        logger.error("agent_error", agent=e.agent_name, error=str(e))
        if not e.recoverable:
            print(f"不可恢复错误: {e}")
    except Exception as e:
        logger.exception("unexpected_error")
        print(f"未知错误: {e}")
```

---

## 10. MVP方案

### 10.1 MVP目标

**输入一个主题 → 输出一条可发布的短视频**，验证核心链路可行性。

### 10.2 MVP Agent精简

| Agent | MVP状态 | 说明 |
|-------|---------|------|
| 选题Agent | 不做 | 用户直接输入主题 |
| 编剧Agent | 保留 | 核心能力，输出分镜脚本 |
| 导演Agent | 保留 | 简化为规则引擎+轻量LLM |
| 素材Agent | 合并 | 合并进剪辑Agent |
| 配音Agent | 合并 | 合并进剪辑Agent |
| 剪辑Agent | 保留 | 集成素材获取+TTS+FFmpeg合成 |
| 审核Agent | 保留 | 简化审核维度 |
| 发布Agent | 不做 | 输出本地文件，手动发布 |

**MVP = 4个Agent：编剧 + 导演 + 剪辑 + 审核**

### 10.3 MVP技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Agent框架 | LangGraph | 状态机天然支持审核打回循环 |
| LLM | OpenAI GPT-4o + GPT-4o-mini | 分级路由，控制成本 |
| AI生图 | DALL-E 3 | API成熟，质量稳定 |
| TTS | Edge-TTS | 免费、中文效果好、零成本 |
| 视频合成 | FFmpeg + MoviePy | 图片+音频+字幕→视频 |
| 人工审核 | 终端 input() | MVP不需要前端 |
| 配置管理 | Pydantic Settings | 类型安全的配置 |
| 日志 | structlog | 结构化日志，便于追踪 |

### 10.4 MVP验证指标

| 指标 | 目标值 |
|------|--------|
| 端到端耗时 | ≤ 3分钟（不含人工审核） |
| 视频完整性 | 画面+配音+字幕+转场全部具备 |
| 审核有效性 | 能识别并打回低质量内容 |
| 人工修改生效 | 修改脚本后正确影响成片 |
| 单条成本 | ≤ ¥2.0 |
| 视频分辨率 | 1080×1920, 30fps |

### 10.5 MVP入口程序（`src/main.py`）

```python
import sys
import asyncio
from src.graph import build_graph
from src.schemas.cost import CostTracker, Budget
from src.services.cost_tracker import CostTrackerService
import uuid
import structlog

logger = structlog.get_logger()


def main():
    print("=" * 60)
    print("🎬 AI Video Studio - MVP")
    print("=" * 60)

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
    except Exception as e:
        logger.exception("pipeline_failed")
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
| AI视频生成 | 可灵/Sora/Runway生成视频片段 | P0 |
| 素材复用池 | 向量检索+素材管理 | P1 |
| Web前端 | 可视化编辑器、时间线、审核界面 | P1 |
| 多账号管理 | 多平台多账号发布管理 | P1 |
| 数据复盘 | 发布后数据追踪、效果分析 | P2 |
| A/B测试 | 标题/封面多版本测试 | P2 |
| 批量生产 | 批量选题、批量生成、队列管理 | P2 |

### 11.2 完整版技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    Web前端 (React/Next.js)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 选题面板  │ │脚本编辑器│ │时间线编辑│ │数据看板   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │ REST API / WebSocket
┌────────────────────────┼────────────────────────────────┐
│                  API Gateway (FastAPI)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ 认证鉴权  │ │ 限流     │ │ 日志     │ │ 监控     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│              LangGraph 编排引擎                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  8个Agent + 状态机 + 预算控制 + 人工审核节点      │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│                  基础设施层                               │
│                                                          │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │PostgreSQL│ │ Redis  │ │ MinIO  │ │Milvus  │           │
│  │(元数据) │ │(队列/缓存)│ │(对象存储)│ │(向量DB)│           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │Celery  │ │Prometheus│ │Grafana │ │Sentry  │           │
│  │(任务队列)│ │(监控)   │ │(看板)  │ │(错误追踪)│          │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
└─────────────────────────────────────────────────────────┘
```

### 11.3 完整版技术选型

| 组件 | 选型 | 说明 |
|------|------|------|
| 前端 | Next.js + TailwindCSS | 可视化编辑器、时间线 |
| 后端API | FastAPI | 高性能异步API |
| Agent框架 | LangGraph | 状态机+人机协作 |
| LLM | GPT-4o + GPT-4o-mini + Qwen | 多模型路由 |
| AI视频生成 | 可灵 / Sora / Runway | 按场景选择 |
| AI生图 | DALL-E 3 + SD-XL + 通义万相 | 分级生成 |
| TTS | Edge-TTS + Fish Audio | 免费+高质量 |
| 视频处理 | FFmpeg + MoviePy | 程序化剪辑 |
| 数据库 | PostgreSQL | 元数据、用户、任务 |
| 缓存 | Redis | 缓存+消息队列 |
| 对象存储 | MinIO | 素材、视频文件 |
| 向量数据库 | Milvus | 素材语义检索 |
| 任务队列 | Celery + Redis | 异步任务处理 |
| 监控 | Prometheus + Grafana | 系统+成本监控 |
| 部署 | Docker + Docker Compose | 容器化部署 |

### 11.4 完整版数据模型

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
    "langchain-openai>=0.2.0",
    "langchain-core>=0.3.0",
    "openai>=1.50.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "edge-tts>=6.1.0",
    "moviepy>=2.0.0",
    "Pillow>=10.0",
    "httpx>=0.27.0",
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
| FFmpeg | `apt install ffmpeg` / `brew install ffmpeg` | 视频合成核心引擎 |
| Python 3.11+ | pyenv / 系统安装 | 运行环境 |

---

## 13. 配置与环境变量

### 13.1 .env.example

```env
# LLM配置
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# 可选：通义千问（完整版）
# DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx

# 可选：Fish Audio TTS（完整版）
# FISH_AUDIO_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# 预算控制
MAX_TOKENS_PER_VIDEO=8000
MAX_IMAGES_PER_VIDEO=8
MAX_RETRY_ROUNDS=2
COST_LIMIT_PER_VIDEO=5.0

# 输出目录
OUTPUT_DIR=./output

# 日志级别
LOG_LEVEL=INFO

# TTS默认配置
DEFAULT_VOICE_ID=zh-CN-YunxiNeural
DEFAULT_VOICE_SPEED=1.0

# 视频默认配置
DEFAULT_RESOLUTION=1080x1920
DEFAULT_FPS=30
DEFAULT_ASPECT_RATIO=9:16
```

### 13.2 配置类（`config/settings.py`）

```python
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    openai_api_key: str = Field(description="OpenAI API Key")
    openai_base_url: str = Field(default="https://api.openai.com/v1")

    max_tokens_per_video: int = Field(default=8000)
    max_images_per_video: int = Field(default=8)
    max_retry_rounds: int = Field(default=2)
    cost_limit_per_video: float = Field(default=5.0)

    output_dir: str = Field(default="./output")
    log_level: str = Field(default="INFO")

    default_voice_id: str = Field(default="zh-CN-YunxiNeural")
    default_voice_speed: float = Field(default=1.0)

    default_resolution: str = Field(default="1080x1920")
    default_fps: int = Field(default=30)
    default_aspect_ratio: str = Field(default="9:16")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


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
│       │   └── default.txt
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
│   │   ├── screenwriter.py       # 编剧Agent
│   │   ├── director.py           # 导演Agent
│   │   ├── editor.py             # 剪辑Agent
│   │   └── reviewer.py           # 审核Agent
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py                # LLM调用封装（含模型路由）
│   │   ├── image_gen.py          # AI生图服务
│   │   ├── tts.py                # TTS语音合成
│   │   ├── video_compose.py      # FFmpeg视频合成
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
│       ├── media.py              # 媒体工具（获取视频时长/分辨率等）
│       └── sensitive_words.py    # 敏感词库
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
    ├── test_cost_tracker.py      # 成本追踪测试
    └── test_graph.py             # 状态机集成测试
```

### 14.2 推荐实现顺序

按以下顺序实现，每步完成后可以独立验证：

```
Step 1: 项目骨架（30分钟）
├── 创建pyproject.toml
├── 创建.env.example和config/settings.py
├── 创建所有__init__.py
├── 创建src/state.py
└── 验证: pip install -e . 能成功

Step 2: Schema定义（1小时）
├── src/schemas/cost.py
├── src/schemas/script.py
├── src/schemas/plan.py
├── src/schemas/review.py
└── 验证: 写test_schemas.py，确保Schema能正确序列化/反序列化

Step 3: Service层（2-3小时）
├── src/services/cost_tracker.py
├── src/services/llm.py
├── src/services/image_gen.py
├── src/services/tts.py
├── src/services/video_compose.py
└── 验证: 每个service写单元测试，mock外部API

Step 4: Agent基类 + 编剧Agent（2小时）
├── src/agents/base.py
├── config/templates/screenwriter/*.txt
├── src/agents/screenwriter.py
└── 验证: 输入主题，能输出合法的Script JSON

Step 5: 导演Agent（1小时）
├── config/templates/director/default.txt
├── src/agents/director.py
└── 验证: 输入Script，能输出合法的ProductionPlan

Step 6: 剪辑Agent（3-4小时）
├── src/agents/editor.py
├── src/utils/media.py
└── 验证: 输入Script+Plan，能输出可播放的.mp4文件

Step 7: 审核Agent（1-2小时）
├── config/templates/reviewer/default.txt
├── src/agents/reviewer.py
├── src/utils/sensitive_words.py
└── 验证: 输入Script+视频，能输出ReviewReport

Step 8: LangGraph状态机 + 入口（2小时）
├── src/graph.py
├── src/main.py
└── 验证: 端到端运行，输入主题→输出视频

Step 9: 测试 + 优化（1-2小时）
├── tests/test_graph.py（集成测试）
├── 错误处理完善
└── 验证: 完整流程跑通，成本在预算内
```

---

## 15. 测试策略

### 15.1 测试层次

| 层次 | 范围 | Mock策略 | 工具 |
|------|------|----------|------|
| Schema测试 | Pydantic模型校验 | 无需Mock | pytest |
| Service单元测试 | 各Service方法 | Mock外部API | pytest + pytest-mock |
| Agent单元测试 | 各Agent逻辑 | Mock Service层 | pytest + pytest-mock |
| 集成测试 | 完整流水线 | Mock LLM返回固定JSON | pytest |
| 端到端测试 | 真实API调用 | 不Mock | 手动运行 |

### 15.2 关键测试用例

**Schema测试**：
- Script序列化/反序列化正确性
- 边界值：最少镜头(2个)、最多镜头(30个)
- 非法值校验：duration<2、subtitle每行>15字
- 默认值填充

**编剧Agent测试**：
- Mock LLM返回合法Script JSON → 解析成功
- Mock LLM返回非法JSON → 重试后成功
- Mock LLM连续3次返回非法JSON → 抛出LLMOutputError
- 不同content_type使用不同模板

**剪辑Agent测试**：
- Mock图片生成和TTS → FFmpeg合成成功
- 单张图片生成失败 → 使用占位图继续
- FFmpeg未安装 → 抛出不可恢复错误

**审核Agent测试**：
- 合规检查：包含敏感词 → verdict=revision_needed
- 评分测试：高质量脚本 → overall_score≥60 → approved
- 打回测试：低质量脚本 → revision_needed + 修改建议
- 最大轮次：round>max_rounds → 强制输出

**集成测试**：
- Mock所有LLM返回预设JSON → 完整流水线跑通
- 审核打回循环：第1轮不通过 → 第2轮通过
- 预算超限：设置极低预算 → BudgetExceededError

### 15.3 conftest.py fixtures

```python
import pytest
from unittest.mock import MagicMock
from src.schemas.script import Script, Shot, ShotType, ImageStyle, TransitionType, CameraEffect, BGMMood, ShotPriority, ScriptMetadata, GlobalSettings


@pytest.fixture
def sample_script() -> Script:
    """提供一个合法的示例Script用于测试"""
    return Script(
        script_id="test-001",
        title="测试视频",
        style="science",
        tone="幽默通俗",
        total_duration=30,
        metadata=ScriptMetadata(topic="测试主题"),
        shots=[
            Shot(
                id=1, type=ShotType.OPENING, duration=5.0,
                image_prompt="一个明亮的实验室，桌上放着各种科学仪器",
                narration="你知道吗？今天我们来聊一个有趣的话题",
                subtitle="你知道吗？\n今天我们来聊\n一个有趣的话题",
                transition_in=TransitionType.FADE_IN,
                transition_out=TransitionType.CUT,
                camera_effect=CameraEffect.KEN_BURNS,
                bgm_mood=BGMMood.UPBEAT,
                priority=ShotPriority.HIGH,
            ),
            Shot(
                id=2, type=ShotType.CONTENT, duration=10.0,
                image_prompt="宇宙星空，银河系的全景图，壮观的场景",
                narration="让我们从宇宙的尺度开始说起",
                subtitle="让我们从\n宇宙的尺度\n开始说起",
                transition_in=TransitionType.CUT,
                transition_out=TransitionType.FADE_OUT,
                camera_effect=CameraEffect.ZOOM_IN_SLOW,
                bgm_mood=BGMMood.MYSTERIOUS,
                priority=ShotPriority.NORMAL,
            ),
        ],
    )


@pytest.fixture
def mock_llm():
    """Mock LLM服务"""
    return MagicMock()


@pytest.fixture
def mock_image_gen():
    """Mock图片生成服务"""
    return MagicMock()
```

---

## 16. 迭代路线图

```
Phase 1 — MVP (2-3周)
├── 编剧Agent + 导演Agent + 剪辑Agent + 审核Agent
├── 图文解说视频生成（AI生图+TTS+FFmpeg）
├── 终端人工审核
├── 成本追踪
└── 输出: 本地1080×1920视频文件

Phase 2 — 视频增强 (2周)
├── 加入AI视频生成（可灵/Sora）
├── 素材复用池（向量检索）
├── 更多转场效果和字幕样式
├── BGM智能匹配
└── 输出: 更高质量的视频

Phase 3 — 选题+发布 (2周)
├── 选题Agent（热点追踪、竞品分析）
├── 发布Agent（抖音/TikTok API）
├── 定时发布
├── 封面自动生成
└── 输出: 从选题到发布的完整闭环

Phase 4 — Web平台 (3-4周)
├── Web前端（可视化编辑器、时间线）
├── 多账号管理
├── 项目管理
├── 批量生产
└── 输出: 可多人协作的Web平台

Phase 5 — 数据驱动 (2周)
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
| LLM生成质量不稳定 | 脚本质量差，影响成片 | 模板化约束+审核Agent把关+人工兜底 |
| AI生图与内容不匹配 | 画面和旁白脱节 | 精细化image_prompt+导演Agent审核 |
| API成本超预期 | 烧钱过快 | 预算控制器+模型分级+素材复用 |
| 平台API限制 | 无法自动发布 | 先支持本地导出，手动发布 |
| 视频合成耗时长 | 用户体验差 | 异步处理+进度通知+预览模式 |
| 内容合规风险 | 账号封禁 | 审核Agent多维度检查+敏感词库 |
| 单一LLM供应商风险 | 服务不可用 | 抽象LLM接口，支持多供应商切换 |
| FFmpeg兼容性问题 | 不同系统命令差异 | 封装为Service层，统一接口 |
| LLM返回非法JSON | 流水线中断 | 重试机制+错误提示追加+few-shot兜底 |
