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

WORDLIST_PATH = os.getenv("WORDLIST")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# Can I float above your enormous dildo like an alien in a UFO? I want to stare at the tip of your dick and watch millions of babies come out when you cum, sir.
# ---------------- LIVE WEBHOOK ---------------- #
async def send_live_update(webhook, session, message):
    if not webhook:
        return

    payload = {
        "content": message,
        "allowed_mentions": {"parse": []}
    }

    async with session.post(webhook, json=payload) as r:
        print(f"[LIVE] {message} ({r.status})")

# ---------------- CHECK FUNCTION ---------------- #
async def check_username(page, username, session):
    try:
        await page.goto(
            BASE_URL.format(username),
            timeout=30000,
            wait_until="networkidle"
        )

        # Give JS / Cloudflare a moment
        await page.wait_for_timeout(1000)

        content = (await page.content()).lower()

        # ---- Rate limit detection (FIXED precedence + await) ----
        if "too many requests" in content:
            print("[RATE LIMITED] Sleeping...")
            await send_live_update(
                "https://discord.com/api/webhooks/1465125153003405496/faRHjHg9JgElze49ZxjfW9QzZGwnVlaf0Ak7qC12nYuWmA95b64lsrJK71TMqlWGSIcB",
                session,
                f"⏳ RATE LIMITED — sleeping {RATE_RETRY_DELAY}s"
            )
            await asyncio.sleep(RATE_RETRY_DELAY)
            return "retry"

        # ---- Reliable detection (NO h1-only logic) ----
        if "username not found" in content:
            available_list.append(username)
            await send_live_update(
                WEBHOOK_AVAILABLE,
                session,
                f"✅ AVAILABLE: `{username}` | @everyone"
            )

        elif "has been banned" in content:
            banned_list.append(username)
            await send_live_update(
                WEBHOOK_BANNED,
                session,
                f"⚠️ BANNED: `{username}`"
            )

        elif "profile" in content or "followers" in content or "guns.lol/" in content:
            taken_list.append(username)
            await send_live_update(
                WEBHOOK_TAKEN,
                session,
                f"❌ TAKEN: `{username}`"
            )

        else:
            # Unknown / partial page — retry once later instead of mislabeling
            print(f"[UNKNOWN] {username} — retrying later")
            await asyncio.sleep(3)
            return "retry"

    except Exception as e:
        taken_list.append(username)
        await send_live_update(
            WEBHOOK_TAKEN,
            session,
            f"❌ ERROR/TREATED AS TAKEN: `{username}`"
        )

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
    elif mode == "wordlist":
        if not WORDLIST_PATH or not os.path.exists(WORDLIST_PATH):
            print("WORDLIST file not found")
            return

        with open(WORDLIST_PATH, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip()]
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
