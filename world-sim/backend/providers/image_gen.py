"""
NVIDIA NIM Image Generation Provider for Qwen-Image-2512.

Supports both hosted Cloud NIM API and local Self-Hosted NIM containers,
with a gorgeous Pillow-based procedural fallback on API error/outage.
"""

from __future__ import annotations

import base64
import logging
import os
import random
import requests
from PIL import Image, ImageDraw

logger = logging.getLogger("world.provider.image_gen")

# Ken Burns Presets (used by video_assembler to pan/zoom)
# Presets defined as (start_scale, end_scale, start_x, start_y, end_x, end_y)
KEN_BURNS_PRESETS = [
    # Slow Zoom In to Center
    {"name": "zoom_in_center", "scale_start": 1.0, "scale_end": 1.15, "x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
    # Pan Left to Right with Slight Zoom
    {"name": "pan_left_right", "scale_start": 1.08, "scale_end": 1.08, "x_start": 0.45, "y_start": 0.5, "x_end": 0.55, "y_end": 0.5},
    # Slow Zoom Out from Center
    {"name": "zoom_out_center", "scale_start": 1.15, "scale_end": 1.0, "x_start": 0.5, "y_start": 0.5, "x_end": 0.5, "y_end": 0.5},
    # Pan Up to Down
    {"name": "pan_up_down", "scale_start": 1.1, "scale_end": 1.1, "x_start": 0.5, "y_start": 0.45, "x_end": 0.5, "y_end": 0.55},
    # Slow Zoom In to Bottom-Right
    {"name": "zoom_bottom_right", "scale_start": 1.0, "scale_end": 1.12, "x_start": 0.5, "y_start": 0.5, "x_end": 0.53, "y_end": 0.53},
]


def generate_scene(prompt: str, output_path: str, api_key: str, mode: str = "hosted") -> bool:
    """
    Generate a visual scene using Qwen-Image-2512.
    Supports "hosted" (NVIDIA cloud catalog) and "self-hosted" (local container).
    """
    # Enhanced prompt styling for biblical renaissance oil painting style
    styled_prompt = (
        "A highly detailed, gorgeous, atmospheric renaissance oil painting of a biblical epic scene: "
        f"{prompt}. Dramatic chiaroscuro lighting, rich deep textures, warm colors, masterpiece visual."
    )
    
    if mode == "self-hosted":
        url = "http://localhost:8000/v1/images/generations"
        payload = {
            "model": "qwen/qwen-image-2512",
            "prompt": styled_prompt,
            "n": 1,
            "response_format": "b64_json"
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer not-needed"
        }
    else:
        # Hosted NVIDIA Cloud Endpoint
        url = "https://ai.api.nvidia.com/v1/genai/qwen/qwen-image-2512"
        payload = {
            "prompt": styled_prompt,
            "n": 1,
            "response_format": "b64_json"
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

    logger.info("Calling NIM Image Gen: url=%s mode=%s model=qwen/qwen-image-2512", url, mode)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        # Extract b64_json
        b64_data = None
        if mode == "self-hosted":
            b64_data = data.get("data", [{}])[0].get("b64_json")
        else:
            # Hosted NIM cloud catalog can have nested formats
            b64_data = data.get("data", [{}])[0].get("b64_json") or data.get("b64_json")
            
        if not b64_data:
            raise ValueError("No b64_json or image data found in response payload")

        img_bytes = base64.b64decode(b64_data)
        
        # Save to disk
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_bytes)
            
        logger.info("Successfully generated NIM scene: %s", output_path)
        return True

    except Exception as e:
        logger.error("NIM Image Generation API call failed: %s. Falling back to procedural placeholder.", e)
        # Generate placeholder image as robust fallback
        generate_placeholder_image(prompt, output_path)
        return False


def generate_placeholder_image(text: str, output_path: str) -> None:
    """
    Generate a high-quality cinematic placeholder gradient with the text overlay
    in case of API error, keeping the video assembly pipeline 100% operational.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 16:9 widescreen canvas (1024x576 resolution)
    width, height = 1024, 576
    
    # Draw a rich dark aesthetic gradient (simulated with 12 horizontal bands)
    img = Image.new('RGB', (width, height), color=(13, 17, 26))
    draw = ImageDraw.Draw(img)
    
    # Simple procedurally drawn background details (auras/beams)
    for i in range(height):
        # Dark celestial blue-purple gradient
        r = int(10 + (i / height) * 15)
        g = int(14 + (i / height) * 20)
        b = int(24 + (i / height) * 35)
        draw.line([(0, i), (width, i)], fill=(r, g, b))
        
    # Draw a thin classical gold border
    draw.rectangle([20, 20, width - 20, height - 20], outline=(212, 168, 83), width=2)
    
    # Write overlay text (word wrapped)
    wrapped_lines = []
    words = text.split()
    current_line = []
    
    for word in words:
        if len(" ".join(current_line + [word])) * 9 > (width - 160):
            wrapped_lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        wrapped_lines.append(" ".join(current_line))
        
    # Draw subtitle header
    draw.text((70, 70), "🌌 GENESIS CHRONICLE (Placeholder Canvas)", fill=(212, 168, 83))
    
    # Render lines onto the image
    y_offset = 150
    for line in wrapped_lines[:10]:
        draw.text((70, y_offset), line, fill=(240, 244, 248))
        y_offset += 30
        
    img.save(output_path)
    logger.info("Procedural placeholder image saved: %s", output_path)
