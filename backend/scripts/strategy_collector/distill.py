"""
AI 攻略提炼模块
使用 Claude Haiku（视觉模型）对小红书图文攻略进行智能提炼，生成简洁实用的摘要。

小红书攻略大量信息藏在图片中（截图、手写笔记、地图标注），
因此需要视觉模型才能完整理解内容。
"""

import asyncio
import base64
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
import anthropic

logger = logging.getLogger(__name__)

# 提炼用的 system prompt
_SYSTEM = (
    "你是一个迪士尼乐园游园助理，专门从小红书攻略中提炼实用信息。"
    "请用100-150字总结以下攻略的核心建议，包括：游玩顺序/时间安排、"
    "排队技巧（哪些项目要早去/晚去）、餐饮建议、特别提示（闪电通道、身高限制等）。"
    "输出纯文本，简洁实用，直接写成一段话，不要分点列举，不要重复标题。"
)

# XHS CDN 图片下载时需要带 Referer，否则 403
_XHS_HEADERS = {
    "Referer": "https://www.xiaohongshu.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


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


async def distill_strategy(
    title: str,
    content: str,
    image_urls: list[str],
    api_key: str,
    base_url: str | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> str | None:
    """
    调用 Claude 视觉模型提炼攻略，返回 AI 摘要字符串。
    失败时返回 None（不抛异常，采集流程不应因提炼失败而中断）。

    Args:
        title: 笔记标题
        content: 笔记正文（可能为空，内容在图片里）
        image_urls: 图片 CDN URL 列表（最多取前4张）
        api_key: Anthropic API Key
        base_url: 自定义 API 地址（可选）
        model: 使用的模型，默认 Haiku 以控制成本
    """
    if not api_key:
        logger.warning("未配置 API Key，跳过 AI 提炼")
        return None

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.AsyncAnthropic(**kwargs)

    # 构建多模态消息
    parts: list = []

    text_body = f"标题：{title or '（无标题）'}\n\n正文：{content or '（无文字，请从图片中提取信息）'}"
    parts.append({"type": "text", "text": text_body})

    # 下载图片（最多4张，并发）
    urls_to_fetch = image_urls[:4]
    if urls_to_fetch:
        async with httpx.AsyncClient(headers=_XHS_HEADERS) as http:
            results = await asyncio.gather(
                *[_fetch_image_b64(u, http) for u in urls_to_fetch],
                return_exceptions=True,
            )
        for r in results:
            if isinstance(r, tuple):
                media_type, b64 = r
                parts.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                })

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=300,
            system=_SYSTEM,
            messages=[{"role": "user", "content": parts}],
        )
        summary = response.content[0].text.strip()
        logger.info(f"AI 提炼完成（{len(summary)}字）：{summary[:60]}…")
        return summary
    except anthropic.APIError as e:
        logger.error(f"Claude API 错误: {e}")
        return None
    except Exception as e:
        logger.error(f"AI 提炼异常: {e}")
        return None


async def distill_batch(
    strategies: list[dict],
    api_key: str,
    base_url: str | None = None,
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
            )
            if summary:
                results[sid] = summary

    await asyncio.gather(*[_one(s) for s in strategies])
    return results
