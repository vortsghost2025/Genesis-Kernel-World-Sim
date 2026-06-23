""" HLS live playlist manager — dynamic .m3u8 for streaming. """
from __future__ import annotations
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("world.hls_stream")

class HLSStreamManager:
    """Manages a live HLS .m3u8 playlist and segment registry."""

    def __init__(
        self,
        segment_dir: str | Path,
        playlist_path: str | Path,
        web_base_url: str = "/stream",
        segment_duration_s: int = 18,
        mode: str = "nim-live",
    ) -> None:
        self._segment_dir = Path(segment_dir)
        self._segment_dir.mkdir(parents=True, exist_ok=True)
        self._playlist_path = Path(playlist_path)
        self._playlist_path.parent.mkdir(parents=True, exist_ok=True)
        self._web_base_url = web_base_url.rstrip("/")
        self._segment_duration_s = segment_duration_s
        self._mode = mode
        self._segment_registry: list[dict[str, Any]] = []
        self._sequence_num = 0
        self._ensure_stale_removed()

    def _ensure_stale_removed(self) -> None:
        try:
            for f in self._segment_dir.glob("*.ts"):
                f.unlink()
            old = self._playlist_path
            if old.exists():
                old.unlink()
        except Exception:
            pass
        self._segment_registry.clear()
        self._sequence_num = 0

    def register_segment(self, ts_path: str, duration_s: float, tick: int) -> dict[str, Any]:
        self._sequence_num += 1
        entry = {
            "sequence": self._sequence_num,
            "tick": tick,
            "filename": Path(ts_path).name,
            "url": f"{self._web_base_url}/{Path(ts_path).name}",
            "duration": duration_s,
        }
        self._segment_registry.append(entry)
        self._regenerate_playlist()
        return entry

    def _regenerate_playlist(self) -> None:
        max_age = self._segment_duration_s * 3
        cutoff = time.time() - max_age
        self._segment_registry = [s for s in self._segment_registry if s.get("added_at", time.time()) >= cutoff]
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", f"#EXT-X-TARGETDURATION:{self._segment_duration_s + 1}", "#EXT-X-MEDIA-SEQUENCE:0"]
        for entry in self._segment_registry:
            lines.append(f"#EXTINF:{entry['duration']:.3f},")
            lines.append(entry["url"])
            entry["added_at"] = entry.get("added_at", time.time())
        if self._mode == "mock":
            lines += ["#EXT-X-ENDLIST"]
        else:
            lines += [f"#EXT-X-START:TIME-OFFSET=0"]
        try:
            self._playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.error("Playlist write failed: %s", exc)

    @property
    def playlist_url(self) -> str:
        return f"{self._web_base_url}/playlist.m3u8"

    @property
    def playlist_path(self) -> Path:
        return self._playlist_path

    @property
    def segment_dir(self) -> Path:
        return self._segment_dir

    def reset(self) -> None:
        self._ensure_stale_removed()
