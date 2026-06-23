"""Video pipeline orchestrator — narrative → image → TTS → ffmpeg → HLS."""

from __future__ import annotations
import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.providers.image_gen import ImageGenProvider, ImageGenResult
from backend.providers.tts import RivaTTSProvider, TTSResult
from backend.providers.video_assembler import VideoAssembler, SegmentResult
from backend.providers.hls_stream import HLSStreamManager
from backend.config import VideoConfig

logger = logging.getLogger("world.video_pipeline")


@dataclass
class TickVideoResult:
    tick: int
    hemisphere: str
    success: bool
    image_success: bool
    tts_success: bool
    segment_success: bool
    image_path: str = ""
    audio_path: str = ""
    segment_url: str = ""
    segment_path: str = ""
    latency_ms: float = 0.0
    error: str = ""
    used_placeholder_image: bool = False
    used_silent_audio: bool = False


class VideoPipeline:
    """Orchestrates per-tick video generation into an HLS livestream."""

    def __init__(self, cfg: VideoConfig) -> None:
        self._cfg = cfg
        self._enabled = cfg.enabled
        self.last_image_error: str = ""
        self.last_tts_error: str = ""
        self.last_assembly_error: str = ""
        if not self._enabled:
            return
        data_root = Path(__file__).resolve().parent.parent.parent
        seg_dir = data_root / cfg.hls_segment_dir
        playlist = data_root / cfg.hls_playlist_path
        self._scenes_dir = data_root / "data" / "scenes"
        self._audio_dir = data_root / "data" / "audio"
        self._scenes_dir.mkdir(parents=True, exist_ok=True)
        self._audio_dir.mkdir(parents=True, exist_ok=True)
        self._image = ImageGenProvider(
            output_dir=str(self._scenes_dir),
            mode="nim-live",
        )
        self._tts = RivaTTSProvider(
            voice=cfg.narrator_voice,
            output_dir=str(self._audio_dir),
            mode="nim-live",
        )
        self._assembler = VideoAssembler(
            segment_dir=seg_dir,
            segment_duration_s=cfg.segment_duration_s,
            mode="nim-live",
        )
        self._hls = HLSStreamManager(
            segment_dir=seg_dir,
            playlist_path=playlist,
            web_base_url=cfg.hls_web_path,
            segment_duration_s=cfg.segment_duration_s,
            mode="nim-live",
        )

    def _generate_placeholder_image(
        self, scene_id: str, tick: int, hemisphere: str
    ) -> str:
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            logger.warning("Pillow not available for placeholder image")
            return ""
        img = Image.new("RGB", (1280, 720), color=(20, 15, 10))
        draw = ImageDraw.Draw(img)
        draw.rectangle([10, 10, 1270, 710], outline=(120, 90, 40), width=3)
        draw.rectangle([20, 20, 1260, 700], outline=(80, 60, 30), width=1)
        lines = [
            "GENESIS WORLD SIM",
            f"--- {hemisphere.upper()} HEMISPHERE ---",
            f"Tick {tick}",
            "",
            "[ Scene generation unavailable ]",
            "[ API connectivity issue ]",
        ]
        y = 200
        for i, line in enumerate(lines):
            try:
                font = ImageFont.truetype("arial.ttf", 32 if i == 0 else 24)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            x = (1280 - tw) // 2
            color = (200, 170, 100) if i == 0 else (160, 140, 90)
            draw.text((x, y), line, fill=color, font=font)
            y += 44
        path = str(self._scenes_dir / f"placeholder_{scene_id}.png")
        img.save(path, "PNG")
        logger.info("placeholder image saved: %s", path)
        return path

    def _generate_silent_audio(self, scene_id: str, duration_s: int) -> str:
        path = str(self._audio_dir / f"silent_{scene_id}.aac")
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-t",
                str(duration_s),
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                path,
            ]
            subprocess.run(cmd, capture_output=True, timeout=30, check=True)
            logger.info("silent audio saved: %s", path)
            return path
        except Exception as exc:
            logger.error("failed to generate silent audio: %s", exc)
            try:
                from backend.providers.tts import RivaTTSProvider

                raw_pcm = b"\x00" * (44100 * 2 * duration_s)
                wav_bytes = RivaTTSProvider._pcm_to_wav(raw_pcm, 44100)
                wav_path = str(self._audio_dir / f"silent_{scene_id}.wav")
                Path(wav_path).write_bytes(wav_bytes)
                logger.info("silent audio (pure-Python WAV fallback): %s", wav_path)
                return wav_path
            except Exception as exc2:
                logger.error("pure-Python silent audio also failed: %s", exc2)
                return ""

    @property
    def enabled(self) -> bool:
        return self._enabled

    def process_tick(
        self,
        tick: int,
        hemisphere: str,
        narrative: str,
        world_snapshot: dict[str, Any] | None = None,
        agent_key: str = "narrator",
    ) -> TickVideoResult:
        start = time.monotonic()
        result = TickVideoResult(
            tick=tick,
            hemisphere=hemisphere,
            success=False,
            image_success=False,
            tts_success=False,
            segment_success=False,
        )
        try:
            img_result, kb = self._image.generate_scene(
                narrative=narrative,
                tick=tick,
                scene_id=f"{hemisphere}_t{tick}",
                world_snapshot=world_snapshot,
                style=self._cfg.style,
            )
            result.image_success = img_result.success
            result.image_path = img_result.image_path
            image_path: str = img_result.image_path
            if not img_result.success:
                self.last_image_error = img_result.error or "image generation failed"
                logger.warning(
                    "image gen failed tick=%d, using placeholder: %s",
                    tick,
                    self.last_image_error,
                )
                image_path = self._generate_placeholder_image(
                    scene_id=f"{hemisphere}_t{tick}",
                    tick=tick,
                    hemisphere=hemisphere,
                )
                if image_path:
                    result.image_path = image_path
                    result.used_placeholder_image = True
                else:
                    result.error = "image gen failed and placeholder also failed"
                    result.latency_ms = round((time.monotonic() - start) * 1000, 1)
                    return result

            tts_result = self._tts.narrate_scene(
                narration_text=narrative[:600],
                agent_key=agent_key,
                scene_id=f"{hemisphere}_t{tick}",
                tick=tick,
            )
            result.tts_success = tts_result.success
            result.audio_path = tts_result.audio_path
            audio_path: str = tts_result.audio_path
            if not tts_result.success:
                self.last_tts_error = tts_result.error or "TTS generation failed"
                logger.warning(
                    "TTS failed tick=%d, using silent audio: %s",
                    tick,
                    self.last_tts_error,
                )
                audio_path = self._generate_silent_audio(
                    scene_id=f"{hemisphere}_t{tick}",
                    duration_s=self._cfg.segment_duration_s,
                )
                if audio_path:
                    result.audio_path = audio_path
                    result.used_silent_audio = True
                else:
                    self.last_tts_error += "; silent audio fallback also failed"

            if image_path and audio_path:
                seg = self._assembler.assemble(
                    image_path=image_path,
                    audio_path=audio_path,
                    segment_id=f"{hemisphere}_t{tick}",
                    tick=tick,
                    ken_burns=kb,
                )
            else:
                seg = SegmentResult(
                    success=False, error="Missing image or audio after fallbacks"
                )
            result.segment_success = seg.success
            result.segment_path = seg.ts_path
            if not seg.success:
                self.last_assembly_error = seg.error or "assembly failed"
            if seg.success:
                reg = self._hls.register_segment(seg.ts_path, seg.duration_s, tick)
                result.segment_url = reg["url"]
            result.success = seg.success
            result.latency_ms = round((time.monotonic() - start) * 1000, 1)
            return result
        except Exception as exc:
            result.latency_ms = round((time.monotonic() - start) * 1000, 1)
            result.error = str(exc)
            logger.error("pipeline error tick=%d: %s", tick, exc, exc_info=True)
            return result

    def process_tick_async(
        self,
        tick: int,
        hemisphere: str,
        narrative: str,
        world_snapshot: dict[str, Any] | None = None,
        agent_key: str = "narrator",
    ) -> "asyncio.Future[TickVideoResult]":
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            None,
            self.process_tick,
            tick,
            hemisphere,
            narrative,
            world_snapshot,
            agent_key,
        )

    @property
    def hls_playlist_url(self) -> str:
        return self._hls.playlist_url if self._enabled else ""

    def reset(self) -> None:
        if self._enabled:
            self._hls.reset()
