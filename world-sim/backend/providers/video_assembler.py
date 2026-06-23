""" ffmpeg video assembler — Ken Burns effect + audio mux + HLS .ts segment. """
from __future__ import annotations
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("world.video_assembler")

@dataclass
class SegmentResult:
    success: bool
    ts_path: str = ""
    duration_s: float = 0.0
    ffmpeg_log: str = ""
    error: str = ""

class VideoAssembler:
    """Assembles a video segment from a still image + audio via ffmpeg."""

    def __init__(
        self,
        segment_dir: str | Path,
        segment_duration_s: int = 18,
        fps: int = 24,
        width: int = 1280,
        height: int = 720,
        mode: str = "nim-live",
    ) -> None:
        self._segment_dir = Path(segment_dir)
        self._segment_dir.mkdir(parents=True, exist_ok=True)
        self._segment_duration_s = segment_duration_s
        self._fps = fps
        self._width = width
        self._height = height
        self._mode = mode

    def assemble(
        self,
        image_path: str,
        audio_path: str,
        segment_id: str,
        tick: int,
        ken_burns: dict[str, str] | None = None,
    ) -> SegmentResult:
        start = time.monotonic()
        ts_path = self._segment_dir / f"seg_{segment_id or tick}_{int(time.time())}.ts"

        if self._mode == "mock":
            elapsed = (time.monotonic() - start) * 1000
            logger.info("video_assembler: mock mode, no ffmpeg run")
            return SegmentResult(success=True, ts_path=str(ts_path), duration_s=0.1)

        kb_filter = self._build_ken_burns_filter(ken_burns)

        if not shutil.which("ffmpeg"):
            return SegmentResult(success=False, error="ffmpeg not found on PATH")
        if not Path(audio_path).exists():
            return SegmentResult(success=False, error=f"Audio not found: {audio_path}")
        if not Path(image_path).exists():
            return SegmentResult(success=False, error=f"Image not found: {image_path}")

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(image_path),
            "-i", str(audio_path),
            "-filter_complex", f"[0:v]{kb_filter}[v]",
            "-map", "[v]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "fast", "-tune", "stillimage",
            "-pix_fmt", "yuv420p", "-r", str(self._fps),
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1",
            "-shortest",
            "-f", "mpegts",
            "-t", str(self._segment_duration_s),
            str(ts_path),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            elapsed = (time.monotonic() - start) * 1000
            if proc.returncode != 0:
                err = proc.stderr[-500:] if proc.stderr else "ffmpeg failed"
                logger.error("ffmpeg failed: %s", err)
                return SegmentResult(success=False, error=f"ffmpeg rc={proc.returncode}", ffmpeg_log=err)
            size = ts_path.stat().st_size
            logger.info("Segment assembled: %s (%d bytes, %.1fs)", ts_path, size, elapsed / 1000)
            return SegmentResult(success=True, ts_path=str(ts_path), duration_s=self._segment_duration_s)
        except subprocess.TimeoutExpired:
            return SegmentResult(success=False, error="ffmpeg timeout")
        except Exception as exc:
            return SegmentResult(success=False, error=str(exc))

    def _build_ken_burns_filter(self, kb: dict[str, str] | None) -> str:
        if kb and kb.get("filter"):
            return kb["filter"]
        return (
            f"scale={self._width}:{self._height}:force_original_aspect_ratio=decrease,"
            f"pad={self._width}:{self._height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"fps={self._fps}"
        )
