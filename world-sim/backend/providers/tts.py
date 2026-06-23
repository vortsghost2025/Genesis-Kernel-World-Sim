"""Text-to-Speech provider — NVIDIA Riva TTS via gRPC (cloud) + HTTPS Magpie fallback."""

from __future__ import annotations

import logging
import os
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from backend.providers.base import call_log

logger = logging.getLogger("world.tts")

RIVA_CLOUD_HOST = "grpc.nvcf.nvidia.com:443"
RIVA_FUNCTION_ID = "5e607c81-7aa6-44ce-a11d-9e08f0a3fe49"
MAGPIE_TTS_URL = "https://integrate.api.nvidia.com/v1/audio/speech"
MAGPIE_TTS_MODEL = "nvidia/magpie-tts-multilingual"
GRPC_PROBE_TIMEOUT_S = 8
GRPC_DEADLINE_S = 30
DEFAULT_VOICE = "English-US.RadTTS.Female-1"
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_ENCODING = "LINEAR_PCM"

CHARACTER_VOICE_MAP: dict[str, str] = {
    "east_adam": "English-US.RadTTS.Male-1",
    "east_eve": "English-US.RadTTS.Female-1",
    "west_adam": "English-US.RadTTS.Male-2",
    "west_eve": "English-US.RadTTS.Female-2",
    "narrator": "English-US.RadTTS.Male-1",
}


@dataclass
class TTSResult:
    success: bool
    audio_path: str = ""
    audio_bytes: bytes = b""
    voice: str = ""
    sample_rate: int = 44100
    latency_ms: float = 0.0
    error: str = ""


