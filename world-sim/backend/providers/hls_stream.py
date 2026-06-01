"""
HLS Stream Playlist Manager.

Manages the live .m3u8 playlist file, adding fresh segments, and maintaining
a sliding window to clean up older files to prevent disk usage growth.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("world.provider.hls_stream")


class HLSPlaylistManager:
    """Manages a rolling live HLS stream playlist (.m3u8)."""

    def __init__(self, output_dir: Path, target_duration: int = 18, window_size: int = 10) -> None:
        self.output_dir = output_dir
        self.target_duration = target_duration
        self.window_size = window_size
        self.segments: list[str] = []
        self.media_sequence: int = 0
        
        # Ensure output directory exists and is empty on startup
        self.reset_stream()

    def reset_stream(self) -> None:
        """Clear all previous HLS files to start fresh."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.segments = []
        self.media_sequence = 0
        
        # Clear previous segments and playlists
        for f in self.output_dir.glob("*.ts"):
            try:
                f.unlink()
            except Exception:
                pass
        for f in self.output_dir.glob("*.m3u8"):
            try:
                f.unlink()
            except Exception:
                pass
                
        self.write_playlist()
        logger.info("HLS stream initialized and reset in: %s", self.output_dir)

    def add_segment(self, segment_filename: str) -> None:
        """Add a new segment and slide the window if it exceeds window_size."""
        self.segments.append(segment_filename)
        
        # Sliding window cleanup: keep only last N segments on disk and in playlist
        if len(self.segments) > self.window_size:
            removed_seg = self.segments.pop(0)
            self.media_sequence += 1
            
            # Delete old segment file from disk
            old_file = self.output_dir / removed_seg
            if old_file.exists():
                try:
                    old_file.unlink()
                    logger.debug("Cleaned up old segment file: %s", removed_seg)
                except Exception as e:
                    logger.warning("Failed to clean up old segment: %s — %s", removed_seg, e)

        self.write_playlist()

    def write_playlist(self) -> None:
        """Compile and write the live .m3u8 playlist file."""
        playlist_path = self.output_dir / "playlist.m3u8"
        
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{self.target_duration}",
            f"#EXT-X-MEDIA-SEQUENCE:{self.media_sequence}",
        ]
        
        for seg in self.segments:
            lines.append(f"#EXTINF:{self.target_duration}.0,")
            lines.append(seg)
            
        # Write file atomically
        temp_path = playlist_path.with_suffix(".tmp")
        try:
            temp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            temp_path.replace(playlist_path)
            logger.debug("Successfully updated HLS playlist (%d segments)", len(self.segments))
        except Exception as e:
            logger.error("Failed to write HLS playlist: %s", e)
