import os
from playwright.sync_api import Page


class LoginHandler:
    def __init__(self):
        self.username = os.getenv("TUDELFT_USERNAME")
        self.password = os.getenv("TUDELFT_PASSWORD")
        if not self.username or not self.password:
            raise ValueError("TUDELFT_USERNAME and TUDELFT_PASSWORD must be set in .env")

    def login(self, page: Page) -> None:
        """Navigate to the site and authenticate. Raises RuntimeError on failure."""
        print("[Login] Navigating to booking page...")
        page.goto("https://x.tudelft.nl/bookings/activities?tags=28")

        # Step 1: click OIDC login button, wait for institution selection page
        page.click("button[data-test-id='oidc-login-button']")
        page.wait_for_load_state("domcontentloaded")

        # Step 2: submit the TU Delft form directly (bypasses click protection)
        page.wait_for_selector("div.wayf__idp[aria-describedby='idp__titleremaining1']")
        page.evaluate("""
            document.querySelector(
                'div.wayf__idp[aria-describedby="idp__titleremaining1"] form'
            ).submit()
        """)
        page.wait_for_load_state("domcontentloaded")

        # Step 3: wait for NetID SSO page, fill credentials, submit
        page.wait_for_selector("#username")
        page.fill("#username", self.username)
        page.fill("#password", self.password)
        page.click("#submit_button")

        # Confirm login succeeded by waiting for redirect back to booking page
        try:
            page.wait_for_url("**/bookings/activities**", timeout=15000)
            print("[Login] Authenticated successfully.")
        except Exception as e:
            raise RuntimeError(
                f"[Login] Authentication failed: {e}"
            ) from e
