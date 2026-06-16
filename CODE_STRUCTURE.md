# AI Video Studio — 代码结构说明书

> 多Agent协作的短视频自动化生产系统
> 技术栈：DeepSeek + 可灵(Kling) + MoviePy + LangGraph

---

## 1. 项目总览

```
ai-video-studio/
├── pyproject.toml                 # 项目配置、依赖管理
├── .env.example                   # 环境变量模板
├── .gitignore
│
├── config/                        # 配置层
│   ├── settings.py                # 全局配置（Pydantic Settings）
│   └── templates/                 # Prompt模板（纯文本）
│       ├── screenwriter/          # 编剧Agent模板（4类）
│       │   ├── science.txt        # 知识科普
│       │   ├── story.txt          # 故事/剧情
│       │   ├── trending.txt       # 热点追踪
│       │   └── product.txt        # 产品带货
│       ├── director/
│       │   └── default.txt        # 导演Agent模板
│       └── reviewer/
│           └── default.txt        # 审核Agent模板
│
├── src/                           # 源码层
│   ├── main.py                    # CLI入口
│   ├── graph.py                   # LangGraph状态机（流程编排）
│   ├── state.py                   # 全局状态类型定义
│   │
│   ├── agents/                    # Agent层（4个角色）
│   │   ├── base.py                # Agent基类 + 异常
│   │   ├── screenwriter.py        # 编剧Agent
│   │   ├── director.py            # 导演Agent
│   │   ├── editor.py              # 剪辑Agent
│   │   └── reviewer.py            # 审核Agent
│   │
│   ├── services/                  # 服务层（基础设施）
│   │   ├── llm.py                 # DeepSeek LLM调用
│   │   ├── kling.py               # 可灵视频生成API
│   │   ├── image_gen.py           # 占位图生成
│   │   ├── tts.py                 # 静音音频占位
│   │   ├── video_compose.py       # MoviePy视频合成
│   │   └── cost_tracker.py        # 成本追踪
│   │
│   ├── schemas/                   # 数据模型层（Pydantic）
│   │   ├── script.py              # 分镜脚本 Schema
│   │   ├── plan.py                # 制作任务书 Schema
│   │   ├── review.py              # 审核报告 Schema
│   │   └── cost.py                # 成本追踪 Schema
│   │
│   └── utils/                     # 工具层
│       ├── media.py               # 视频信息获取
│       └── sensitive_words.py     # 敏感词检测
│
├── output/                        # 运行时输出（gitignore）
│
└── tests/                         # 测试层（60个用例）
    ├── conftest.py                # 公共fixtures
    ├── test_schemas.py            # Schema校验
    ├── test_screenwriter.py       # 编剧Agent
    ├── test_director.py           # 导演Agent
    ├── test_editor.py             # 剪辑/合成
    ├── test_reviewer.py           # 审核/敏感词
    ├── test_kling.py              # 可灵API
    ├── test_cost_tracker.py       # 成本追踪
    └── test_graph.py              # 状态机路由
```

---

## 2. 系统架构

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

---

## 3. 四个Agent角色详解

### 3.1 编剧Agent — `src/agents/screenwriter.py`

| 属性 | 值 |
|------|-----|
| **类名** | `ScreenwriterAgent` |
| **位置** | `src/agents/screenwriter.py:36` |
| **继承** | `BaseAgent` |
| **调用LLM** | 是，`deepseek-chat`（creative档，temperature=0.8） |
| **输入** | `user_input`, `content_type`, `tone`, `duration` |
| **输出** | `Script` 对象（分镜脚本JSON） |
| **Prompt模板** | `config/templates/screenwriter/{type}.txt` |

**核心逻辑**：
1. 根据 `content_type` 选择对应Prompt模板（science/story/trending/product）
2. 根据 `duration` 和 `content_type` 计算镜头数量（`_calculate_shot_count`）
3. 填充模板变量（主题、风格、时长、受众、镜头数、JSON Schema）
4. 调用DeepSeek生成结构化JSON，用Pydantic校验
5. 如果有人工反馈（打回场景），追加到prompt中

**镜头数计算规则**（`_calculate_shot_count`）：

| 类型 | 时长范围 | 镜头数 |
|------|---------|--------|
| science | 30-60s | 4-6 |
| science | 60-120s | 6-10 |
| science | 120-180s | 10-12 |
| story | 60-120s | 6-10 |
| story | 120-300s | 10-20 |
| trending | 30-60s | 3-5 |
| trending | 60-90s | 5-8 |
| product | 30-60s | 4-8 |

