import asyncio
import os
import random
import string
import aiohttp
from playwright.async_api import async_playwright

BASE_URL = "https://guns.lol/{}"

available_list = []
banned_list = []
taken_list = []

CHARS = string.ascii_lowercase + string.digits
RATE_LIMIT_TEXT = ["too many requests"]
RATE_RETRY_DELAY = 120

WEBHOOK_AVAILABLE = os.getenv("WEBHOOK_AVAILABLE")
WEBHOOK_TAKEN = os.getenv("WEBHOOK_TAKEN")
WEBHOOK_BANNED = os.getenv("WEBHOOK_BANNED")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ---------------- LIVE WEBHOOK ---------------- #
async def send_live_update(session, message):
    if not WEBHOOK_AVAILABLE:
        return

    payload = {
        "content": message,
        "allowed_mentions": {"parse": []}
    }

    async with session.post(WEBHOOK_AVAILABLE, json=payload) as r:
        print(f"[LIVE] {message} ({r.status})")

# ---------------- CHECK FUNCTION ---------------- #
async def check_username(page, username, session):
    try:
        response = await page.goto(
            BASE_URL.format(username),
            timeout=30000,
            wait_until="domcontentloaded"
        )

        content = (await page.content()).lower()

        if response and response.status == 429 or any(x in content for x in RATE_LIMIT_TEXT):
            print("[RATE LIMITED] Sleeping...")
            await asyncio.sleep(RATE_RETRY_DELAY)
            return "retry"

        h1 = page.locator("h1")
        text = (await h1.inner_text()).lower() if await h1.count() else ""

        if "username not found" in text:
            available_list.append(username)
            await send_live_update(session, f"✅ AVAILABLE: `{username}`")

        elif "has been banned" in text:
            banned_list.append(username)
            await send_live_update(session, f"⚠️ BANNED: `{username}`")

        else:
            taken_list.append(username)
            await send_live_update(session, f"❌ TAKEN: `{username}`")

    except Exception as e:
        taken_list.append(username)
        await send_live_update(session, f"❌ ERROR/TOKEN: `{username}`")

    return "ok"

# ---------------- SUMMARY WEBHOOK ---------------- #
async def send_summary(url, title, names, color):
    if not url:
        return

    if not names:
        names = ["None"]

    payload = {
        "embeds": [{
            "title": title,
            "description": "```\n" + "\n".join(names[:50]) + "\n```",
            "color": color
        }],
        "allowed_mentions": {"parse": []}
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as r:
            print(f"{title} summary webhook: {r.status}")

# ---------------- MAIN ---------------- #
async def main():
    mode = os.getenv("MODE", "2c")
    amount = int(os.getenv("AMOUNT", "50"))

    if mode == "2c":
        usernames = ["".join(random.choice(CHARS) for _ in range(2)) for _ in range(amount)]
    elif mode == "3c":
        usernames = ["".join(random.choice(CHARS) for _ in range(3)) for _ in range(amount)]
    else:
        print("Invalid MODE")
        return

    async with aiohttp.ClientSession() as session:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            page = await browser.new_page(user_agent=USER_AGENT)

            for user in usernames:
                await check_username(page, user, session)
                await asyncio.sleep(1)  # small delay to avoid Discord spam limits

            await browser.close()

    # Final summaries
    await send_summary(WEBHOOK_AVAILABLE, "✅ Available Names", available_list, 0x57F287)
    await send_summary(WEBHOOK_TAKEN, "❌ Taken Names", taken_list, 0xED4245)
    await send_summary(WEBHOOK_BANNED, "⚠️ Banned Names", banned_list, 0xFEE75C)

    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
