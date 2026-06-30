# AI Video Studio

多Agent协作的短视频自动化生产系统，支持连续剧/系列视频创作。

## 技术栈

- **LLM**: DeepSeek (chat/reasoner 分级)
- **视频生成**: 可灵 CLI (MCP)
- **视频合成**: MoviePy
- **编排引擎**: LangGraph
- **语音合成**: Edge-TTS

## 快速开始

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 3. 登录可灵
kling login

# 4. 运行
python -m src.main
```

## 项目结构

```
projects/                    # 项目数据（每个项目独立目录）
├── 赘婿逆袭/
│   ├── project.json         # 项目数据
│   ├── characters/          # 角色参考图
│   └── episodes/ep01/       # 每集输出
└── 校园恋爱/
    └── ...
```

详细代码结构见 [CODE_STRUCTURE.md](CODE_STRUCTURE.md)

## 核心功能

- **多Agent流水线**: 编剧 → 导演 → 剪辑 → 审核
- **人工审核节点**: 脚本审核、方案审核（花钱前确认）、成片审核
- **项目管理**: 角色设定、参考图、剧情延续、伏笔管理
- **角色一致性**: 参考图 + image_to_video 保持外貌一致
- **成本控制**: 模型分级、分辨率、时长、生成模式均可配置
- **连续剧支持**: 前情提要、角色状态追踪、外貌演变历史