公式：`shot_count = max(min_shots, min(max_shots, duration // 10))`

---

### 3.2 导演Agent — `src/agents/director.py`

| 属性 | 值 |
|------|-----|
| **类名** | `DirectorAgent` |
| **位置** | `src/agents/director.py:45` |
| **继承** | `BaseAgent` |
| **调用LLM** | 否（纯规则引擎） |
| **输入** | `Script` 对象 |
| **输出** | `ProductionPlan` 对象（制作任务书） |

**核心逻辑**：
不调LLM，完全基于规则决策：

1. **素材质量决策**（`_decide_quality_for_shot`）：
   - `priority=high` → hd质量
   - `priority=normal/low` → standard质量

2. **BGM风格决策**（`_decide_bgm_style`）：
   - 含"幽默/轻松/通俗" → 轻快电子
   - 含"严肃/专业" → 简约钢琴
   - 含"悬疑/紧张" → 暗黑氛围
   - 默认 → 轻快电子

3. **字幕动画决策**（`_decide_subtitle_animation`）：
   - science → typewriter（打字机效果）
   - story → fade（淡入淡出）
   - trending/product → slide_up（上滑）

4. **转场决策**（`_decide_transition`）：
   - trending/product → cut（硬切，快节奏）
   - 其他 → crossfade（交叉淡入淡出）

---

### 3.3 剪辑Agent — `src/agents/editor.py`

| 属性 | 值 |
|------|-----|
| **类名** | `EditorAgent` |
| **位置** | `src/agents/editor.py:15` |
| **继承** | `BaseAgent` |
| **调用LLM** | 否 |
| **输入** | `Script` + `ProductionPlan` |
| **输出** | 视频文件路径 + 素材映射 |
| **调用服务** | `KlingService` + `ImageGenService` + `TTSService` + `VideoComposeService` |

**核心逻辑**：

```
1. 遍历每个shot → 调可灵API生成视频片段
   ├── 成功 → 保存 clip_{id}.mp4
   └── 失败 → 降级为占位图 shot_{id}.png

2. 遍历每个shot → 生成音频（当前为静音占位）
   └── 保存 narration_{id}.wav

3. 调MoviePy合成最终视频
   ├── 视频片段（或占位图）作为画面
   ├── 音频叠加
   └── 字幕烧录

4. 保存 script.json + plan.json 到输出目录
```

**文件输出结构**：
```
output/{video_id}/
├── assets/
│   ├── clip_01.mp4          # 可灵生成的视频片段
│   ├── clip_02.mp4
│   ├── shot_03.png          # 可灵失败时的占位图
│   ├── narration_01.wav     # 音频
│   └── subtitles.srt        # 字幕文件
├── script.json              # 分镜脚本快照
├── plan.json                # 制作任务书快照
└── draft.mp4                # 成片初稿
```

---

### 3.4 审核Agent — `src/agents/reviewer.py`

| 属性 | 值 |
|------|-----|
| **类名** | `ReviewerAgent` |
| **位置** | `src/agents/reviewer.py:21` |
| **继承** | `BaseAgent` |
| **调用LLM** | 是，`deepseek-chat`（efficient档，temperature=0.3） |
| **输入** | `Script` + `review_round` |
| **输出** | `ReviewReport` 对象 |
| **通过分数** | 60分 |
| **Prompt模板** | `config/templates/reviewer/default.txt` |

**核心逻辑**：

审核分3步：

1. **合规检查**（`_check_compliance`，不调LLM）：
   - 敏感词库匹配（`src/utils/sensitive_words.py`）
   - 命中即一票否决

2. **技术检查**（`_check_technical`，不调LLM）：
   - 镜头时长是否在2-30秒
   - 字幕每行是否≤15字
   - 总时长是否≥15秒

3. **内容审核**（调LLM）：
   - 将完整脚本发给DeepSeek评估
   - 评估维度：技术质量(30%) + 内容质量(40%) + 平台适配(30%)

**评分公式**：
```
overall_score = technical_quality × 0.3 + content_quality × 0.4 + platform_fit × 0.3

判定规则：
- 合规不通过 → 直接打回（一票否决）
- overall_score ≥ 60 且合规通过 → approved
- overall_score < 60 → revision_needed
- 最多打回2轮，超过则强制输出当前最佳版本
```

---

## 4. 状态机流程 — `src/graph.py`

### 4.1 流程图

