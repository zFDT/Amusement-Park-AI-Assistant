import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Iterable

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas import PlanningInfo, RouteItem, AIConfig
from app.services.prompt_builder import build_system_prompt

logger = logging.getLogger("app.ai")

API_MODE_DEFAULTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "openai-responses": ("https://api.openai.com/v1", "gpt-4.1-mini"),
    "ollama": ("http://localhost:11434", "llama3.1"),
    "anthropic": ("https://api.anthropic.com", settings.claude_model),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta", "gemini-2.5-pro"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-v4-flash"),
}

SUPPORTED_API_MODES = set(API_MODE_DEFAULTS.keys())


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = dict(headers)
    for key in list(redacted.keys()):
        if key.lower() in {"authorization", "x-api-key", "api-key", "anthropic-api-key"}:
            redacted[key] = "***REDACTED***"
    return redacted


def _log_ai_event(request_id: str, event: str, payload: object) -> None:
    if not settings.ai_debug_logging:
        return
    logger.info("[AI:%s] %s %s", request_id, event, _json_dumps(payload))


def _coalesce(value: str | None, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _resolve_runtime_config(ai_config: AIConfig | None) -> dict[str, str]:
    if ai_config and ai_config.source == "internal":
        code = (ai_config.internal_code or "").strip().lower()
        if not code:
            raise HTTPException(status_code=400, detail="配置错误：请填写内测码")

        profile = next((item for item in settings.ai_internal_profiles if item.code.lower() == code), None)
        if profile is None:
            raise HTTPException(status_code=400, detail=f"配置错误：内测码 '{ai_config.internal_code}' 未匹配到可用配置")

        api_mode = profile.api_mode if profile.api_mode in SUPPORTED_API_MODES else "anthropic"
        base_url = _coalesce(profile.base_url, API_MODE_DEFAULTS[api_mode][0])
        model_id = _coalesce(profile.model_id, API_MODE_DEFAULTS[api_mode][1])
        api_key = profile.api_key.strip()
        if api_mode != "ollama" and not api_key:
            raise HTTPException(status_code=400, detail="配置错误：内测配置缺少 API Key")

        return {
            "source": "internal",
            "api_key": api_key,
            "base_url": base_url,
            "api_mode": api_mode,
            "model_id": model_id,
        }

    api_mode = (ai_config.api_mode if ai_config and ai_config.api_mode in SUPPORTED_API_MODES else None) or None
    base_url = _coalesce(ai_config.base_url if ai_config else None, API_MODE_DEFAULTS[(api_mode or _infer_api_mode(ai_config))][0])
    api_mode = api_mode or _infer_api_mode(ai_config, base_url)
    model_id = _coalesce(
        ai_config.model_id if ai_config and ai_config.model_id else None,
        ai_config.model if ai_config and ai_config.model else API_MODE_DEFAULTS[api_mode][1],
    )
    api_key = _coalesce(
        ai_config.api_key if ai_config and ai_config.api_key else None,
        ai_config.auth_token if ai_config and ai_config.auth_token else settings.anthropic_api_key if api_mode == "anthropic" else "",
    )

    if api_mode != "ollama" and not api_key:
        raise HTTPException(status_code=400, detail="配置错误：API Key 不能为空")

    if not base_url:
        base_url = API_MODE_DEFAULTS[api_mode][0]

    return {
        "source": "custom",
        "api_key": api_key,
        "base_url": base_url,
        "api_mode": api_mode,
        "model_id": model_id,
    }


def _infer_api_mode(ai_config: AIConfig | None, base_url: str | None = None) -> str:
    raw = " ".join(
        [
            (ai_config.base_url if ai_config and ai_config.base_url else ""),
            (base_url or ""),
            (ai_config.model_id if ai_config and ai_config.model_id else ""),
            (ai_config.model if ai_config and ai_config.model else ""),
        ]
    ).lower()
    if "deepseek" in raw:
        return "deepseek"
    if "anthropic" in raw or "claude" in raw:
        return "anthropic"
    if "googleapis" in raw or "gemini" in raw:
        return "gemini"
    if "ollama" in raw:
        return "ollama"
    return "openai"


def _parse_route_from_text(text: str) -> list[RouteItem] | None:
    match = re.search(r"```route\s*([\s\S]*?)```", text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1).strip())
        return [RouteItem(**item) for item in data]
    except Exception:
        return None


