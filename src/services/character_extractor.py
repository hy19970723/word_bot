import json
from pydantic import BaseModel, Field
from src.services.llm import LLMService, LLMOutputError
from src.schemas.script import Script
from src.schemas.project import Character
import structlog

logger = structlog.get_logger()

EXTRACT_PROMPT = """你是一个角色分析专家。请从以下分镜脚本中提取所有角色信息。

分镜脚本：
{script_json}

请提取每个角色的：
1. 名称（从旁白和画面描述中推断）
2. 外貌描述（从image_prompt中提取，要具体详细，用于AI生图）
3. 性格描述（从旁白和行为中推断）

要求：
- 外貌描述要包含：年龄、性别、发型、服装、体型等具体特征
- 如果角色没有明确名称，根据特征给一个简短代号
- 只提取有实际出场的角色

请严格按照以下JSON格式输出：
{json_schema}"""


class ExtractedCharacters(BaseModel):
    characters: list[Character] = Field(description="提取到的角色列表")


class CharacterExtractor:
    def __init__(self):
        self.llm = LLMService(model_tier="efficient")

    def extract(self, script: Script) -> list[Character]:
        json_schema = json.dumps(ExtractedCharacters.model_json_schema(), ensure_ascii=False)
        prompt = EXTRACT_PROMPT.format(
            script_json=script.model_dump_json(indent=2),
            json_schema=json_schema,
        )

        try:
            result, usage = self.llm.generate_structured(prompt, ExtractedCharacters)
            logger.info(
                "characters_extracted",
                count=len(result.characters),
                names=[c.name for c in result.characters],
                cost=usage.get("cost", 0),
            )
            return result.characters
        except LLMOutputError as e:
            logger.warning("character_extraction_failed", error=str(e))
            return []
