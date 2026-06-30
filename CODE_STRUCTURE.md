# AI Video Studio — 代码结构说明书

> 多Agent协作的短视频自动化生产系统，支持连续剧/系列视频创作
> 技术栈：DeepSeek + 可灵(Kling CLI) + MoviePy + LangGraph

---

## 1. 项目总览

```
ai-video-studio/
├── pyproject.toml                 # 项目配置、依赖管理
├── .env.example                   # 环境变量模板
├── .gitignore
├── README.md                      # 项目简介
├── CODE_STRUCTURE.md              # 本文档
├── test_run.py                    # 非交互测试脚本
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
│       │   └── default.txt        # 导演Agent模板（当前未使用）
│       └── reviewer/
│           └── default.txt        # 审核Agent模板
│
├── src/                           # 源码层
│   ├── main.py                    # CLI入口（项目管理+流水线启动）
│   ├── graph.py                   # LangGraph状态机（流程编排+人工审核）
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
│   │   ├── llm.py                 # DeepSeek LLM调用（chat/reasoner分级）
│   │   ├── kling.py               # 可灵CLI调用（文生视频/图生视频/文生图）
│   │   ├── image_gen.py           # 占位图生成（Pillow）
│   │   ├── tts.py                 # TTS语音合成（Edge-TTS/静音占位）
│   │   ├── video_compose.py       # MoviePy视频合成（拼接+字幕）
│   │   ├── cost_tracker.py        # 成本追踪
│   │   └── project_manager.py     # 项目管理（CRUD+集数+角色+伏笔）
│   │
│   ├── schemas/                   # 数据模型层（Pydantic）
│   │   ├── script.py              # Script/Shot（分镜脚本）
│   │   ├── plan.py                # ProductionPlan（制作任务书）
│   │   ├── review.py              # ReviewReport（审核报告）
│   │   ├── cost.py                # CostTracker（成本追踪）
│   │   └── project.py             # Project/Character/Episode/PlotThread
│   │
│   └── utils/                     # 工具层
│       ├── media.py               # 视频信息获取
│       └── sensitive_words.py     # 敏感词检测
│
├── projects/                      # 项目数据（gitignore）
│   └── {项目名}/
│       ├── project.json           # 项目数据
│       ├── characters/            # 角色参考图
│       └── episodes/ep{N}/        # 每集输出
│
├── output/                        # 非项目模式的输出（gitignore）
│
└── tests/                         # 测试层（100个用例）
    ├── conftest.py                # 公共fixtures
    ├── test_schemas.py            # Schema校验
    ├── test_screenwriter.py       # 编剧Agent
    ├── test_director.py           # 导演Agent
    ├── test_editor.py             # 剪辑/合成
    ├── test_reviewer.py           # 审核/敏感词
    ├── test_kling.py              # 可灵CLI
    ├── test_cost_tracker.py       # 成本追踪
    ├── test_project.py            # 项目管理
    └── test_graph.py              # 状态机路由
```

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   CLI 用户交互层                      │
│              src/main.py + graph.py                  │
│    项目管理 → 收集输入 → 启动流水线 → 人工审核节点      │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│              编排调度层 (LangGraph)                    │
│                   src/graph.py                       │
│    状态机 + 条件路由 + 3个人工审核 + 打回循环           │
└───────────────────────┬─────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────┐
│                  Agent 执行层                         │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ 编剧Agent │ │ 导演Agent │ │ 剪辑Agent │ │审核Agent│ │
│  │DeepSeek  │ │ 纯规则    │ │ 可灵+合成 │ │DeepSeek│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
└───────┼────────────┼────────────┼────────────┼──────┘
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────┐
│                  Service 服务层                       │
│                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────┐ │
│  │DeepSeek│ │可灵CLI │ │Edge-TTS│ │ MoviePy合成  │ │
│  │  LLM   │ │视频/图片│ │/静音   │ │ 拼接+字幕   │ │
│  └────────┘ └────────┘ └────────┘ └──────────────┘ │
│                                                      │
│  ┌──────────────┐ ┌──────────────────┐              │
│  │  成本追踪服务  │ │  项目管理服务     │              │
│  └──────────────┘ └──────────────────┘              │
└─────────────────────────────────────────────────────┘
```

---

## 3. 流水线流程

```
START → 编剧Agent → [①脚本审核] → 导演Agent → [②方案审核] → 剪辑Agent
                                                              ↓
END ← [③成片审核] ← 审核Agent ←──────────────────────────────┘
         ↓ (打回)
      剪辑Agent（最多2轮）
