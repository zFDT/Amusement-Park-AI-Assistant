"""图片代理 — 解决小红书 CDN 图片 403 问题

XHS CDN 要求请求带 Referer: https://www.xiaohongshu.com 头，
前端直接加载 CDN URL 会被 403 拒绝。
此端点作为代理，后端请求图片时带正确 Referer，返回给前端。
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter(prefix="/images", tags=["images"])

_XHS_REFERER = "https://www.xiaohongshu.com"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# 允许代理的图片域名（安全白名单）
_ALLOWED_HOSTS = {
    "sns-webpic-qc.xhscdn.com",
    "sns-webpic.xhscdn.com",
    "ci.xiaohongshu.com",
    "sns-avatar-qc.xhscdn.com",
}


@router.get("/proxy")
async def proxy_image(
    url: str = Query(..., description="原始图片 CDN URL"),
):
    """代理获取小红书 CDN 图片，带正确 Referer 头避免 403。

    仅允许白名单内的 CDN 域名，防止被用作开放代理。
    """
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if host not in _ALLOWED_HOSTS and not host.endswith(".xhscdn.com"):
        raise HTTPException(status_code=400, detail=f"不支持的图片域名: {host}")

    headers = {
        "Referer": _XHS_REFERER,
        "User-Agent": _USER_AGENT,
    }

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail=f"上游返回 {resp.status_code}",
                )
            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                content=resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                },
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"图片获取失败: {e}")
