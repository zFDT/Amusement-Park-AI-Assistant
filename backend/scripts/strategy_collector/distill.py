"""
AI 攻略提炼模块
使用 Claude Haiku（视觉模型）对小红书图文攻略进行智能提炼，生成简洁实用的摘要。

小红书攻略大量信息藏在图片中（截图、手写笔记、地图标注），
因此需要视觉模型才能完整理解内容。
"""

import asyncio
import base64
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
import anthropic

logger = logging.getLogger(__name__)

# 提炼用的 system prompt
_SYSTEM = (
    "你是一个迪士尼乐园游园助理，专门从小红书攻略中提炼实用信息。"
    "请用详细总结以下攻略的核心建议，包括：游玩顺序/时间安排、"
    "排队技巧（哪些项目要早去/晚去）、餐饮建议、特别提示（闪电通道、身高限制等）。"
    "输出纯文本，简洁实用，直接写成一段话，不要分点列举，不要重复标题。"
)

# XHS CDN 图片下载时需要带 Referer，否则 403
_XHS_HEADERS = {
    "Referer": "https://www.xiaohongshu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

SUPPORTED_DISTILL_API_MODES = {"openai", "openai-responses", "anthropic", "gemini"}


def _profile_to_distill_config(profile: Any) -> dict[str, str]:
    api_mode = getattr(profile, "api_mode", "anthropic") or "anthropic"
    if api_mode not in SUPPORTED_DISTILL_API_MODES:
        api_mode = "anthropic"
    return {
        "code": getattr(profile, "code", ""),
        "api_mode": api_mode,
        "base_url": getattr(profile, "base_url", "") or "",
        "api_key": getattr(profile, "api_key", "") or "",
        "model": getattr(profile, "model_id", "") or "",
    }


def resolve_distill_ai_config() -> dict[str, str] | None:
    """Resolve strategy-distill AI config from env profiles.

    Priority:
    1) AI_INTERNAL_PROFILES + AI_DISTILL_PROFILE_CODE
    2) Single AI_INTERNAL_PROFILES entry
    3) Legacy ANTHROPIC_API_KEY fallback
    """
    profiles = getattr(settings, "ai_internal_profiles", []) or []
    preferred_code = (getattr(settings, "ai_distill_profile_code", "") or "").strip()

    if profiles:
        if preferred_code:
            matched = next((p for p in profiles if getattr(p, "code", "") == preferred_code), None)
            if matched is not None:
                cfg = _profile_to_distill_config(matched)
                logger.info("AI 提炼将使用内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
                return cfg
            logger.warning("未找到 AI_DISTILL_PROFILE_CODE=%s 对应的配置，将尝试自动选择", preferred_code)

        if len(profiles) == 1:
            cfg = _profile_to_distill_config(profiles[0])
            logger.info("AI 提炼将使用唯一内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
            return cfg

        # 兜底：优先选择 Anthropic 相关配置，其次选择第一个有 key 的配置
        candidates = [p for p in profiles if getattr(p, "api_key", "")]
        anthropic_candidate = next((p for p in candidates if (getattr(p, "api_mode", "") or "").lower() == "anthropic"), None)
        chosen = anthropic_candidate or (candidates[0] if candidates else None)
        if chosen is not None:
            cfg = _profile_to_distill_config(chosen)
            logger.info("AI 提炼自动选择内测配置 code=%s, api_mode=%s", cfg["code"], cfg["api_mode"])
            return cfg

    legacy_api_key = getattr(settings, "anthropic_api_key", "") or ""
    if legacy_api_key:
        logger.info("AI 提炼将使用 legacy ANTHROPIC_API_KEY")
        return {
            "code": "legacy",
            "api_mode": "anthropic",
            "base_url": "https://api.anthropic.com",
            "api_key": legacy_api_key,
            "model": getattr(settings, "claude_model", "claude-sonnet-4-6"),
        }

    return None


async def _fetch_image_b64(url: str, client: httpx.AsyncClient) -> tuple[str, str] | None:
    """下载图片并返回 (media_type, base64_data)，失败返回 None"""
    try:
        resp = await client.get(url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not ct.startswith("image/"):
                ct = "image/jpeg"
            return ct, base64.standard_b64encode(resp.content).decode()
    except Exception as e:
        logger.debug(f"图片下载失败 {url[:60]}: {e}")
    return None


def _build_text_body(title: str, content: str) -> str:
    return f"标题：{title or '（无标题）'}\n\n正文：{content or '（无文字，请从图片中提取信息）'}"


def _build_image_parts_for_anthropic(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    return [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
        for media_type, b64 in images
    ]


def _build_image_parts_for_openai(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for media_type, b64 in images:
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_type};base64,{b64}"},
        })
    return parts


def _build_image_parts_for_gemini(images: list[tuple[str, str]]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for media_type, b64 in images:
        parts.append({"inline_data": {"mime_type": media_type, "data": b64}})
    return parts


async def distill_strategy(
    title: str,
    content: str,
    image_urls: list[str],
    api_key: str,
    base_url: str | None = None,
    model: str = "claude-haiku-4-5-20251001",
    api_mode: str = "anthropic",
) -> str | None:
    """
    调用视觉模型提炼攻略，返回 AI 摘要字符串。
    失败时返回 None（不抛异常，采集流程不应因提炼失败而中断）。
    """
    if not api_key:
        logger.warning("未配置 API Key，跳过 AI 提炼")
        return None

    api_mode = api_mode if api_mode in SUPPORTED_DISTILL_API_MODES else "anthropic"
    text_body = _build_text_body(title, content)
    image_payloads: list[tuple[str, str]] = []

    urls_to_fetch = image_urls[:4]
    if urls_to_fetch:
        async with httpx.AsyncClient(headers=_XHS_HEADERS) as http:
            results = await asyncio.gather(
                *[_fetch_image_b64(u, http) for u in urls_to_fetch],
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, tuple):
                image_payloads.append(result)

    try:
        if api_mode in {"openai", "openai-responses"}:
            url = f"{(base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
            payload = {
                "model": model,
                "max_tokens": 300,
                "messages": [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": [{"type": "text", "text": text_body}, *_build_image_parts_for_openai(image_payloads)]},
                ],
            }
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
                response.raise_for_status()
                data = response.json()
                summary = data["choices"][0]["message"]["content"].strip()
        elif api_mode == "gemini":
            base = (base_url or "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
            url = f"{base}/models/{model}:generateContent"
            payload = {
                "systemInstruction": {"parts": [{"text": _SYSTEM}]},
                "contents": [{
                    "role": "user",
                    "parts": [{"text": text_body}, *_build_image_parts_for_gemini(image_payloads)],
                }],
                "generationConfig": {"maxOutputTokens": 300},
            }
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload, headers={"x-goog-api-key": api_key})
                response.raise_for_status()
                data = response.json()
                summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            kwargs: dict = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = anthropic.AsyncAnthropic(**kwargs)
            response = await client.messages.create(
                model=model,
                max_tokens=300,
                system=_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": text_body}, *_build_image_parts_for_anthropic(image_payloads)],
                }],
            )
            summary = response.content[0].text.strip()

        logger.info(f"AI 提炼完成（{len(summary)}字）：{summary[:60]}…")
        return summary
    except anthropic.APIError as e:
        logger.error(f"Claude API 错误: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"AI 提炼 HTTP 错误: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"AI 提炼异常: {e}")
        return None


async def distill_batch(
    strategies: list[dict],
    api_key: str,
    base_url: str | None = None,
    api_mode: str = "anthropic",
    concurrency: int = 3,
) -> dict[str, str]:
    """
    批量提炼多条攻略，返回 {strategy_id: summary} 字典。
    使用信号量控制并发，避免 API 限速。
    """
    sem = asyncio.Semaphore(concurrency)
    results: dict[str, str] = {}

    async def _one(s: dict) -> None:
        async with sem:
            sid = s["id"]
            summary = await distill_strategy(
                title=s.get("title", ""),
                content=s.get("content", ""),
                image_urls=s.get("images", []),
                api_key=api_key,
                base_url=base_url,
                api_mode=api_mode,
            )
            if summary:
                results[sid] = summary

    await asyncio.gather(*[_one(s) for s in strategies])
    return results