```
START
  │
  ▼
screenwriting（编剧Agent）
  │
  ▼
human_script_review（人工审核脚本）──→ [a]确认 ──→ directing
  │                                    [r]修改 ──→ 回到screenwriting
  │                                    [q]取消 ──→ END
  ▼
directing（导演Agent）
  │
  ▼
editing（剪辑Agent）←──────────────────────────┐
  │                                             │
  ▼                                             │
reviewing（审核Agent）                           │
  │                                             │
  ├── approved ──→ human_video_review           │
  ├── revision_needed ──────────────────────────┘
  └── max_rounds ──→ human_video_review
                        │
                        ├── [a]确认 ──→ END
                        ├── [r]修改 ──→ editing
                        └── [q]取消 ──→ END
```

### 4.2 节点定义

| 节点名 | 类型 | 位置 | 说明 |
|--------|------|------|------|
| `screenwriting` | Agent | `graph.py:18` | 编剧Agent执行 |
| `human_script_review` | 人工 | `graph.py:89` | 终端交互，展示脚本，等待确认/修改/取消 |
| `directing` | Agent | `graph.py:20` | 导演Agent执行（纯规则） |
| `editing` | Agent | `graph.py:21` | 剪辑Agent执行（可灵+合成） |
| `reviewing` | Agent | `graph.py:22` | 审核Agent执行（LLM+规则） |
| `human_video_review` | 人工 | `graph.py:121` | 终端交互，展示成片，等待确认/修改/取消 |

### 4.3 路由函数

| 函数 | 位置 | 触发条件 | 路由目标 |
|------|------|---------|---------|
| `route_after_script_review` | `graph.py:60` | 人工审核脚本后 | approved→directing / revision→screenwriting / cancelled→END |
| `route_after_review` | `graph.py:70` | 审核Agent完成后 | approved→human_video_review / revision_needed→editing / max_rounds→human_video_review |
| `route_after_video_review` | `graph.py:79` | 人工审核成片后 | approved→END / revision→editing / cancelled→END |

---

## 5. 全局状态 — `src/state.py`

所有Agent通过 `VideoState` 共享数据，每个Agent只读写自己需要的字段：

```python
class VideoState(TypedDict):
    # ── 用户输入（初始化时写入）──
    video_id: str              # 视频唯一ID
    user_input: str            # 原始主题
    content_type: str          # 内容类型: science/story/trending/product
    tone: str                  # 语气风格
    duration: int              # 目标时长（秒）

    # ── Agent产出 ──
    script: Script             # 编剧Agent → 分镜脚本
    production_plan: ProductionPlan  # 导演Agent → 制作任务书
    generated_images: dict     # 剪辑Agent → {shot_id: 图片路径}
    generated_audios: dict     # 剪辑Agent → {shot_id: 音频路径}
    video_draft_path: str      # 剪辑Agent → 成片路径
    final_video_path: str      # 审核通过后 → 最终视频路径
    review_report: ReviewReport # 审核Agent → 审核报告
    review_round: int          # 审核Agent → 当前轮次

    # ── 全局控制 ──
    cost_tracker: CostTracker  # 成本追踪器
    human_feedback: str        # 人工反馈内容
    human_action: str          # 人工操作类型: approve/revise/cancel
    status: str                # 流水线状态
    error: str                 # 错误信息
```

**status 状态流转**：
```
pending → screenwriting → awaiting_script_review → directing → editing → reviewing → awaiting_video_review → completed
```

---

## 6. 数据模型（Schemas）

### 6.1 Script（分镜脚本）— `src/schemas/script.py`

核心结构，所有Agent围绕此交互：

```
Script
├── script_id, title, style, tone, total_duration
├── metadata: {topic, target_audience, keywords, platform}
├── global_settings: {voice_id, voice_speed, subtitle_font, ...}
└── shots: [Shot, Shot, ...]
    └── Shot
        ├── id, type(opening/content/transition/closing)
        ├── duration(2-30秒), image_prompt(10-500字)
        ├── narration(旁白), subtitle(字幕)
        ├── transition_in/out, camera_effect, bgm_mood
        └── priority(high/normal/low)
```

### 6.2 ProductionPlan（制作任务书）— `src/schemas/plan.py`

```
ProductionPlan
├── plan_id, script_id
├── shot_sources: [{shot_id, source, generate_prompt, image_model}, ...]
├── generation_params: {image_model, image_size, image_quality}
├── audio_plan: {tts_engine, voice_id, voice_speed, bgm_volume}
├── edit_plan: {default_transition, subtitle_animation}
└── budget: {max_images_to_generate, max_cost}
```

