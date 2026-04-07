"""
app.py
------
Quart application entry point for the Cardano dashboard only.
Handles: startup, shutdown, and background refresh loop.
"""

import asyncio
import os

from quart import Quart, redirect, url_for
from jinja2 import FileSystemLoader, ChoiceLoader
from dotenv import load_dotenv
from loguru import logger

from logs.logger import setup_logger
from routes.cardano import cardano_bp
import data.cardano_data as cardano_data

# ── Env + logging ────────────────────────────────────────────────────────────

load_dotenv()
setup_logger()

# ── Config ───────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFRESH_INTERVAL = 60 * 60  # 1 hour

# ── App ──────────────────────────────────────────────────────────────────────

app = Quart(
    __name__,
    template_folder=os.path.join(BASE_DIR, "www", "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

app.jinja_env.loader = ChoiceLoader([
    FileSystemLoader(os.path.join(BASE_DIR, "www", "templates")),
    FileSystemLoader(os.path.join(BASE_DIR, "www", "views")),
])

app.register_blueprint(cardano_bp)

# ── Global state ─────────────────────────────────────────────────────────────

_background_task = None

# ── Simple root redirect ─────────────────────────────────────────────────────

@app.route("/")
async def index():
    return redirect(url_for("cardano.cardano_page"))

# ── Startup / Shutdown ───────────────────────────────────────────────────────

@app.before_serving
async def startup():
    global _background_task

    asyncio.get_event_loop().slow_callback_duration = 5.0
    logger.info("Starting Cardano dashboard...")

    _background_task = asyncio.create_task(cardano_refresh_loop())
    logger.info("Cardano background refresh loop started")
    logger.info("Server ready")

@app.after_serving
async def shutdown():
    global _background_task

    logger.info("Shutting down...")

    if _background_task and not _background_task.done():
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass

    logger.info("Clean shutdown complete")

# ── Background refresh loop ──────────────────────────────────────────────────

async def cardano_refresh_loop():
    """
    Refresh Cardano data on startup if stale/missing, then keep it fresh hourly.
    Uses cached disk data whenever it is still within TTL.
    """
    await asyncio.sleep(2)  # let startup settle

    while True:
        try:
            if cardano_data.should_refresh():
                api_key = os.getenv("BLOCKFROST_API_KEY", "").strip()

                if api_key:
                    logger.info("Cardano data stale or missing — refreshing from Blockfrost...")
                    ok = await cardano_data.refresh_cardano_data(api_key)
                    if ok:
                        logger.info("Cardano refresh complete")
                    else:
                        logger.warning("Cardano refresh failed — keeping existing cached data")
                else:
                    logger.warning(
                        "BLOCKFROST_API_KEY not configured — using cached Cardano data only"
                    )
            else:
                logger.info("Cardano data still fresh — skipping refresh")

        except asyncio.CancelledError:
            logger.info("Cardano refresh loop cancelled")
            break
        except Exception as e:
            logger.exception(f"Cardano refresh loop error: {e}")

        try:
            await asyncio.sleep(REFRESH_INTERVAL)
        except asyncio.CancelledError:
            logger.info("Cardano refresh sleep cancelled")
            break

# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=False)