def _normalize_messages(messages: Iterable[dict], api_mode: str) -> list[dict]:
    normalized: list[dict] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            continue
        if api_mode == "anthropic":
            if role not in {"user", "assistant"}:
                role = "user"
            normalized.append({"role": role, "content": content})
        elif api_mode == "gemini":
            gemini_role = "model" if role == "assistant" else "user"
            normalized.append({"role": gemini_role, "parts": [{"text": content}]})
        else:
            normalized.append({"role": role, "content": content})
    return normalized


def _build_payload(system_prompt: str, messages: list[dict], runtime: dict[str, str], stream: bool, user_id: str | None = None) -> tuple[str, dict, dict]:
    api_mode = runtime["api_mode"]
    base_url = runtime["base_url"].rstrip("/")
    api_key = runtime["api_key"]
    model_id = runtime["model_id"]

    if api_mode == "anthropic":
        url = f"{base_url}/v1/messages"
        payload = {
            "model": model_id,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": _normalize_messages(messages, api_mode),
            "stream": stream,
        }
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        return url, payload, headers

    if api_mode == "gemini":
        endpoint = ":streamGenerateContent?alt=sse" if stream else ":generateContent"
        url = f"{base_url}/models/{model_id}{endpoint}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": _normalize_messages(messages, api_mode),
            "generationConfig": {"maxOutputTokens": 2048},
        }
        headers = {"x-goog-api-key": api_key}
        return url, payload, headers

    if api_mode == "ollama":
        url = f"{base_url}/api/chat"
        payload = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, *_normalize_messages(messages, api_mode)],
            "stream": stream,
        }
        headers = {}
        return url, payload, headers

    if api_mode == "openai-responses":
        url = f"{base_url}/responses"
        payload = {
            "model": model_id,
            "input": [{"role": "system", "content": system_prompt}, *_normalize_messages(messages, api_mode)],
            "stream": stream,
        }
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        return url, payload, headers

    if api_mode == "deepseek":
        url = f"{base_url}/chat/completions"
        # 思考模式：reasoner 或 v4-pro 模型启用
        # 官方文档：https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
        # 思考 token 与输出 token 共享 max_tokens 配额（官方未明确说明，但实测如此）
        # 超长 prompt 下思考可能耗尽配额导致空响应，因此提升至 16384 并显式控制思考强度
        thinking_enabled = any(k in model_id.lower() for k in ("reasoner", "v4-pro"))
        max_tokens = 16384 if thinking_enabled else 4096
        payload = {
            "model": model_id,
            "messages": [{"role": "system", "content": system_prompt}, *_normalize_messages(messages, "openai")],
            "stream": stream,
            "max_tokens": max_tokens,
        }
        if thinking_enabled:
            payload["thinking"] = {"type": "enabled"}
            # reasoning_effort: low/medium→high, high(默认), max(复杂Agent场景)
            # high 适合路线规划场景，避免 max 消耗过多思考 token
            payload["reasoning_effort"] = "high"
        # DeepSeek user_id 隔离：内容安全、KVCache、调度隔离
        # https://api-docs.deepseek.com/zh-cn/quick_start/rate_limit
        if user_id:
            payload["user_id"] = user_id
        headers = {"Authorization": f"Bearer {api_key}"}
        return url, payload, headers

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model_id,
        "messages": [{"role": "system", "content": system_prompt}, *_normalize_messages(messages, api_mode)],
        "stream": stream,
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return url, payload, headers


