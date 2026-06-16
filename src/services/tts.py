import struct
import wave
from pathlib import Path
import structlog

logger = structlog.get_logger()

SAMPLE_RATE = 44100
NUM_CHANNELS = 1
SAMPLE_WIDTH = 2


class TTSService:
    def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str = "placeholder",
        rate: str = "+0%",
        volume: str = "+0%",
        duration: float = 5.0,
    ) -> dict:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            num_samples = int(SAMPLE_RATE * duration)
            with wave.open(output_path, "w") as wf:
                wf.setnchannels(NUM_CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(SAMPLE_RATE)
                silence = struct.pack(f"<{num_samples}h", *([0] * num_samples))
                wf.writeframes(silence)

            logger.info("silence_audio_generated", path=output_path, duration=duration)
            return {"path": output_path, "cost": 0.0}

        except Exception as e:
            raise TTSError(f"静音音频生成失败: {e}")

    @staticmethod
    def speed_to_rate(speed: float) -> str:
        pct = int((speed - 1.0) * 100)
        return f"+{pct}%" if pct >= 0 else f"{pct}%"


class TTSError(Exception):
    pass
