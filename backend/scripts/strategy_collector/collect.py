"""
香港/上海迪士尼乐园攻略采集器
基于 DrissionPage（Chrome 自动化），采集小红书图文攻略并入库。

核心改进（参考 xiaohongshu-mcp 项目）：
- 使用 window.__INITIAL_STATE__ 提取数据，比 DOM 选择器更稳定可靠
- 搜索结果直接从 JS 状态对象读取，包含 xsecToken
- 详情页通过 noteDetailMap 获取完整图片列表和互动数据

运行方式：
    python -m scripts.strategy_collector.collect --park hongkong_disney
    python -m scripts.strategy_collector.collect --park hongkong_disney --limit 30
    python -m scripts.strategy_collector.collect --park hongkong_disney --no-distill

依赖：
    pip install DrissionPage  （需要 Chrome 浏览器）
    数据库需已初始化（python -m scripts.init_db）
"""

import asyncio
import hashlib
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.core.logging import configure_logging
from app.core.database import AsyncSessionLocal
from app.models.park import Strategy
from scripts.strategy_collector.distill import distill_batch, resolve_distill_ai_config

logger = logging.getLogger(__name__)

try:
    from DrissionPage import ChromiumPage, ChromiumOptions
    DRISSION_AVAILABLE = True
except ImportError:
    DRISSION_AVAILABLE = False
    logger.warning("DrissionPage not installed. Run: pip install DrissionPage")

BROWSER_DATA_DIR = Path(__file__).parent.parent.parent / "browser_data" / "xhs"
XHS_PORT = 9521

PARK_KEYWORDS = {
    "hongkong_disney": [
        "香港迪士尼攻略",
        "香港迪士尼游玩路线",
        "香港迪士尼必玩",
        "香港迪士尼一日游",
        "香港迪士尼排队技巧",
    ],
    "shanghai_disney": [
        "上海迪士尼攻略",
        "上海迪士尼游玩路线",
        "上海迪士尼必玩",
        "上海迪士尼一日游",
    ],
}

_ATTRACTIONS = {
    "hongkong_disney": [
        "迷离庄园", "大灰熊山谷", "超空间山峰", "钢铁侠", "蚁侠",
        "小小世界", "小熊维尼", "冰雪奇缘", "达菲", "灰姑娘",
        "森林河流", "泰山树屋", "RC飞车", "绿军人", "飞象",
        "米奇幻想曲", "幻想花园", "童话森林",
    ],
    "shanghai_disney": [
        "创极速光轮", "翱翔", "雷鸣山漂流", "加勒比海盗",
        "七个小矮人", "小飞侠", "疯狂动物城", "巴斯光年",
    ],
}

# 详情页之间的间隔，避免触发反爬
_DETAIL_INTERVAL = 1.5


def create_browser() -> "ChromiumPage":
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    co = ChromiumOptions()
    co.set_user_data_path(str(BROWSER_DATA_DIR))
    co.set_local_port(XHS_PORT)
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--no-first-run")
    return ChromiumPage(co)


def wait_for_login(page: "ChromiumPage", force: bool = False) -> None:
    page.get("https://www.xiaohongshu.com")
    time.sleep(3)
    avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
    if avatar and not force:
        logger.info("XHS: 已登录（复用上次 session）")
        return

    if force:
        logger.info("XHS: 已进入专门登录模式，请在浏览器中完成登录")
    else:
        logger.info("XHS: 需要登录，请在浏览器中完成登录")

    input(">>> 小红书登录完成后，按回车继续...")

    # 回车后再做一次轻量校验，便于确认登录态是否真的生效
    avatar = page.ele("css:.user-avatar", timeout=3) or page.ele("css:[class*='avatar']", timeout=2)
    if avatar:
        logger.info("XHS: 已确认登录态")
    else:
        logger.warning("XHS: 未检测到明确登录态，但将继续尝试采集（如仍无结果，可重新登录）")