def _extract_text_from_payload(api_mode: str, payload: dict) -> str:
    if api_mode == "anthropic":
        if payload.get("type") == "content_block_delta":
            return payload.get("delta", {}).get("text", "")
        if payload.get("type") == "message_delta":
            return payload.get("delta", {}).get("text", "")
        return ""

    if api_mode == "gemini":
        candidates = payload.get("candidates") or []
        if candidates:
            parts = candidates[0].get("content", {}).get("parts") or []
            if parts:
                return parts[0].get("text", "")
        return ""

    if api_mode == "ollama":
        return payload.get("message", {}).get("content", "")

    if api_mode == "openai-responses":
        if payload.get("type") in {"response.output_text.delta", "response.text.delta"}:
            return payload.get("delta", "")
        output = payload.get("output") or []
        if output:
            for item in output:
                content = item.get("content") or []
                for block in content:
                    if "text" in block:
                        return block.get("text", "")
        return ""

    if api_mode == "deepseek":
        choices = payload.get("choices") or []
        if choices:
            delta = choices[0].get("delta") or {}
            # 只取 content，跳过 reasoning_content（思考过程不展示给用户）
            return delta.get("content") or ""
        return ""

    choices = payload.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            return delta.get("content", "")
        message = choices[0].get("message") or {}
        return message.get("content", "") or ""
    return ""


async def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    detail = response.text
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            detail = parsed.get("error", {}).get("message") or parsed.get("message") or detail
    except Exception:
        pass
    raise HTTPException(status_code=response.status_code, detail=detail or "AI 请求失败")


async def _stream_provider_text(
    system_prompt: str,
    messages: list[dict],
    ai_config: AIConfig | None,
    request_id: str,
    user_id: str | None = None,
) -> AsyncIterator[str]:
    runtime = _resolve_runtime_config(ai_config)
    url, payload, headers = _build_payload(system_prompt, messages, runtime, stream=True, user_id=user_id)

    _log_ai_event(
        request_id,
        "request",
        {
            "provider": runtime["api_mode"],
            "source": runtime["source"],
            "url": url,
            "headers": _redact_headers(headers),
            "payload": payload,
        },
    )

    timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                await _raise_for_status(response)
                _log_ai_event(request_id, "response_status", {"status_code": response.status_code})
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    raw = line.strip()
                    if raw in {"[DONE]", "data: [DONE]"}:
                        break
                    if raw.startswith("event:") or raw.startswith(":"):
                        continue
                    if raw.startswith("data:"):
                        raw = raw[5:].strip()
                    try:
                        data = json.loads(raw)
                    except Exception:
                        continue
                    text = _extract_text_from_payload(runtime["api_mode"], data)
                    if text:
                        yield text
        except Exception as exc:
            _log_ai_event(request_id, "error", {"error": str(exc)})
            raise


async def _collect_response_text(system_prompt: str, messages: list[dict], ai_config: AIConfig | None, request_id: str, user_id: str | None = None) -> str:
    chunks: list[str] = []
    async for chunk in _stream_provider_text(system_prompt, messages, ai_config, request_id, user_id=user_id):
        chunks.append(chunk)
    return "".join(chunks)


async def stream_chat_response(
    planning: PlanningInfo,
    messages: list[dict],
    wait_times_json: str,
    completed_attractions: list[str],
    current_location: dict | None,
    strategy_snippets: list[str] | None = None,
    ai_config: AIConfig | None = None,
    user_id: str | None = None,
) -> AsyncIterator[dict]:
    request_id = uuid.uuid4().hex[:12]
    current_time = datetime.now(timezone.utc).astimezone().isoformat()
    system_prompt = build_system_prompt(
        planning=planning,
        wait_times_json=wait_times_json,
        current_time=current_time,
        completed_attractions=completed_attractions,
        current_location=current_location,
        strategy_snippets=strategy_snippets,
    )
    _log_ai_event(
        request_id,
        "context",
        {
            "mode": "stream_chat_response",
            "planning": planning.model_dump(),
            "wait_times_json": wait_times_json,
            "completed_attractions": completed_attractions,
            "current_location": current_location,
            "strategy_snippets": strategy_snippets,
            "messages": messages,
            "system_prompt": system_prompt,
        },
    )
    accumulated = ""

    async for text in _stream_provider_text(system_prompt, messages, ai_config, request_id, user_id=user_id):
        accumulated += text
        yield {"type": "text", "content": text}

    route = _parse_route_from_text(accumulated)
    _log_ai_event(
        request_id,
        "response",
        {
            "text": accumulated,
            "route": [r.model_dump() for r in route] if route else [],
        },
    )
    logger.info("[AI:%s] response_complete %s", request_id, _json_dumps({"text": accumulated, "route": [r.model_dump() for r in route] if route else []}))
    if route:
        yield {"type": "route_update", "route": [r.model_dump() for r in route]}

    yield {"type": "done"}


