"""
Cosmic Video Pipeline Orchestrator.

Coordinates the entire generation flow:
Event Narrative -> Qwen-Image Gen -> Riva TTS Synthesis -> FFmpeg Mux -> HLS .m3u8 Registration.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any

from backend.config import config
from backend.providers.image_gen import generate_scene, KEN_BURNS_PRESETS
from backend.providers.tts import narrate_scene, voice_for_agent
from backend.providers.video_assembler import assemble_segment
from backend.providers.hls_stream import HLSPlaylistManager

logger = logging.getLogger("world.provider.video_pipeline")

# Diagnostic tracks
last_pipeline_error: str | None = None
last_image_error: str | None = None
last_tts_error: str | None = None
last_assembly_error: str | None = None
pipeline_runs_count: int = 0
pipeline_success_count: int = 0


class VideoPipeline:
    """Orchestrates text-to-video HLS generation on every simulation tick."""

    def __init__(self) -> None:
        self.cfg = config.video_config
        self.output_dir = Path(self.cfg.output_dir)
        self.temp_dir = self.output_dir / "temp"
        
        # Ensure clean folders
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Playlist Manager (retains rolling last N segments)
        self.playlist_manager = HLSPlaylistManager(
            output_dir=self.output_dir,
            target_duration=self.cfg.segment_duration_s,
            window_size=10
        )
        
    def process_tick(self, narrative: str, tick: int, agents_snapshot: dict[str, Any] | None = None) -> bool:
        """
        Takes the current narrative, generates scene canvas, TTS narration,
        compiles HLS segments, and registers them in the live playlist.
        """
        global last_pipeline_error, last_image_error, last_tts_error, last_assembly_error
        global pipeline_runs_count, pipeline_success_count
        
        pipeline_runs_count += 1
        
        if not self.cfg.enabled:
            logger.info("Video Pipeline is disabled in config. Skipping.")
            return False
            
        logger.info("Starting Video Pipeline for Tick %d...", tick)
        
        # Determine temporary workspace files
        temp_image_path = self.temp_dir / f"tick_{tick}.png"
        temp_audio_path = self.temp_dir / f"tick_{tick}.wav"
        
        # Output segment file
        segment_filename = f"segment_{tick}.ts"
        segment_output_path = self.output_dir / segment_filename
        
        # 1. Image Generation (or load existing/placeholder if we are on a 5-tick hold)
        image_success = False
        api_key = os.environ.get("NVIDIA_NIM_KEY", "") # Fallback key from env
        
        # Determine whether to regenerate image (e.g. every 5 ticks or if first tick)
        should_regenerate = (tick % self.cfg.regen_interval_ticks == 0) or (tick == 1) or not temp_image_path.exists()
        
        if should_regenerate:
            # Generate new scene
            image_success = generate_scene(
                prompt=narrative,
                output_path=str(temp_image_path),
                api_key=api_key,
                mode=self.cfg.image_provider
            )
            if not image_success:
                last_image_error = "NIM Image Generation call failed or returned empty payload."
                logger.warning("Image Generation failed. Falling back to procedurally drawn placeholder image.")
        else:
            # Re-use previous generated image to save API calls
            prev_tick = tick - 1
            prev_img = self.temp_dir / f"tick_{prev_tick}.png"
            if prev_img.exists():
                import shutil
                shutil.copy(prev_img, temp_image_path)
                image_success = True
                logger.info("Re-using image from previous tick: %d -> %d", prev_tick, tick)
            else:
                # If previous doesn't exist, generate fresh
                image_success = generate_scene(
                    prompt=narrative,
                    output_path=str(temp_image_path),
                    api_key=api_key,
                    mode=self.cfg.image_provider
                )
                
        # 2. TTS Audio Generation
        # Detect principal speaking character to choose speaking voice
        speaking_voice = "Narrator"
        if agents_snapshot:
            for name in agents_snapshot:
                if name in narrative:
                    speaking_voice = voice_for_agent(name)
                    break
                    
        tts_success = narrate_scene(
            text=narrative,
            output_path=str(temp_audio_path),
            voice_name=speaking_voice,
            duration_s=self.cfg.segment_duration_s,
            api_url=os.environ.get("RIVA_API_URL", "")
        )
        if not tts_success:
            last_tts_error = "Riva TTS failed or was unconfigured. Silently fell back to local silent WAV."
            
        # 3. FFmpeg Video Assembly (Apply Ken Burns and Mux)
        # Select random preset to make Ken Burns feel dynamic and non-repetitive
        preset_choice = random.choice(KEN_BURNS_PRESETS)["name"]
        
        assembly_success = assemble_segment(
            image_path=str(temp_image_path),
            audio_path=str(temp_audio_path),
            output_path=str(segment_output_path),
            duration_s=self.cfg.segment_duration_s,
            fps=self.cfg.fps,
            preset=preset_choice
        )
        
        if not assembly_success:
            last_assembly_error = "FFmpeg binary failed. Check if ffmpeg is installed and supports H.264."
            last_pipeline_error = f"Tick {tick} failed at FFmpeg assembly step."
            logger.error("FFmpeg Segment assembly failed.")
            return False
            
        # 4. Register in HLS Playlist
        self.playlist_manager.add_segment(segment_filename)
        
        # Cleanup temporary files (except the PNG for potential 5-tick hold reuse)
        if temp_audio_path.exists():
            try:
                temp_audio_path.unlink()
            except Exception:
                pass
                
        # Housekeeping: keep temp directory light
        self._cleanup_temp_dir()
        
        pipeline_success_count += 1
        logger.info("Video Pipeline completed successfully for Tick %d!", tick)
        return True

    def _cleanup_temp_dir(self) -> None:
        """Keep only the last 3 generated PNG files in temp workspace."""
        png_files = sorted(self.temp_dir.glob("*.png"), key=lambda x: x.stat().st_mtime)
        while len(png_files) > 3:
            removed_file = png_files.pop(0)
            try:
                removed_file.unlink()
            except Exception:
                pass


# Global single video pipeline instance
import os
video_pipeline = VideoPipeline()