```

### 3个人工审核节点

| 节点 | 位置 | 展示内容 | 操作 |
|------|------|---------|------|
| ①脚本审核 | `graph.py:human_script_review_node` | 每个镜头的画面/旁白/字幕 | [a]确认 [r]修改 [q]取消 |
| ②方案审核 | `graph.py:human_plan_review_node` | 可灵调用计划+完整prompt+预估成本 | [a]确认生成 [r]返回修改 [q]取消 |
| ③成片审核 | `graph.py:human_video_review_node` | 视频文件+审核评分 | [a]确认 [r]重新剪辑 [q]取消 |

**②方案审核是关键**：在调用可灵（花钱）之前，显示每个镜头的完整prompt和预估总成本，确认后才开始生成。

---

## 4. 四个Agent角色详解

### 4.1 编剧Agent — `src/agents/screenwriter.py`

| 属性 | 值 |
|------|-----|
| **调用LLM** | 是，DeepSeek（chat或reasoner，可配置） |
| **输入** | 主题 + 类型 + 项目上下文（角色/前情/伏笔/世界观） |
| **输出** | `Script` 对象（分镜脚本JSON） |
| **Prompt模板** | `config/templates/screenwriter/{type}.txt` |

**注入的项目上下文**：
- 角色设定（外貌+性格+当前状态）
- 角色当前外貌描述
- 世界观设定 + 视觉风格 + 色调
- 故事阶段划分
- 创作备忘
- 未解决的伏笔/剧情线索
- 最近3集的详细回顾（摘要+关键事件+角色状态变化）
- 整体故事大纲
- 当前集数

**模型选择**（`LLM_SCREENWRITER_TIER`）：
- `auto` — science/story用reasoner，trending/product用chat
- `chat` — 全部用deepseek-chat（快、省）
- `reasoner` — 全部用deepseek-reasoner（深度思考）

### 4.2 导演Agent — `src/agents/director.py`

| 属性 | 值 |
|------|-----|
| **调用LLM** | 否（纯规则引擎） |
| **输入** | `Script` 对象 |
| **输出** | `ProductionPlan` 对象（制作任务书） |

**决策规则**：
- 素材质量：priority=high → hd，其他 → standard
- BGM风格：幽默→轻快电子，严肃→简约钢琴，悬疑→暗黑氛围
- 字幕动画：science→typewriter，story→fade，带货→slide_up
- 转场：trending/product→cut，其他→crossfade

### 4.3 剪辑Agent — `src/agents/editor.py`

| 属性 | 值 |
|------|-----|
| **调用LLM** | 否 |
| **调用服务** | KlingService + ImageGenService + TTSService + VideoComposeService |
| **输入** | `Script` + `ProductionPlan` + `Project` |
| **输出** | 视频文件路径 + 素材映射 |

**生成策略**（`KLING_VIDEO_MODE`）：
- `all_video` — 全部用可灵文生视频
- `mixed` — 开头/结尾用视频，中间用图片
- `all_image` — 全部用可灵文生图片（最省）

**角色一致性**：
- 自动匹配镜头中涉及的角色
- 如果角色有参考图，优先用 `image_to_video`（图生视频）保持外貌一致
- 在prompt中注入角色当前外貌描述

**降级链**：
```
可灵文生视频 → 可灵图生视频(有参考图时) → 可灵文生图片 → 本地占位图
```

### 4.4 审核Agent — `src/agents/reviewer.py`

| 属性 | 值 |
|------|-----|
| **调用LLM** | 是，DeepSeek chat |
| **通过分数** | 60分 |
| **可关闭** | `LLM_REVIEWER_ENABLED=false` |

**审核维度**：
- 合规检查（一票否决）：敏感词匹配
- 技术质量（30%）：时长/字幕/转场
- 内容质量（40%）：叙事连贯/画面匹配/开头吸引力
- 平台适配（30%）：标题/互动引导

---

## 5. 项目管理系统

### 5.1 目录结构

```
projects/
├── 赘婿逆袭/
│   ├── project.json              # 项目数据
│   ├── characters/               # 角色参考图
│   │   ├── 张伟.png
│   │   └── 王美丽.png
│   └── episodes/                 # 每集输出
│       ├── ep01/
│       │   ├── script.json
│       │   ├── plan.json
│       │   ├── draft.mp4
│       │   └── assets/
│       └── ep02/
└── 校园恋爱/
    └── ...
