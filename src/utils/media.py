def get_video_duration(video_path: str) -> float:
    try:
        from moviepy import VideoFileClip
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception:
        return 0.0


def get_video_resolution(video_path: str) -> tuple[int, int]:
    try:
        from moviepy import VideoFileClip
        clip = VideoFileClip(video_path)
        size = clip.size
        clip.close()
        return (size[0], size[1])
    except Exception:
        return (0, 0)