async def generate_initial_plan(
    planning: PlanningInfo,
    wait_times_json: str,
    strategy_snippets: list[str] | None = None,
    ai_config: AIConfig | None = None,
    user_id: str | None = None,
) -> tuple[str, list[RouteItem]]:
    request_id = uuid.uuid4().hex[:12]
    current_time = datetime.now(timezone.utc).astimezone().isoformat()
    system_prompt = build_system_prompt(
        planning=planning,
        wait_times_json=wait_times_json,
        current_time=current_time,
        completed_attractions=[],
        current_location=None,
        strategy_snippets=strategy_snippets,
    )
    _log_ai_event(
        request_id,
        "context",
        {
            "mode": "generate_initial_plan",
            "planning": planning.model_dump(),
            "wait_times_json": wait_times_json,
            "strategy_snippets": strategy_snippets,
            "system_prompt": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": f"请根据我的信息，为我生成一份完整的 {planning.visit_date} 游园路线规划。",
                }
            ],
        },
    )
    text = await _collect_response_text(
        system_prompt,
        [
            {
                "role": "user",
                "content": f"请根据我的信息，为我生成一份完整的 {planning.visit_date} 游园路线规划。",
            }
        ],
        ai_config,
        request_id,
        user_id=user_id,
    )
    route = _parse_route_from_text(text) or []
    _log_ai_event(
        request_id,
        "response",
        {
            "text": text,
            "route": [r.model_dump() for r in route],
        },
    )
    logger.info("[AI:%s] response_complete %s", request_id, _json_dumps({"text": text, "route": [r.model_dump() for r in route]}))
    return text, route


async def generate_initial_plan_stream(
    planning: PlanningInfo,
    wait_times_json: str,
    strategy_snippets: list[str] | None = None,
    ai_config: AIConfig | None = None,
    user_id: str | None = None,
):
    """流式版本：逐字 yield 路线规划内容，最后 yield route 解析结果。
    
    用法：
        async for chunk in generate_initial_plan_stream(...):
            # chunk = {"type":"text","content":"..."} 或 {"type":"route","route":[...]} 或 {"type":"error","message":"..."}
    """
    request_id = uuid.uuid4().hex[:12]
    current_time = datetime.now(timezone.utc).astimezone().isoformat()
    system_prompt = build_system_prompt(
        planning=planning,
        wait_times_json=wait_times_json,
        current_time=current_time,
        completed_attractions=[],
        current_location=None,
        strategy_snippets=strategy_snippets,
    )
    _log_ai_event(request_id, "context", {
        "mode": "generate_initial_plan_stream",
        "planning": planning.model_dump(),
        "system_prompt": system_prompt,
    })

    accumulated = ""
    try:
        async for chunk in _stream_provider_text(
            system_prompt,
            [{"role": "user", "content": f"请根据我的信息，为我生成一份完整的 {planning.visit_date} 游园路线规划。"}],
            ai_config,
            request_id,
            user_id=user_id,
        ):
            accumulated += chunk
            yield {"type": "text", "content": chunk}
    except Exception as e:
        _log_ai_event(request_id, "error", {"error": str(e)})
        yield {"type": "error", "message": str(e)}
        return

    route = _parse_route_from_text(accumulated) or []
    _log_ai_event(request_id, "response", {
        "text": accumulated,
        "route": [r.model_dump() for r in route],
    })
    yield {"type": "route", "route": [r.model_dump() for r in route]}
    yield {"type": "done"}
