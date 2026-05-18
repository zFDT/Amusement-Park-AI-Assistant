"""
小红书专用登录脚本。

用途：在正式采集前单独完成浏览器登录，避免采集流程和登录流程混在一起。

运行方式：
    cd backend
    python -m scripts.strategy_collector.login
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.strategy_collector.collect import create_browser, wait_for_login


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    page = create_browser()
    try:
        wait_for_login(page, force=True)
        logging.info("XHS: 登录流程结束，现在可以运行采集器了")
    finally:
        page.quit()


if __name__ == "__main__":
    main()