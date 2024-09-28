import asyncio
import logging
import sys

from config import get_config
from handle import serve
from notify import init_notify


def setup_logging(debug=False):
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True
    logging.getLogger("httpcore.http11").disabled = True
    logging.getLogger("httpcore.http2").disabled = True
    logging.getLogger("httpcore.connection").disabled = True


async def main():
    logger = logging.getLogger("eqqr.main")
    logger.info("Starting EQQR")
    await serve()


if __name__ == "__main__":
    config_file = "config.yaml"
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    config = get_config(config_file)
    setup_logging(debug=config["debug"])
    init_notify()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
