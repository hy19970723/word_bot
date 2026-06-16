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
        from moviepy import (
            VideoFileClip, ImageClip, AudioFileClip,
            TextClip, CompositeVideoClip, concatenate_videoclips,
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        composed_clips = []
        for shot in shots:
            shot_id = shot["id"]
            duration = shot["duration"]
            clip_path = clips.get(shot_id)
            image_path = images.get(shot_id)
            audio_path = audios.get(shot_id)

            if clip_path and Path(clip_path).exists():
                base_clip = VideoFileClip(clip_path)
                if base_clip.duration > duration:
                    base_clip = base_clip.subclipped(0, duration)
                elif base_clip.duration < duration:
                    speed_factor = base_clip.duration / duration
                    base_clip = base_clip.with_speed_scaled(speed_factor)
                base_clip = base_clip.resized((VIDEO_WIDTH, VIDEO_HEIGHT))
            elif image_path and Path(image_path).exists():
                base_clip = ImageClip(image_path, duration=duration)
                base_clip = base_clip.resized((VIDEO_WIDTH, VIDEO_HEIGHT))
            else:
                logger.warning("missing_asset", shot_id=shot_id)
                continue

            if audio_path and Path(audio_path).exists():
                try:
                    audio_clip = AudioFileClip(audio_path)
                    if audio_clip.duration > duration:
                        audio_clip = audio_clip.subclipped(0, duration)
                    base_clip = base_clip.with_audio(audio_clip)
                except Exception as e:
                    logger.warning("audio_attach_failed", shot_id=shot_id, error=str(e))

            subtitle_text = shot.get("subtitle", "")
            if subtitle_text:
                try:
                    txt_clip = TextClip(
                        text=subtitle_text.replace("\\n", "\n"),
                        font_size=global_settings.get("subtitle_font_size", 42),
                        color=global_settings.get("subtitle_color", "white"),
                        stroke_color=global_settings.get("subtitle_outline_color", "black"),
                        stroke_width=global_settings.get("subtitle_outline_width", 2),
                        font="Arial",
                        size=(VIDEO_WIDTH - 100, None),
                        method="caption",
                        text_align="center",
                    )
                    txt_clip = txt_clip.with_duration(duration)
                    position = global_settings.get("subtitle_position", "bottom")
                    if position == "top":
                        txt_clip = txt_clip.with_position(("center", 100))
                    elif position == "center":
                        txt_clip = txt_clip.with_position(("center", "center"))
                    else:
                        txt_clip = txt_clip.with_position(("center", VIDEO_HEIGHT - 300))
                    base_clip = CompositeVideoClip([base_clip, txt_clip], size=(VIDEO_WIDTH, VIDEO_HEIGHT))
                except Exception as e:
                    logger.warning("subtitle_render_failed", shot_id=shot_id, error=str(e))

            composed_clips.append(base_clip)

        if not composed_clips:
            raise ComposeError("没有可用的视频片段")

        final = concatenate_videoclips(composed_clips, method="compose")

        final.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            logger=None,
        )

        for clip in composed_clips:
            clip.close()
        final.close()

        logger.info("video_composed", output=output_path)
        return output_path

    def _generate_srt(self, shots: list[dict], output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        lines = []
        current_time = 0.0
        for i, shot in enumerate(shots, 1):
            duration = shot["duration"]
            start_time = self._format_srt_time(current_time)
            end_time = self._format_srt_time(current_time + duration)
            subtitle = shot.get("subtitle", shot.get("narration", ""))
            lines.append(f"{i}")
            lines.append(f"{start_time} --> {end_time}")
            lines.append(subtitle)
            lines.append("")
            current_time += duration

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class ComposeError(Exception):
    pass