def _parse_count(text: str) -> int:
    text = str(text).strip()
    if not text:
        return 0
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(text.replace("+", "").replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _extract_mentioned_attractions(content: str, park_id: str) -> list[str]:
    keywords = _ATTRACTIONS.get(park_id, [])
    return [kw for kw in keywords if kw in content]


def _wait_initial_state(page: "ChromiumPage", timeout: int = 10) -> bool:
    """等待 window.__INITIAL_STATE__ 加载完成"""
    for _ in range(timeout * 2):
        try:
            ready = page.run_js("return typeof window.__INITIAL_STATE__ !== 'undefined'")
            if ready:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _run_js(page: "ChromiumPage", js: str):
    """执行 JS，返回解析后的 Python 对象；失败返回 None"""
    try:
        raw = page.run_js(js)
        if raw is None or raw == "null" or raw == "undefined":
            return None
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.debug(f"JS 执行失败: {e}")
        return None


def _get_detail(page: "ChromiumPage", feed_id: str, xsec_token: str) -> tuple[str, list[str], int, int]:
    """
    导航到笔记详情页，从 __INITIAL_STATE__.note.noteDetailMap 提取：
    - content: 正文（desc 字段）
    - images: 图片 URL 列表（imageList[].urlDefault）
    - collects: 收藏数
    - comments: 评论数

    参考 xiaohongshu-mcp feed_detail.go 的 URL 格式和数据提取方式。
    """
    content = ""
    images: list[str] = []
    collects = 0
    comments = 0

    try:
        detail_url = (
            f"https://www.xiaohongshu.com/explore/{feed_id}"
            f"?xsec_token={xsec_token}&xsec_source=pc_feed"
        )
        page.get(detail_url)
        time.sleep(2)

        if not _wait_initial_state(page):
            logger.warning(f"详情页 __INITIAL_STATE__ 未加载: {feed_id}")
            return content, images, collects, comments

        # 安全地访问嵌套属性，避免 JS 注入（feed_id 来自 XHS 自身数据）
        safe_id = feed_id.replace("'", "").replace('"', "")
        detail = _run_js(page, f"""
            return JSON.stringify((() => {{
                const state = window.__INITIAL_STATE__;
                const noteMap = state?.note?.noteDetailMap;
                if (!noteMap) return null;
                const entry = noteMap['{safe_id}'];
                return entry?.note || null;
            }})())
        """)

        if not detail:
            return content, images, collects, comments

        content = detail.get("desc", "")

        # 提取所有图片（urlDefault 优先，fallback urlPre）
        for img in detail.get("imageList", []):
            url = img.get("urlDefault") or img.get("urlPre", "")
            if url:
                images.append(url)

        interact = detail.get("interactInfo", {})
        collects = _parse_count(interact.get("collectedCount", "0"))
        comments = _parse_count(interact.get("commentCount", "0"))

    except Exception as e:
        logger.debug(f"获取详情出错 {feed_id}: {e}")

    return content, images, collects, comments


def search_xhs(page: "ChromiumPage", keyword: str, limit: int = 20) -> list[dict]:
    """
    搜索小红书，从 window.__INITIAL_STATE__.search.feeds 提取结果。
    参考 xiaohongshu-mcp search.go 的数据提取逻辑。
    """
    results = []
    try:
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_explore_feed"
        page.get(search_url)
        time.sleep(3)

        if not _wait_initial_state(page):
            logger.warning(f"搜索页 __INITIAL_STATE__ 未加载，关键词：{keyword}")
            return results

        # 兼容 .value 和 ._value 两种属性名（参考 xiaohongshu-mcp feeds.go）
        feeds = _run_js(page, """
            return JSON.stringify((() => {
                const state = window.__INITIAL_STATE__;
                if (!state?.search?.feeds) return null;
                const f = state.search.feeds;
                return f.value !== undefined ? f.value : f._value;
            })())
        """)

        if not feeds:
            logger.warning(f"未找到搜索结果，关键词：{keyword}")
            return results

        logger.info(f"找到 {len(feeds)} 条笔记，关键词：{keyword}")

        for feed in feeds[:limit]:
            try:
                feed_id = feed.get("id", "")
                xsec_token = feed.get("xsecToken", "")
                if not feed_id:
                    continue

                note_card = feed.get("noteCard", {})
                title = note_card.get("displayTitle", "")
                user = note_card.get("user", {})
                author = user.get("nickname", "") or user.get("nickName", "")
                interact = note_card.get("interactInfo", {})
                likes = _parse_count(interact.get("likedCount", "0"))
                source_url = f"https://www.xiaohongshu.com/explore/{feed_id}"

                content, images, collects, comments = _get_detail(page, feed_id, xsec_token)
                time.sleep(_DETAIL_INTERVAL)

                results.append({
                    "id": feed_id,
                    "title": title,
                    "content": content or title,
                    "author": author,
                    "likes": likes,
                    "collects": collects,
                    "comments": comments,
                    "source_url": source_url,
                    "images": images,
                })
            except Exception as e:
                logger.debug(f"解析 feed 出错: {e}")
                continue

    except Exception as e:
        logger.error(f"搜索出错: {e}")

    return results


async def save_strategies(
    park_id: str,
    items: list[dict],
    existing_strategy_ids: set[str] | None = None,
) -> list[dict]:
    """
    将采集到的攻略保存到数据库，跳过已存在的。
    返回新入库的 item 列表（供后续 AI 提炼使用）。
    """
    new_items = []
    known_ids = set(existing_strategy_ids or set())
    async with AsyncSessionLocal() as session:
        for item in items:
            source_url = item.get("source_url", "")
            if not source_url:
                continue

            strategy_id = hashlib.md5(source_url.encode()).hexdigest()
            item["id"] = strategy_id

            if strategy_id in known_ids:
                continue

            content = item.get("content", "")
            strategy = Strategy(
                id=strategy_id,
                park_id=park_id,
                platform="xhs",
                source_url=source_url,
                title=item.get("title", ""),
                content=content,
                author=item.get("author", ""),
                likes=item.get("likes", 0),
                collects=item.get("collects", 0),
                comments=item.get("comments", 0),
                tags=[],
                mentioned_attractions=_extract_mentioned_attractions(content, park_id),
                image_urls=item.get("images", []),
            )
            session.add(strategy)
            new_items.append(item)
            known_ids.add(strategy_id)

        await session.commit()
    return new_items


async def load_existing_strategy_ids(park_id: str, platform: str = "xhs") -> set[str]:
    """加载指定乐园下已入库攻略的 ID，用于采集前去重。"""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Strategy.id).where(Strategy.park_id == park_id, Strategy.platform == platform)
        )
        return set(result.scalars().all())