### 6.3 ReviewReport（审核报告）— `src/schemas/review.py`

```
ReviewReport
├── review_id, script_id, round, max_rounds
├── verdict: approved / revision_needed
├── overall_score: 0-100
├── dimensions: {
│     compliance: {score, passed, issues},        ← 一票否决
│     technical_quality: {score, passed, issues}, ← 权重30%
│     content_quality: {score, passed, issues},   ← 权重40%
│     platform_fit: {score, passed, issues}       ← 权重30%
│   }
└── revision_instructions: 打回时的修改指引
```

### 6.4 CostTracker（成本追踪）— `src/schemas/cost.py`

```
CostTracker
├── video_id
├── budget: {max_tokens, max_images, max_retry_rounds, cost_limit}
├── usage: {
│     tokens: {agent_name: {prompt_tokens, completion_tokens, cost}},
│     images: {ai_generated, cost},
│     tts_cost, total_cost
│   }
└── status: within_budget / warning / exceeded
```

---

## 7. Service层说明

### 7.1 LLM服务 — `src/services/llm.py`

| 属性 | 值 |
|------|-----|
| **后端** | DeepSeek API (api.deepseek.com) |
| **模型** | `deepseek-chat` |
| **认证** | API Key |
| **输出格式** | 强制JSON（`response_format: json_object`） |
| **重试** | JSON解析失败最多重试2次，每次追加错误提示 |

**模型分级**：

| 档位 | 模型 | temperature | 用途 |
|------|------|-------------|------|
| creative | deepseek-chat | 0.8 | 编剧Agent（高创意） |
| efficient | deepseek-chat | 0.3 | 审核Agent（结构化评估） |

**价格**（DeepSeek官方定价，单位：元/百万token）：
- 输入：¥1.0 / 百万token
- 输出：¥2.0 / 百万token

### 7.2 可灵视频服务 — `src/services/kling.py`

| 属性 | 值 |
|------|-----|
| **后端** | 可灵API (api.klingai.com) |
| **认证** | JWT（access_key + secret_key → HS256签名） |
| **模式** | 异步：提交任务 → 轮询结果 → 下载视频 |
| **轮询间隔** | 5秒 |
| **最大等待** | 300秒 |
| **默认模型** | `kling-v2-5-turbo` |

**支持的视频参数**：
- 时长：5秒 或 10秒
- 画面比例：9:16（竖屏）
- 分辨率：1080p

**价格参考**：
| 模型 | 5秒 | 10秒 |
|------|-----|------|
| kling-v2-5-turbo | $0.35 (~¥2.5) | - |
| kling-v2-6-std | $0.28 (~¥2.0) | - |
| kling-v2-6-pro | $0.49 (~¥3.5) | $0.98 (~¥7.1) |

### 7.3 占位图服务 — `src/services/image_gen.py`

可灵API调用失败时的降级方案：用Pillow生成灰色占位图（1080×1920），上面显示prompt文字。

### 7.4 静音音频服务 — `src/services/tts.py`

生成对应时长的静音WAV文件（44100Hz, 16bit, 单声道），作为TTS未集成时的占位。

### 7.5 视频合成服务 — `src/services/video_compose.py`

| 属性 | 值 |
|------|-----|
| **后端** | MoviePy |
| **分辨率** | 1080×1920 (9:16竖屏) |
| **帧率** | 30fps |
| **编码** | libx264 + AAC |

**合成流程**：
1. 遍历每个shot：
   - 优先使用可灵生成的视频片段（`VideoFileClip`）
   - 降级使用占位图（`ImageClip`）
   - 叠加音频（`AudioFileClip`）
   - 叠加字幕（`TextClip` + `CompositeVideoClip`）
2. 拼接所有片段（`concatenate_videoclips`）
3. 输出最终MP4

### 7.6 成本追踪服务 — `src/services/cost_tracker.py`

追踪每个Agent的token消耗和图片/视频生成费用，超预算时触发降级或停止。

**预算控制**：
- Token总量 > 8000 → 超限
- 图片/视频数 > 8 → 超限
- 总花费 > ¥5.0 → 超限
- 花费达到80% → 预警

---

## 8. 关键Prompt模板

