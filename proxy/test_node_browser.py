import asyncio
from playwright.async_api import async_playwright

PROXY_URL = "http://127.0.0.1:8888"

async def main():
    async with async_playwright() as p:
        # disable-web-security bypasses Chrome's mixed-content block for local HTTP tests
        browser = await p.chromium.launch(
            headless=False,
            proxy={"server": PROXY_URL},
            args=["--proxy-bypass-list=<-loopback>", "--disable-web-security"]
        )
        page = await browser.new_page()

        # pipe browser console to terminal output
        page.on("console", lambda msg: print(f"[BROWSER] {msg.text}"))

        print("[-] Opening portal 4...")
        await page.goto("http://localhost:3000/portal4/login")

        print("[-] Submitting login form...")
        await page.fill('input[name="username"]', 'anna')
        await page.fill('input[name="password"]', 'VAULT_PASS')
        await page.click('button[type="submit"]')

        print("[-] Waiting for dashboard...")
        await page.wait_for_url("**/dashboard")
        
        # wait for the async fetch() to trigger
        await asyncio.sleep(5)
        
        print("[-] Done. Check mitmdump logs.")
        await browser.close()

asyncio.run(main())