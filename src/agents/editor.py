from pathlib import Path

from src.agents.base import BaseAgent, AgentError
from src.services.kling import KlingService, KlingError
from src.services.image_gen import ImageGenService
from src.services.tts import TTSService, TTSError
from src.services.video_compose import VideoComposeService, ComposeError
from src.services.cost_tracker import CostTrackerService
from src.schemas.script import Script
from src.schemas.plan import ProductionPlan
from src.state import VideoState
from config.settings import settings


class EditorAgent(BaseAgent):
    def __init__(self):
        super().__init__("editor")
        self.kling_service = KlingService() if settings.kling_access_key else None
        self.image_service = ImageGenService()
        self.tts_service = TTSService()
        self.video_composer = VideoComposeService()

    def execute(self, state: VideoState) -> dict:
        self.check_budget(state)

        script: Script = state["script"]
        plan: ProductionPlan = state["production_plan"]
        video_id = state["video_id"]

        output_dir = Path(settings.output_dir) / video_id
        assets_dir = output_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        generated_clips = {}
        generated_images = {}
        tracker = CostTrackerService(state["cost_tracker"])

        source_map = {s.shot_id: s for s in plan.shot_sources}
        for shot in script.shots:
            source = source_map.get(shot.id)
            prompt = source.generate_prompt if source and source.generate_prompt else shot.image_prompt

            if self.kling_service:
                clip_path = str(assets_dir / f"clip_{shot.id:02d}.mp4")
                kling_duration = 5 if shot.duration <= 7 else 10

                try:
                    result = self.kling_service.text_to_video(
                        prompt=prompt,
                        output_path=clip_path,
                        duration=kling_duration,
                        aspect_ratio="9:16",
                    )
                    generated_clips[shot.id] = result["path"]
                    tracker.record_image_generation(count=1, cost=result["cost"])
                    continue
                except KlingError as e:
                    self.logger.warning("kling_failed", shot_id=shot.id, error=str(e))

            img_path = str(assets_dir / f"shot_{shot.id:02d}.png")
            self.image_service.generate(prompt=prompt, output_path=img_path)
            generated_images[shot.id] = img_path
            tracker.record_image_generation(count=1, cost=0.0)

        generated_audios = {}
        voice_id = script.global_settings.voice_id
        voice_rate = self.tts_service.speed_to_rate(script.global_settings.voice_speed)

        for shot in script.shots:
            audio_path = str(assets_dir / f"narration_{shot.id:02d}.mp3")
            try:
                result = self.tts_service.synthesize_sync(
                    text=shot.narration,
                    output_path=audio_path,
                    voice=voice_id,
                    rate=voice_rate,
                    duration=shot.duration,
                )
                generated_audios[shot.id] = result["path"]
            except TTSError as e:
                self.logger.warning("tts_failed", shot_id=shot.id, error=str(e))
                raise AgentError(self.name, f"音频生成失败 shot {shot.id}: {e}")

        shots_data = [shot.model_dump() for shot in script.shots]

        global_settings = script.global_settings.model_dump()
        global_settings["bgm_volume"] = plan.audio_plan.bgm_volume

        video_path = str(output_dir / "draft.mp4")
        try:
            self.video_composer.compose(
                shots=shots_data,
                clips=generated_clips,
                images=generated_images,
                audios=generated_audios,
                output_path=video_path,
                global_settings=global_settings,
            )
        except ComposeError as e:
            raise AgentError(self.name, f"视频合成失败: {e}")

        script_path = str(output_dir / "script.json")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script.model_dump_json(indent=2))

        plan_path = str(output_dir / "plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan.model_dump_json(indent=2))

        self.logger.info("editing_complete", video=video_path)

        return {
            "generated_clips": generated_clips,
            "generated_images": generated_images,
            "generated_audios": generated_audios,
            "video_draft_path": video_path,
            "cost_tracker": tracker.get_tracker(),
            "status": "reviewing",
        }