```

### 5.2 Project 数据模型 — `src/schemas/project.py`

```
Project
├── 基本信息: project_id, name, genre, tone
├── 世界观: world_setting
├── 故事规划: overall_story, planned_episodes, story_arcs[]
├── 视觉风格: visual_style, color_tone
├── 音乐: bgm_style, bgm_tracks[]
├── 发布: target_platform[], publish_schedule, tags[]
├── 受众: target_audience
├── 统计: total_cost, episode_costs{}
├── 素材库: reusable_assets[]
├── 备注: notes[]
├── characters: Character[]
│   └── Character
│       ├── name, description, personality
│       ├── current_state（当前状态，随剧情更新）
│       ├── current_appearance（当前外貌，可随剧情变化）
│       ├── reference_image_path（角色参考图路径）
│       └── appearance_history[]（外貌变化历史）
├── episodes: EpisodeSummary[]
│   └── EpisodeSummary
│       ├── episode_number, title, summary
│       ├── script_path, video_path
│       ├── characters_appeared[]
│       ├── character_states{}（角色状态变化）
│       ├── plot_threads[]（涉及的伏笔ID）
│       └── key_events[]（关键事件）
├── plot_threads: PlotThread[]
│   └── PlotThread
│       ├── thread_id, description
│       ├── introduced_episode, resolved, resolved_episode
│       └── importance（low/normal/high/critical）
└── created_at, updated_at
```

### 5.3 项目管理服务 — `src/services/project_manager.py`

| 方法 | 作用 |
|------|------|
| `list_projects()` | 列出所有项目 |
| `get_project(id)` | 按ID获取项目 |
| `get_project_by_name(name)` | 按名称获取项目 |
| `create_project(...)` | 创建项目（含目录初始化） |
| `save_project(project)` | 保存项目到JSON |
| `add_episode(project, episode)` | 添加集数 |
| `get_episode_dir(project, ep_num)` | 获取集数输出目录 |
| `get_previous_episodes_summary(project)` | 生成前情提要 |
| `build_screenwriter_context(project)` | 构建编剧Agent完整上下文 |
| `update_character_states(project, episode)` | 更新角色状态 |
| `update_character_appearance(...)` | 更新角色外貌（含历史记录） |
| `generate_character_reference_image(...)` | 用可灵生成角色参考图 |
| `add_plot_thread(...)` | 添加伏笔/剧情线索 |
| `resolve_plot_thread(...)` | 标记伏笔已解决 |
| `delete_project(id)` | 删除整个项目目录 |

### 5.4 连续剧工作流

```
第1集: 创建项目 → 设定角色 → 生成参考图 → 生成视频 → 录入信息 → 保存
第2集: 选择项目 → 注入前情+角色+伏笔 → 生成视频 → 录入信息 → 保存
第3集: 选择项目 → 注入前情+角色+伏笔 → 生成视频 → 录入信息 → 保存
...
```

**每集结束后可录入**：
- 剧情摘要
- 关键事件
- 角色状态变化
- 角色外貌变化（可选重新生成参考图）
- 新增伏笔
- 解决已有伏笔

---

## 6. 成本控制配置

所有配置在 `.env` 中设置：

### 6.1 可灵视频生成

| 配置项 | 默认值 | 说明 | 省钱效果 |
|--------|--------|------|---------|
| `KLING_MODEL` | `kling-video-v2_5` | 最便宜的视频模型 | ~30% |
| `KLING_RESOLUTION` | `720p` | 标准画质 | ~50% |
| `KLING_DURATION` | `5` | 固定5秒 | ~50% |
| `KLING_VIDEO_MODE` | `all_video` | all_video/mixed/all_image | mixed省~40% |
| `KLING_IMAGE_MODEL` | `kling-image-v2_1` | 最便宜的图片模型 | 图片免费 |
| `KLING_IMAGE_RESOLUTION` | `1k` | 图片标准分辨率 | - |
| `PREVIEW_MODE` | `false` | 只生成第1个镜头 | 省~75% |
| `MAX_SHOTS` | `4` | 最大镜头数 | 按比例省 |

### 6.2 LLM

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `LLM_SCREENWRITER_TIER` | `chat` | auto/chat/reasoner |
| `LLM_REVIEWER_ENABLED` | `true` | 是否启用审核Agent |
| `LLM_REVIEWER_TIER` | `efficient` | 审核模型档位 |

### 6.3 预算

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MAX_TOKENS_PER_VIDEO` | 8000 | 单视频最大token数 |
| `MAX_IMAGES_PER_VIDEO` | 8 | 单视频最大生成数 |
| `COST_LIMIT_PER_VIDEO` | 5.0 | 单视频预算上限(CNY) |

