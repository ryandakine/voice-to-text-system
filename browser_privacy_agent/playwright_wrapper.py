"""Playwright automation utilities with stealth configuration."""

from __future__ import annotations

import asyncio
import random
import re
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Error, Page, async_playwright

from .config import CONFIG
from .logger import setup_logger

LOGGER = setup_logger("playwright")


TELEMETRY_PATTERN = re.compile("|".join(CONFIG.browser.request_intercept_patterns), re.IGNORECASE)


@asynccontextmanager
async def browser_context() -> AsyncIterator[BrowserContext]:
    """Provision a Chromium context with stealth optimizations."""
    playwright = await async_playwright().start()
    user_agent = random.choice(CONFIG.browser.user_agents)
    LOGGER.info("Launching headless Chromium with UA: %s", user_agent)
    browser: Browser = await playwright.chromium.launch(
        headless=CONFIG.browser.headless,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    context = await browser.new_context(
        user_agent=user_agent,
        viewport={"width": 1280 + random.randint(-40, 40), "height": 720 + random.randint(-20, 20)},
    )
    if CONFIG.browser.stealth:
        await _apply_stealth(context)
    try:
        yield context
    finally:
        await context.close()
        await browser.close()
        await playwright.stop()


async def _apply_stealth(context: BrowserContext) -> None:
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )


async def run_task(url: str, actions: Optional[Dict[str, str]] = None) -> str:
    """Navigate to a URL with stealth waits and return page content."""
    actions = actions or {}
    attempt = 0
    while attempt < CONFIG.browser.max_retries:
        attempt += 1
        try:
            async with browser_context() as context:
                page = await context.new_page()
                await page.route("**/*", _block_telemetry)
                await page.goto(url, wait_until="domcontentloaded", timeout=CONFIG.browser.navigation_timeout)
                await _slow_human_like_scroll(page)
                for selector, value in actions.items():
                    await _interact(page, selector, value)
                content = await page.content()
                return content
        except Error as exc:
            LOGGER.warning("Playwright attempt %s failed: %s", attempt, exc)
            await asyncio.sleep(random.uniform(3, 7))
    raise RuntimeError(f"Failed to complete Playwright task for {url}")


async def _block_telemetry(route, request) -> None:
    if TELEMETRY_PATTERN.search(request.url):
        await route.abort()
    else:
        await route.continue_()


async def _slow_human_like_scroll(page: Page) -> None:
    for _ in range(random.randint(3, 6)):
        await page.mouse.wheel(0, random.randint(200, 500))
        await asyncio.sleep(random.uniform(1.0, 2.5))


async def _interact(page: Page, selector: str, value: str) -> None:
    try:
        await page.wait_for_selector(selector, timeout=5000)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        if value == "click":
            await page.click(selector, delay=random.randint(50, 120))
        else:
            await page.fill(selector, value)
            await asyncio.sleep(random.uniform(0.3, 0.8))
    except Error as exc:
        LOGGER.error("Interaction failed for %s: %s", selector, exc)
        raise
