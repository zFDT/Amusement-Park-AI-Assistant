"""视觉定位 API——上传乐园照片，AI 识别当前位置。

模型兼容性：
- ✅ 支持：Anthropic Claude、Google Gemini、OpenAI GPT-4V/4o、Ollama vision 模型
- ❌ 不支持：DeepSeek（无视觉能力），会尝试自动回退到可用视觉模型
"""

import base64
import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.schemas import VisionLocateRequest, VisionLocateResponse, AIConfig
from app.services.ai_service import _resolve_runtime_config

router = APIRouter()
logger = logging.getLogger("app.vision")

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# ── 不支持视觉的 API 模式 ─────────────────────────────────────────────────
_VISION_BLIND_MODES = {"deepseek"}


def _find_vision_capable_fallback() -> dict[str, str] | None:
    """在内测配置中寻找一个支持视觉的模型作为回退。"""
    for profile in settings.ai_internal_profiles:
        if profile.api_mode not in _VISION_BLIND_MODES:
            from app.services.ai_service import API_MODE_DEFAULTS, SUPPORTED_API_MODES
            api_mode = profile.api_mode if profile.api_mode in SUPPORTED_API_MODES else "anthropic"
            return {
                "source": "internal",
                "api_key": profile.api_key.strip(),
                "base_url": profile.base_url,
                "api_mode": api_mode,
                "model_id": profile.model_id,
            }
    # 尝试使用服务端默认 Anthropic key
    if settings.anthropic_api_key:
        return {
            "source": "server",
            "api_key": settings.anthropic_api_key,
            "base_url": "https://api.anthropic.com",
            "api_mode": "anthropic",
            "model_id": settings.claude_model,
        }
    return None


def _load_area_names(park_id: str) -> list[str]:
    data_file = _DATA_DIR / f"{park_id}.json"
    if not data_file.exists():
        return []
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
        return [area["name"] for area in data.get("areas", []) if area.get("name")]
    except Exception:
        return []


def _load_attraction_names(park_id: str) -> list[str]:
    data_file = _DATA_DIR / f"{park_id}.json"
    if not data_file.exists():
        return []
    try:
        data = json.loads(data_file.read_text(encoding="utf-8"))
        names: list[str] = []
        for area in data.get("areas", []):
            for a in area.get("attractions", []):
                if a.get("name"):
                    names.append(a["name"])
        return names
    except Exception:
        return []


@router.post("/vision/locate", response_model=VisionLocateResponse)
async def vision_locate(request: VisionLocateRequest):
    """Use vision AI to identify current location from a photo."""
    area_names = _load_area_names(request.park_id)
    attraction_names = _load_attraction_names(request.park_id)

    park_name = "香港迪士尼乐园" if request.park_id == "hongkong_disney" else "上海迪士尼乐园"

    prompt = f"""这是一张在{park_name}拍摄的照片。请识别照片中显示的位置信息。

已知的园区区域：{', '.join(area_names)}
已知的游乐项目：{', '.join(attraction_names[:30])}

请分析照片，判断：
1. 用户当前在哪个区域（area_name）
2. 照片中是否有明显的项目/设施名称（attraction_name）
3. 给出一个简短的位置描述（label），例如"幻想世界入口附近"
4. 识别置信度（confidence）：high/medium/low

请以 JSON 格式回复，不要有其他内容：
{{"area_name": "区域名称或null", "attraction_name": "项目名称或null", "label": "位置描述", "confidence": "high/medium/low"}}"""

    try:
        runtime = _resolve_runtime_config(request.ai_config)
    except HTTPException as e:
        # Fall back to server default config
        try:
            runtime = _resolve_runtime_config(None)
        except HTTPException:
            runtime = None

    if runtime is None:
        return VisionLocateResponse(
            area_name=None, attraction_name=None,
            label="AI 服务未配置，无法识别位置",
            confidence="low",
        )

    api_mode = runtime["api_mode"]

    # ── 视觉模型兼容性检测 ───────────────────────────────────────────
    if api_mode in _VISION_BLIND_MODES:
        logger.info(
            "Vision locate: 当前模型 %s (%s) 不支持图像识别，尝试回退",
            runtime["model_id"], api_mode,
        )
        fallback = _find_vision_capable_fallback()
        if fallback:
            logger.info("Vision locate: 已回退到 %s (%s)", fallback["model_id"], fallback["api_mode"])
            runtime = fallback
        else:
            return VisionLocateResponse(
                area_name=None, attraction_name=None,
                label=f"当前 AI 模型（{runtime['model_id']}）不支持图像识别。请在 .env 中配置支持视觉的 AI 模型（如 Claude 或 Gemini）",
                confidence="low",
            )

    api_mode = runtime["api_mode"]
    base_url = runtime["base_url"].rstrip("/")
    api_key = runtime["api_key"]
    model_id = runtime["model_id"]

    image_data = request.image_base64
    image_type = request.image_type

    try:
        if api_mode == "anthropic":
            url = f"{base_url}/v1/messages"
            payload = {
                "model": model_id,
                "max_tokens": 256,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": image_type, "data": image_data}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            }
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        elif api_mode == "gemini":
            url = f"{base_url}/models/{model_id}:generateContent"
            payload = {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": image_type, "data": image_data}},
                        {"text": prompt},
                    ]
                }],
                "generationConfig": {"maxOutputTokens": 256},
            }
            headers = {"x-goog-api-key": api_key}
        else:
            # OpenAI-compatible (including deepseek with vision)
            url = f"{base_url}/chat/completions"
            payload = {
                "model": model_id,
                "max_tokens": 256,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{image_type};base64,{image_data}"}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            }
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        # Extract text from response
        text = ""
        if api_mode == "anthropic":
            content = data.get("content", [])
            text = content[0].get("text", "") if content else ""
        elif api_mode == "gemini":
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = parts[0].get("text", "") if parts else ""
        else:
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")

        # Parse JSON from response
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())

        return VisionLocateResponse(
            area_name=result.get("area_name"),
            attraction_name=result.get("attraction_name"),
            label=result.get("label", "位置识别中"),
            confidence=result.get("confidence", "low"),
        )

    except json.JSONDecodeError as e:
        logger.warning("Vision locate JSON parse failed: raw=%s error=%s", text[:200], e)
        return VisionLocateResponse(
            area_name=None, attraction_name=None,
            label=f"AI 返回格式异常，无法解析位置（原始回复: {text[:60]}...）",
            confidence="low",
        )
    except httpx.HTTPStatusError as e:
        logger.warning("Vision locate API error: %s %s", e.response.status_code, e.response.text[:300])
        return VisionLocateResponse(
            area_name=None, attraction_name=None,
            label=f"AI 服务返回错误（{e.response.status_code}），请稍后重试或检查 API 配置",
            confidence="low",
        )
    except Exception as e:
        logger.warning("Vision locate failed: %s", e)
        return VisionLocateResponse(
            area_name=None, attraction_name=None,
            label=f"位置识别失败（{type(e).__name__}），请手动描述附近标志物",
            confidence="low",
        )