### 6.4 最省方案

```env
KLING_VIDEO_MODE=all_image
KLING_MODEL=kling-video-v2_5
KLING_RESOLUTION=720p
KLING_DURATION=5
MAX_SHOTS=2
PREVIEW_MODE=true
LLM_SCREENWRITER_TIER=chat
LLM_REVIEWER_ENABLED=false
```

---

## 7. Service层说明

### 7.1 LLM服务 — `src/services/llm.py`

| 属性 | 值 |
|------|-----|
| **后端** | DeepSeek API |
| **模型** | `deepseek-chat` / `deepseek-reasoner` |
| **输出格式** | 强制JSON（`response_format: json_object`） |
| **重试** | JSON解析失败最多重试2次 |

**价格**（元/百万token）：
| 模型 | 输入 | 输出 |
|------|------|------|
| deepseek-chat | ¥1.0 | ¥2.0 |
| deepseek-reasoner | ¥4.0 | ¥16.0 |

### 7.2 可灵CLI服务 — `src/services/kling.py`

| 属性 | 值 |
|------|-----|
| **后端** | 可灵CLI（`@klingai/cli-cn`） |
| **认证** | OAuth浏览器登录（`kling login`） |
| **模式** | 异步：提交任务 → `--poll` 自动等待 → 下载 |
| **默认模型** | `kling-video-v2_5` |

**支持的操作**：
| 方法 | CLI命令 | 用途 |
|------|---------|------|
| `text_to_video()` | `kling text_to_video` | 文生视频 |
| `text_to_image()` | `kling text_to_image` | 文生图 |
| `image_to_video()` | `kling image_to_video` | 图生视频（角色一致性） |
| `check_login()` | `kling who_am_i` | 检查登录状态 |

**价格参考**（720p）：
| 模型 | 5秒 | 10秒 |
|------|-----|------|
| kling-video-v2_5 | ~¥1.76 | ~¥3.53 |
| kling-video-v2_6 | ~¥2.02 | ~¥4.03 |
| kling-video-v3_0_turbo | ~¥3.53 | ~¥7.06 |

### 7.3 其他服务

| 服务 | 文件 | 说明 |
|------|------|------|
| 占位图 | `image_gen.py` | Pillow生成灰色占位图（可灵失败时降级） |
| TTS | `tts.py` | Edge-TTS语音合成 / 静音WAV占位 |
| 视频合成 | `video_compose.py` | MoviePy拼接+字幕（微软雅黑字体） |
| 成本追踪 | `cost_tracker.py` | 记录token/图片/TTS费用 |
| 项目管理 | `project_manager.py` | 项目CRUD+角色+伏笔+集数管理 |

---

## 8. 全局状态 — `src/state.py`

```python
class VideoState(TypedDict):
    # 用户输入
    video_id, user_input, content_type, tone, duration

    # 项目上下文
    project, episode_number, previous_episodes_summary
    character_descriptions, project_context, output_dir

    # Agent产出
    script, production_plan
    generated_clips, generated_images, generated_audios
    video_draft_path, final_video_path
    review_report, review_round

    # 全局控制
    cost_tracker, human_feedback, human_action, status, error
```

---

## 9. 运行与测试

### 启动

```bash
# 主入口（交互式）
python -m src.main

# 非交互测试（自动批准所有审核）
python test_run.py
```

### 测试

```bash
# 运行全部100个测试
pytest tests/ -v

# 运行lint检查
ruff check src/ tests/ config/
```

### 测试覆盖

| 测试文件 | 用例数 | 覆盖范围 |
|---------|--------|---------|
| `test_schemas.py` | 12 | Schema序列化/反序列化/边界值 |
| `test_screenwriter.py` | 14 | 镜头数计算 + 模型选择 + Agent执行 |
| `test_director.py` | 11 | 质量/BGM/字幕/转场决策 |
| `test_editor.py` | 2 | SRT时间格式化 + 字幕生成 |
| `test_reviewer.py` | 4 | 敏感词检测 |
| `test_kling.py` | 21 | CLI调用 + URL提取 + 成本估算 |
| `test_cost_tracker.py` | 8 | 成本记录 + 超限检测 |
| `test_project.py` | 14 | 项目CRUD + 集数 + 伏笔 |
| `test_graph.py` | 9 | 状态机路由逻辑 |