class RivaTTSProvider:
    """NVIDIA Riva TTS — gRPC layer-1, HTTPS Magpie fallback layer-2."""

    _grpc_available: bool | None = None

    def __init__(
        self,
        api_key_env: str = "NVIDIA_API_KEY",
        voice: str = DEFAULT_VOICE,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        encoding: str = DEFAULT_ENCODING,
        function_id: str = RIVA_FUNCTION_ID,
        output_dir: str | None = None,
        mode: str = "nim-live",
    ) -> None:
        self._api_key_env = api_key_env
        self._voice = voice
        self._sample_rate = sample_rate
        self._encoding = encoding
        self._function_id = function_id
        self._mode = mode
        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = (
                Path(__file__).resolve().parent.parent.parent / "data" / "audio"
            )
        self._output_dir.mkdir(parents=True, exist_ok=True)
        if self._grpc_available is None:
            RivaTTSProvider._grpc_available = self._probe_grpc_channel()

    def _probe_grpc_channel(self) -> bool:
        try:
            import grpc

            ssl_creds = grpc.ssl_channel_credentials()
            channel = grpc.secure_channel(RIVA_CLOUD_HOST, ssl_creds)
            try:
                grpc.channel_ready_future(channel).result(timeout=GRPC_PROBE_TIMEOUT_S)
                logger.info("Riva gRPC channel probe OK")
                return True
            except Exception:
                logger.warning(
                    "Riva gRPC channel probe failed — will use HTTPS fallback"
                )
                return False
            finally:
                channel.close()
        except ImportError:
            logger.warning("riva-client / grpc not installed — HTTPS fallback only")
            return False
        except Exception as exc:
            logger.warning("Riva gRPC probe error: %s — HTTPS fallback only", exc)
            return False

    def synthesize(
        self,
        text: str,
        voice: str | None = None,
        sample_rate: int | None = None,
        scene_id: str = "",
        tick: int = 0,
    ) -> TTSResult:
        start = time.monotonic()
        effective_voice = voice or self._voice
        effective_rate = sample_rate or self._sample_rate
        if self._mode == "nim-live":
            return self._live_call(
                text, effective_voice, effective_rate, scene_id, tick, start
            )
        elif self._mode == "nim-dry-run":
            return self._dry_run(
                text, effective_voice, effective_rate, scene_id, tick, start
            )
        else:
            return self._mock(
                text, effective_voice, effective_rate, scene_id, tick, start
            )

    def _live_call(self, text, voice, sample_rate, scene_id, tick, start) -> TTSResult:
        api_key = os.environ.get(self._api_key_env, "")
        if not api_key:
            elapsed = (time.monotonic() - start) * 1000
            call_log.record(
                "riva_tts", "pipeline", tick, False, round(elapsed, 2), "No API key"
            )
            return TTSResult(
                success=False, error="No API key configured", latency_ms=elapsed
            )

        if self._grpc_available:
            result = self._grpc_call(
                text, voice, sample_rate, scene_id, tick, start, api_key
            )
            if result.success:
                return result
            logger.warning(
                "gRPC TTS failed (%s), falling back to HTTPS Magpie", result.error[:120]
            )

        return self._https_magpie(
            text, voice, sample_rate, scene_id, tick, start, api_key
        )

    def _grpc_call(
        self, text, voice, sample_rate, scene_id, tick, start, api_key
    ) -> TTSResult:
        try:
            import grpc
            from riva.client.proto import riva_tts_pb2, riva_tts_pb2_grpc
            from riva.client.proto import riva_audio_pb2

            ssl_creds = grpc.ssl_channel_credentials()
            channel = grpc.secure_channel(RIVA_CLOUD_HOST, ssl_creds)
            stub = riva_tts_pb2_grpc.RivaSpeechSynthesisStub(channel)
            metadata = [
                ("authorization", f"Bearer {api_key}"),
                ("function-id", self._function_id),
            ]
            req = riva_tts_pb2.SynthesizeSpeechRequest(
                text=text,
                language_code="en-US",
                encoding=riva_audio_pb2.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
                voice_name=voice,
            )
            response = stub.Synthesize(
                req,
                metadata=metadata,
                timeout=GRPC_DEADLINE_S,
            )
            audio_raw = response.audio
            elapsed = (time.monotonic() - start) * 1000
            fname = f"tts_{scene_id or tick}_{int(time.time())}.wav"
            save_path = self._output_dir / fname
            wav_bytes = self._pcm_to_wav(audio_raw, sample_rate)
            save_path.write_bytes(wav_bytes)
            logger.info(
                "TTS gRPC audio saved: %s (%d bytes)", save_path, len(wav_bytes)
            )
            call_log.record("riva_tts", "pipeline", tick, True, round(elapsed, 2))
            return TTSResult(
                success=True,
                audio_path=str(save_path),
                audio_bytes=wav_bytes,
                voice=voice,
                sample_rate=sample_rate,
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            call_log.record(
                "riva_tts", "pipeline", tick, False, round(elapsed, 2), str(exc)[:200]
            )
            logger.error("Riva gRPC TTS error: %s", exc, exc_info=True)
            return TTSResult(success=False, error=str(exc), latency_ms=elapsed)

    def _https_magpie(
        self, text, voice, sample_rate, scene_id, tick, start, api_key
    ) -> TTSResult:
        try:
            payload = {
                "model": MAGPIE_TTS_MODEL,
                "input": text[:2000],
                "voice": voice,
                "response_format": "wav",
                "sample_rate": sample_rate,
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/wav",
            }
            resp = httpx.post(
                MAGPIE_TTS_URL,
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            elapsed = (time.monotonic() - start) * 1000
            if resp.status_code != 200:
                err = f"Magpie HTTPS {resp.status_code}: {resp.text[:200]}"
                call_log.record(
                    "riva_tts", "magpie", tick, False, round(elapsed, 2), err
                )
                return TTSResult(success=False, error=err, latency_ms=elapsed)

            audio_bytes = resp.content
            fname = f"tts_{scene_id or tick}_magpie_{int(time.time())}.wav"
            save_path = self._output_dir / fname
            save_path.write_bytes(audio_bytes)
            logger.info(
                "TTS Magpie audio saved: %s (%d bytes)", save_path, len(audio_bytes)
            )
            call_log.record("riva_tts", "magpie", tick, True, round(elapsed, 2))
            return TTSResult(
                success=True,
                audio_path=str(save_path),
                audio_bytes=audio_bytes,
                voice=voice,
                sample_rate=sample_rate,
                latency_ms=round(elapsed, 2),
            )
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            call_log.record(
                "riva_tts", "magpie", tick, False, round(elapsed, 2), str(exc)[:200]
            )
            logger.error("Magpie TTS error: %s", exc, exc_info=True)
            return TTSResult(success=False, error=str(exc), latency_ms=elapsed)

    def _dry_run(self, text, voice, sample_rate, scene_id, tick, start) -> TTSResult:
        elapsed = (time.monotonic() - start) * 1000
        call_log.record("riva_tts", "pipeline", tick, True, round(elapsed, 2))
        return TTSResult(
            success=True,
            voice=voice,
            sample_rate=sample_rate,
            latency_ms=round(elapsed, 2),
        )

    def _mock(self, text, voice, sample_rate, scene_id, tick, start) -> TTSResult:
        elapsed = (time.monotonic() - start) * 1000
        call_log.record("riva_tts", "pipeline", tick, True, round(elapsed, 2))
        return TTSResult(
            success=True,
            voice=voice,
            sample_rate=sample_rate,
            latency_ms=round(elapsed, 2),
        )

    @staticmethod
    def _pcm_to_wav(
        pcm_data: bytes, sample_rate: int, channels: int = 1, bits: int = 16
    ) -> bytes:
        import numpy as np

        audio_arr = np.frombuffer(pcm_data, dtype=np.float32)
        audio_int16 = np.clip(audio_arr * 32767, -32768, 32767).astype(np.int16)
        pcm_int16 = audio_int16.tobytes()
        num_samples = len(audio_int16)
        data_size = num_samples * channels * (bits // 8)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            channels,
            sample_rate,
            sample_rate * channels * (bits // 8),
            channels * (bits // 8),
            bits,
            b"data",
            data_size,
        )
        return header + pcm_int16

    def voice_for_agent(self, agent_key: str, narrator_voice: str = "") -> str:
        return CHARACTER_VOICE_MAP.get(agent_key.lower(), narrator_voice or self._voice)

    def narrate_scene(
        self,
        narration_text: str,
        agent_key: str = "narrator",
        scene_id: str = "",
        tick: int = 0,
    ) -> TTSResult:
        voice = self.voice_for_agent(agent_key)
        return self.synthesize(
            narration_text, voice=voice, scene_id=scene_id, tick=tick
        )
