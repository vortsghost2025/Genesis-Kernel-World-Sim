"""Image generation provider — NVIDIA NIM Visual GenAI (SDXL-Turbo / SDXL)."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.providers.base import call_log

logger = logging.getLogger("world.image_gen")

GENAI_BASE = "https://ai.api.nvidia.com/v1/genai"

CINEMATIC_STYLE_PREFIXES = {
    "cinematic_biblical": (
        "Renaissance oil painting masterpiece, dramatic chiaroscuro lighting. "
        "Caravaggio-style deep shadows and golden highlights. Epic biblical landscape. "
        "Atmospheric. Highly detailed. Cinematic composition."
    ),
}

KEN_BURNS_PRESETS = [
    {
        "filter": "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,zoompan=z='min(zoom+0.0004,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25",
        "label": "zoom_in",
    },
    {
        "filter": "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,zoompan=z='max(zoom-0.0004,0.9)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25",
        "label": "zoom_out",
    },
    {
        "filter": "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,zoompan=z=1:x='x+0.5':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25",
        "label": "pan_right",
    },
    {
        "filter": "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,zoompan=z=1:x='x-0.5':y='ih/2-(ih/zoom/2)':s=1280x720:fps=25",
        "label": "pan_left",
    },
    {"filter": "", "label": "static"},
]

MODEL_CHAIN = [
    "stabilityai/sdxl-turbo",
    "stabilityai/stable-diffusion-xl",
    "inference-sh-flux",
]

IMAGE_GEN_TIMEOUT_S = 15


@dataclass
class ImageGenResult:
    success: bool
    image_path: str = ""
    image_b64: str = ""
    model: str = ""
    latency_ms: float = 0.0
    error: str = ""
    size: str = ""
    seed: int = 0


class ImageGenProvider:
    """NVIDIA NIM image generation via GenAI endpoint."""

    def __init__(
        self,
        api_key_env: str = "NVIDIA_API_KEY",
        model: str = "stabilityai/sdxl-turbo",
        fallback_model: str = "stabilityai/stable-diffusion-xl",
        size: str = "1280x720",
        output_dir: str | None = None,
        mode: str = "nim-live",
    ) -> None:
        self._api_key_env = api_key_env
        self._model = model
        self._fallback_model = fallback_model
        self._size = size
        self._mode = mode
        self._call_count = 0

        if output_dir:
            self._output_dir = Path(output_dir)
        else:
            self._output_dir = (
                Path(__file__).resolve().parent.parent.parent / "data" / "scenes"
            )
        self._output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def model(self) -> str:
        return self._model

    @property
    def mode(self) -> str:
        return self._mode

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str | None = None,
        seed: int | None = None,
        cfg_scale: float = 4.0,
        steps: int = 30,
        scene_id: str = "",
        tick: int = 0,
    ) -> ImageGenResult:
        start = time.monotonic()
        effective_size = size or self._size
        effective_seed = seed if seed is not None else int(time.time()) % 4294967295

        if self._mode == "nim-live":
            return self._live_call(
                prompt,
                negative_prompt,
                effective_size,
                effective_seed,
                cfg_scale,
                steps,
                scene_id,
                tick,
                start,
            )
        elif self._mode == "nim-dry-run":
            return self._dry_run(
                prompt, effective_size, effective_seed, scene_id, tick, start
            )
        else:
            return self._mock(
                prompt, effective_size, effective_seed, scene_id, tick, start
            )

    def _live_call(
        self,
        prompt,
        negative_prompt,
        size,
        seed,
        cfg_scale,
        steps,
        scene_id,
        tick,
        start,
    ) -> ImageGenResult:
        api_key = os.environ.get(self._api_key_env, "")
        if not api_key:
            elapsed = (time.monotonic() - start) * 1000
            call_log.record(
                "image_gen", "pipeline", tick, False, round(elapsed, 2), "No API key"
            )
            return ImageGenResult(
                success=False, error="No API key configured", latency_ms=elapsed
            )

        chain = [m for m in MODEL_CHAIN if m]
        result = self._try_chain(
            chain, prompt, negative_prompt, size, seed, api_key, tick
        )

        elapsed = (time.monotonic() - start) * 1000
        result.latency_ms = round(elapsed, 2)

        fname = f"scene_{scene_id or tick}_{int(time.time())}.png"
        save_path = self._output_dir / fname
        if result.success and result.image_b64:
            try:
                img_bytes = base64.b64decode(result.image_b64)
                save_path.write_bytes(img_bytes)
                result.image_path = str(save_path)
                logger.info("Image saved: %s (%d bytes)", save_path, len(img_bytes))
            except Exception as exc:
                result.error = f"Save failed: {exc}"
                result.success = False

        call_log.record(
            "image_gen",
            "pipeline",
            tick,
            result.success,
            round(elapsed, 2),
            model=result.model,
        )
        return result

    def _try_chain(
        self, models, prompt, negative_prompt, size, seed, api_key, tick
    ) -> ImageGenResult:
        last_error = ""
        for model in models:
            if model == "inference-sh-flux":
                result = self._inference_sh_flux(prompt, size, tick)
            else:
                result = self._genai_call(
                    model, prompt, negative_prompt, size, seed, api_key
                )
            if result.success:
                return result
            last_error = result.error
            logger.warning("Model %s failed: %s", model, last_error)
        return ImageGenResult(
            success=False,
            error=last_error,
            model=models[-1] if models else "",
            size=size,
            seed=seed,
        )

    def _inference_sh_flux(self, prompt: str, size: str, tick: int) -> ImageGenResult:
        """Fallback to inference.sh CLI (FLUX) when NVIDIA NIM fails."""
        import subprocess

        api_key = os.environ.get("INFERENCE_API_KEY", "")
        if not api_key:
            return ImageGenResult(success=False, error="INFERENCE_API_KEY not set")
        try:
            # Download infsh CLI binary for Windows if not present
            infsh_path = Path.home() / ".local" / "bin" / "infsh.exe"
            if not infsh_path.exists():
                return ImageGenResult(success=False, error="infsh CLI not installed")

            result = subprocess.run(
                [
                    str(infsh_path),
                    "app",
                    "run",
                    "falai/flux-dev-lora",
                    "--input",
                    json.dumps({"prompt": prompt[:500]}),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "INFERENCE_API_KEY": api_key},
            )
            if result.returncode != 0:
                return ImageGenResult(
                    success=False, error=f"infsh flux failed: {result.stderr[:100]}"
                )
            # Parse output - infsh returns JSON with result URL
            try:
                output = json.loads(result.stdout)
                img_url = output.get("result", "")
                if not img_url:
                    return ImageGenResult(
                        success=False, error="No result URL from infsh"
                    )
                with urllib.request.urlopen(img_url, timeout=30) as resp:
                    img_bytes = resp.read()
                    b64 = base64.b64encode(img_bytes).decode("utf-8")
                    return ImageGenResult(
                        success=True, image_b64=b64, model="flux-dev-lora"
                    )
            except Exception as parse_err:
                return ImageGenResult(success=False, error=f"Parse error: {parse_err}")
        except FileNotFoundError:
            return ImageGenResult(success=False, error="infsh CLI not found")
        except Exception as exc:
            return ImageGenResult(success=False, error=str(exc))

    def _genai_call(
        self,
        model: str,
        prompt: str,
        negative_prompt: str,
        size: str,
        seed: int,
        api_key: str,
    ) -> ImageGenResult:
        url = f"{GENAI_BASE}/{model}"
        payload: dict = {
            "text_prompts": [{"text": prompt[:800], "weight": 1.0}],
            "n": 1,
            "seed": seed,
        }
        if negative_prompt:
            payload["text_prompts"].append(
                {"text": negative_prompt[:500], "weight": -1.0}
            )
        cfg = payload.copy()
        cfg["cfg_scale"] = 7.0
        cfg["steps"] = 20
        payload.update(cfg)

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Accept", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=IMAGE_GEN_TIMEOUT_S) as resp:
                raw = resp.read().decode("utf-8")
                body = json.loads(raw)
                artifacts = body.get("artifacts", [])
                if not artifacts:
                    return ImageGenResult(
                        success=False,
                        error="No artifacts in response",
                        model=model,
                        size=size,
                        seed=seed,
                    )
                b64 = artifacts[0].get("base64", "")
                if not b64:
                    return ImageGenResult(
                        success=False,
                        error="Empty base64 in artifact",
                        model=model,
                        size=size,
                        seed=seed,
                    )
                return ImageGenResult(
                    success=True, image_b64=b64, model=model, size=size, seed=seed
                )
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            logger.error("Image gen HTTP %d for %s: %s", exc.code, model, err_body)
            return ImageGenResult(
                success=False,
                error=f"HTTP {exc.code}: {err_body}",
                model=model,
                size=size,
                seed=seed,
            )
        except Exception as exc:
            logger.error("Image gen error for %s: %s", model, exc)
            return ImageGenResult(
                success=False, error=str(exc), model=model, size=size, seed=seed
            )

    def _dry_run(self, prompt, size, seed, scene_id, tick, start) -> ImageGenResult:
        elapsed = (time.monotonic() - start) * 1000
        call_log.record(
            "image_gen", "pipeline", tick, True, round(elapsed, 2), model=self._model
        )
        return ImageGenResult(
            success=True,
            model=self._model,
            size=size,
            seed=seed,
            latency_ms=round(elapsed, 2),
            image_path="",
        )

    def _mock(self, prompt, size, seed, scene_id, tick, start) -> ImageGenResult:
        elapsed = (time.monotonic() - start) * 1000
        call_log.record(
            "image_gen", "pipeline", tick, True, round(elapsed, 2), model="mock"
        )
        return ImageGenResult(
            success=True,
            model="mock",
            size=size,
            seed=seed,
            latency_ms=round(elapsed, 2),
        )

    def build_cinematic_prompt(
        self, narrative, world_snapshot=None, style="cinematic_biblical"
    ):
        prefix = CINEMATIC_STYLE_PREFIXES.get(
            style, CINEMATIC_STYLE_PREFIXES["cinematic_biblical"]
        )
        context = ""
        if world_snapshot:
            parts = [
                world_snapshot.get("weather", ""),
                world_snapshot.get("time_of_day", ""),
                f"garden:{world_snapshot.get('garden_condition', '')}",
            ]
            parts = [p for p in parts if p]
            if parts:
                context = f"Scene context: {', '.join(parts)}. "
        return f"{prefix} {context}Scene: {narrative[:400]}"

    def get_ken_burns_preset(self, tick: int, regen_interval: int = 5) -> dict:
        idx = (tick // regen_interval) % len(KEN_BURNS_PRESETS)
        return KEN_BURNS_PRESETS[idx]

    def generate_scene(
        self,
        narrative,
        tick,
        scene_id="",
        world_snapshot=None,
        style="cinematic_biblical",
    ):
        prompt = self.build_cinematic_prompt(narrative, world_snapshot, style)
        kb = self.get_ken_burns_preset(tick)
        result = self.generate(
            prompt=prompt, scene_id=scene_id or f"t{tick}", tick=tick
        )
        return result, kb
