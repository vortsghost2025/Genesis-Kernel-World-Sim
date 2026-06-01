"""
FFmpeg Video Assembler.

Muxes AI-generated images (applying smooth Ken Burns zoom/pan animation)
with synthetic TTS audio tracks, rendering them directly into HLS transport stream (.ts) segments.
"""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger("world.provider.video_assembler")


def assemble_segment(
    image_path: str,
    audio_path: str,
    output_path: str,
    duration_s: int = 18,
    fps: int = 24,
    preset: str = "zoom_in_center"
) -> bool:
    """
    Assemble a single HLS .ts segment from an image and an audio track.
    Applies the Ken Burns effect using FFmpeg's zoompan filter.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    num_frames = duration_s * fps

    # Map Ken Burns presets to FFmpeg zoompan filters
    # We use 1280x720 (720p) for fast rendering and perfect compatibility
    if preset == "pan_left_right":
        # Slow pan horizontally
        zoom_filter = f"zoompan=z='1.1':x='(iw-iw/zoom)*(0.2+0.6*on/{num_frames})':y='(ih-ih/zoom)/2':d={num_frames}:s=1280x720:fps={fps}"
    elif preset == "zoom_out_center":
        # Slow zoom out
        zoom_filter = f"zoompan=z='1.15-0.15*on/{num_frames}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={num_frames}:s=1280x720:fps={fps}"
    elif preset == "pan_up_down":
        # Slow pan vertically
        zoom_filter = f"zoompan=z='1.1':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*(0.2+0.6*on/{num_frames})':d={num_frames}:s=1280x720:fps={fps}"
    elif preset == "zoom_bottom_right":
        # Zoom in towards bottom right
        zoom_filter = f"zoompan=z='1.0+0.15*on/{num_frames}':x='(iw-iw/zoom)*on/{num_frames}':y='(ih-ih/zoom)*on/{num_frames}':d={num_frames}:s=1280x720:fps={fps}"
    else:
        # Default zoom_in_center
        zoom_filter = f"zoompan=z='1.0+0.15*on/{num_frames}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d={num_frames}:s=1280x720:fps={fps}"

    # Build the ffmpeg command
    # -loop 1: loop the input image
    # -i image_path: image source
    # -i audio_path: audio WAV source
    # -c:v libx264: H.264 video codec
    # -pix_fmt yuv420p: widely compatible pixel format
    # -c:a aac: AAC audio codec
    # -shortest: end when the shortest input (audio) ends
    # -f mpegts: format output as MPEG Transport Stream
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(duration_s), "-i", image_path,
        "-i", audio_path,
        "-vf", zoom_filter,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", str(fps * 2),
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-f", "mpegts",
        output_path
    ]

    logger.info("Executing FFmpeg command for preset '%s': %s", preset, " ".join(cmd))

    try:
        # Run ffmpeg in a subprocess, capturing output for diagnostics
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            logger.error("FFmpeg compilation failed! error log:\n%s", result.stderr)
            return False
            
        logger.info("FFmpeg segment successfully built: %s", output_path)
        return True

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg assembly timed out after 120 seconds!")
        return False
    except Exception as e:
        logger.error("Failed to execute FFmpeg assembly: %s", e)
        return False
