import json
import re
from datetime import datetime, timezone
from typing import AsyncIterator

import anthropic

from app.core.config import settings
from app.schemas import PlanningInfo, RouteItem, AIConfig
from app.services.prompt_builder import build_system_prompt

_default_client: anthropic.AsyncAnthropic | None = None


def _get_client(ai_config: AIConfig | None = None) -> anthropic.AsyncAnthropic:
    """返回 AI 客户端。优先使用用户传入的配置，否则使用服务端默认配置。"""
    if ai_config:
        return anthropic.AsyncAnthropic(
            api_key=ai_config.auth_token,
            base_url=ai_config.base_url,
        )
    global _default_client
    if _default_client is None:
        _default_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _default_client


def _resolve_model(ai_config: AIConfig | None) -> str:
    if ai_config and ai_config.model:
        return ai_config.model
    return settings.claude_model


def _parse_route_from_text(text: str) -> list[RouteItem] | None:
    match = re.search(r"```route\s*([\s\S]*?)```", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
        return [RouteItem(**item) for item in data]
    except Exception:
        return None


async def stream_chat_response(
    planning: PlanningInfo,
    messages: list[dict],
    wait_times_json: str,
    completed_attractions: list[str],
    current_location: dict | None,
    strategy_snippets: list[str] | None = None,
    ai_config: AIConfig | None = None,
) -> AsyncIterator[dict]:
    current_time = datetime.now(timezone.utc).astimezone().isoformat()
    system_prompt = build_system_prompt(
        planning=planning,
        wait_times_json=wait_times_json,
        current_time=current_time,
        completed_attractions=completed_attractions,
        current_location=current_location,
        strategy_snippets=strategy_snippets,
    )

    client = _get_client(ai_config)
    model = _resolve_model(ai_config)
    accumulated = ""

    async with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            accumulated += text
            yield {"type": "text", "content": text}

    route = _parse_route_from_text(accumulated)
    if route:
        yield {"type": "route_update", "route": [r.model_dump() for r in route]}

    yield {"type": "done"}


async def generate_initial_plan(
    planning: PlanningInfo,
    wait_times_json: str,
    strategy_snippets: list[str] | None = None,
    ai_config: AIConfig | None = None,
) -> tuple[str, list[RouteItem]]:
    current_time = datetime.now(timezone.utc).astimezone().isoformat()
    system_prompt = build_system_prompt(
        planning=planning,
        wait_times_json=wait_times_json,
        current_time=current_time,
        completed_attractions=[],
        current_location=None,
        strategy_snippets=strategy_snippets,
    )

    client = _get_client(ai_config)
    model = _resolve_model(ai_config)
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": "请根据我的信息，为我生成一份完整的今日游园路线规划。",
            }
        ],
    )

    text = response.content[0].text
    route = _parse_route_from_text(text) or []
    return text, route