async def apply_ai_summaries(new_items: list[dict]) -> None:
    """对新入库的攻略批量调用 AI 提炼，将摘要写回数据库"""
    ai_config = resolve_distill_ai_config()
    if not ai_config:
        logger.warning("未配置可用的 AI 提炼配置，跳过 AI 提炼步骤")
        return

    logger.info(
        "开始 AI 提炼，共 %d 条攻略…（api_mode=%s, code=%s）",
        len(new_items),
        ai_config["api_mode"],
        ai_config.get("code", ""),
    )
    results = await distill_batch(
        new_items,
        api_key=ai_config["api_key"],
        base_url=ai_config.get("base_url") or None,
        api_mode=ai_config.get("api_mode", "anthropic"),
    )

    if not results:
        logger.info("AI 提炼无结果")
        return

    async with AsyncSessionLocal() as session:
        for strategy_id, data in results.items():
            strategy = await session.get(Strategy, strategy_id)
            if strategy:
                if data.get("ai_summary"):
                    strategy.ai_summary = data["ai_summary"]
                if data.get("structured"):
                    strategy.structured_summary = data["structured"]
        await session.commit()

    logger.info(f"AI 提炼完成，成功提炼 {len(results)} 条")


async def collect(
    park_id: str = "hongkong_disney",
    limit_per_keyword: int = 20,
    enable_distill: bool = True,
    force_login: bool = False,
    login_only: bool = False,
    offset: int = 0,
    max_total: int | None = None,
):
    if not DRISSION_AVAILABLE:
        logger.error("DrissionPage 未安装，无法运行采集器")
        return

    keywords = PARK_KEYWORDS.get(park_id, [])
    if not keywords:
        logger.error(f"未找到乐园 {park_id} 的关键词配置")
        return

    logger.info(f"开始采集 {park_id} 攻略，关键词：{keywords}")
    page = create_browser()

    try:
        wait_for_login(page, force=force_login or login_only)

        if login_only:
            logger.info("XHS: 登录模式完成，按需退出采集器")
            return

        all_items: list[dict] = []
        seen_urls: set[str] = set()
        existing_strategy_ids = await load_existing_strategy_ids(park_id)
        skipped_existing = 0
        skipped_duplicate = 0
        skipped_offset = 0
        skipped_max_total = 0
        item_counter = 0

        for keyword in keywords:
            if max_total is not None and len(all_items) >= max_total:
                logger.info(f"已达到最大采集数 {max_total}，停止采集")
                break

            logger.info(f"搜索关键词：{keyword}")
            items = search_xhs(page, keyword, limit=limit_per_keyword)

            for item in items:
                item_counter += 1

                if item_counter <= offset:
                    skipped_offset += 1
                    continue

                if max_total is not None and len(all_items) >= max_total:
                    skipped_max_total += 1
                    continue

                url = item.get("source_url", "")
                if not url:
                    continue

                if url in seen_urls:
                    skipped_duplicate += 1
                    continue

                strategy_id = hashlib.md5(url.encode()).hexdigest()
                item["id"] = strategy_id

                if strategy_id in existing_strategy_ids:
                    skipped_existing += 1
                    continue

                seen_urls.add(url)
                all_items.append(item)

            time.sleep(2)

        logger.info(
            "共采集 %d 条去重后的攻略（本轮内重复 %d 条，数据库已存在 %d 条，offset 跳过 %d 条，max_total 截断 %d 条）",
            len(all_items),
            skipped_duplicate,
            skipped_existing,
            skipped_offset,
            skipped_max_total,
        )

        new_items = await save_strategies(park_id, all_items, existing_strategy_ids=existing_strategy_ids)
        logger.info(f"新入库 {len(new_items)} 条攻略（跳过已存在的）")

        if enable_distill and new_items:
            await apply_ai_summaries(new_items)

    finally:
        page.quit()


if __name__ == "__main__":
    import argparse
    configure_logging()
    logging.getLogger(__name__).setLevel(logging.INFO)

    parser = argparse.ArgumentParser(description="迪士尼攻略采集器")
    parser.add_argument("--park", default="hongkong_disney", choices=list(PARK_KEYWORDS.keys()))
    parser.add_argument("--limit", type=int, default=20, help="每个关键词采集数量")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 条搜索结果（用于续采或避免重复采集热门笔记）")
    parser.add_argument("--max-total", type=int, default=None, help="限制本次采集的总条数上限（不含数据库已有）")
    parser.add_argument("--no-distill", action="store_true", help="跳过 AI 提炼步骤")
    parser.add_argument("--force-login", action="store_true", help="忽略已保存登录态，强制重新登录")
    parser.add_argument("--login-only", action="store_true", help="仅执行登录，不开始采集")
    args = parser.parse_args()

    asyncio.run(collect(
        park_id=args.park,
        limit_per_keyword=args.limit,
        enable_distill=not args.no_distill,
        force_login=args.force_login,
        login_only=args.login_only,
        offset=args.offset,
        max_total=args.max_total,
    ))