### 8.1 编剧Prompt — 科普类 (`config/templates/screenwriter/science.txt`)

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
3. 最后一个镜头要有总结或引导互动
4. 每个镜头时长5-15秒
5. image_prompt必须具体、可视化，描述一个明确的画面场景
6. narration要口语化，像在跟朋友聊天
7. subtitle用\n换行，每行不超过15个字
8. 合理分配transition和camera_effect

请严格按照以下JSON格式输出：
{json_schema}
```

**变量说明**：
- `{topic}` — 用户输入的主题
- `{tone}` — 语气风格（如"幽默通俗"）
- `{duration}` — 目标时长（秒）
- `{target_audience}` — 目标受众（固定为"抖音用户"）
- `{shot_count}` — 计算出的镜头数
- `{json_schema}` — Script模型的JSON Schema（运行时注入）

### 8.2 编剧Prompt — 其他类型

| 类型 | 模板文件 | 核心差异 |
|------|---------|---------|
| 故事类 | `story.txt` | 要求有悬念/冲突/转折/反转 |
| 热点类 | `trending.txt` | 要求直接切入热点、独特视角 |
| 带货类 | `product.txt` | 要求痛点切入→产品亮点→引导购买 |

### 8.3 导演Prompt (`config/templates/director/default.txt`)

> 注意：当前导演Agent是纯规则引擎，不调LLM，此模板保留用于未来扩展。

```
你是一个短视频导演，负责将编剧的分镜脚本转化为可执行的制作方案。

以下是分镜脚本：
{script_json}

决策规则：
- priority为high → 高质量AI生图（hd质量）
- priority为normal → 标准AI生图（standard质量）
- priority为low → 标准AI生图（standard质量）

同时决策：BGM风格、转场节奏、字幕动画
```

### 8.4 审核Prompt (`config/templates/reviewer/default.txt`)

```
你是一个短视频内容审核专家。请对以下视频脚本进行多维度审核。

视频标题：{title}
视频类型：{style}
总时长：{total_duration}秒
镜头数：{shot_count}个

分镜脚本：
{script_json}

评估维度：
1. 技术质量（权重30%）：时长合理性、字幕规范、转场合理性
2. 内容质量（权重40%）：叙事连贯性、画面-旁白匹配、开头吸引力
3. 平台适配（权重30%）：标题吸引力、平台适配度、互动引导
4. 合规检查（一票否决）：敏感词、版权风险、虚假信息
```

---

## 9. 配置说明 — `config/settings.py`

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| `deepseek_api_key` | `DEEPSEEK_API_KEY` | (必填) | DeepSeek API Key |
| `deepseek_base_url` | `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API地址 |
| `kling_access_key` | `KLING_ACCESS_KEY` | (必填) | 可灵 Access Key |
| `kling_secret_key` | `KLING_SECRET_KEY` | (必填) | 可灵 Secret Key |
| `kling_base_url` | `KLING_BASE_URL` | `https://api.klingai.com` | 可灵 API地址 |
| `kling_model` | `KLING_MODEL` | `kling-v2-5-turbo` | 可灵模型 |
| `max_tokens_per_video` | `MAX_TOKENS_PER_VIDEO` | 8000 | 单视频最大token数 |
| `max_images_per_video` | `MAX_IMAGES_PER_VIDEO` | 8 | 单视频最大生成数 |
| `cost_limit_per_video` | `COST_LIMIT_PER_VIDEO` | 5.0 | 单视频预算上限(元) |
| `output_dir` | `OUTPUT_DIR` | `./output` | 输出目录 |

---

## 10. 运行与测试

### 启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY 和 KLING_ACCESS_KEY/SECRET_KEY

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 运行
python src/main.py
```

### 测试

```bash
# 运行全部60个测试
pytest tests/ -v

# 运行lint检查
ruff check src/ tests/ config/
```

### 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---------|--------|---------|
| `test_schemas.py` | 12 | Schema序列化/反序列化/边界值校验 |
| `test_screenwriter.py` | 9 | 镜头数计算 + Agent执行（Mock LLM） |
| `test_director.py` | 11 | 质量/BGM/字幕/转场决策规则 |
| `test_editor.py` | 2 | SRT时间格式化 + 字幕生成 |
| `test_reviewer.py` | 4 | 敏感词检测 |
| `test_kling.py` | 3 | JWT生成 + Header格式 + 价格查询 |
| `test_cost_tracker.py` | 8 | 成本记录 + 超限检测 + 报告生成 |
| `test_graph.py` | 9 | 状态机路由逻辑（3个路由函数） |
