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
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
            await communicate.save(output_path)
            logger.info("edge_tts_synthesized", path=output_path, voice=voice)
            return {"path": output_path, "cost": 0.0}
        except ImportError:
            logger.warning("edge_tts_not_installed, falling back to silence")
            return self._generate_silence(output_path, duration)
        except Exception as e:
            logger.warning("edge_tts_failed", error=str(e), fallback="silence")
            return self._generate_silence(output_path, duration)

    def synthesize_sync(
        self,
        text: str,
        output_path: str,
        voice: str = "zh-CN-YunxiNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        duration: float = 5.0,
    ) -> dict:
        return asyncio.run(self.synthesize(text, output_path, voice, rate, volume, duration))

    @staticmethod
    def _generate_silence(output_path: str, duration: float) -> dict:
        import struct
        import wave

        sample_rate = 44100
        num_samples = int(sample_rate * duration)
        with wave.open(output_path, "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            silence = struct.pack(f"<{num_samples}h", *([0] * num_samples))
            wf.writeframes(silence)

        logger.info("silence_audio_generated", path=output_path, duration=duration)
        return {"path": output_path, "cost": 0.0}

    @staticmethod
    def speed_to_rate(speed: float) -> str:
        pct = int((speed - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"


class TTSError(Exception):
    pass
