# TU Delft Gym Slot Booker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI script that headlessly books a TU Delft gym fitness timeslot for today at a user-specified time, retrying until the slot becomes available.

**Architecture:** Three modules — `booker.py` (CLI entry point), `login_handler.py` (Playwright login), `booking_handler.py` (slot search + retry loop). Playwright controls headless Chromium; credentials come from `.env`.

**Tech Stack:** Python 3.10+, Playwright (sync API), python-dotenv

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `.gitignore` | Create | Exclude `.env` and cache files from git |
| `requirements.txt` | Create | Pin dependencies |
| `.env.example` | Create | Credential template (`.env` is gitignored) |
| `login_handler.py` | Create | `LoginHandler` — auth via Playwright |
| `booking_handler.py` | Create | `BookingHandler` — find slot, book, retry |
| `booker.py` | Create | CLI entry point — wires everything together |

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
```

- [ ] **Step 2: Create `requirements.txt`**

```
playwright==1.50.0
python-dotenv==1.0.1
```

- [ ] **Step 3: Create `.env.example`**

```
TUDELFT_USERNAME=your_netid
TUDELFT_PASSWORD=your_password
RETRY_INTERVAL_SECONDS=30
MAX_RETRIES=0
```

- [ ] **Step 4: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected: Playwright and chromium download without errors.

- [ ] **Step 5: Copy `.env.example` to `.env` and fill in real credentials**

```bash
cp .env.example .env
# Edit .env with real NetID and password
```

- [ ] **Step 6: Commit**

```bash
git init
git add .gitignore requirements.txt .env.example
git commit -m "chore: project setup with dependencies"
```

---

## Task 2: Inspect Login & Booking Page

**Purpose:** Before writing automation code, identify the exact selectors for login fields and booking timeslots. This is a discovery step — run a temporary script interactively.

**Files:**
- Create (temporary, delete after): `inspect.py`

- [ ] **Step 1: Create `inspect.py` to open the booking page non-headlessly**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://x.tudelft.nl/bookings/activities?tags=28")
    input("Browser open — inspect login and timeslot elements, then press Enter to close...")
    browser.close()
```

- [ ] **Step 2: Run `inspect.py` and note down**

```bash
python inspect.py
```

In the browser DevTools (F12), identify and note:
- The login button/link selector (e.g., `a[href*="login"]` or `button:has-text("Login")`)
- The SSO username field selector (e.g., `input[name="username"]` or `input[type="email"]`)
- The SSO password field selector (e.g., `input[name="password"]` or `input[type="password"]`)
- The submit button selector (e.g., `button[type="submit"]`)
- A post-login element that confirms auth (e.g., user avatar, profile link)
- The timeslot card/row structure — what HTML element wraps each slot
- How today's date is displayed on the page
- The time label element inside each slot
- The "Book" button selector on each slot
- Any confirmation dialog/button after clicking Book

> **Note:** TU Delft uses SSO (Microsoft or their own identity provider). If 2FA is required, this script cannot handle it automatically — confirm with the user that their account does not require 2FA, or that they can disable it.

- [ ] **Step 3: Delete `inspect.py`**

```bash
rm inspect.py
```

---

## Task 3: LoginHandler

**Files:**
- Create: `login_handler.py`

- [ ] **Step 1: Create `login_handler.py`**

Replace selector strings with what you found in Task 2.

```python
import os
from dotenv import load_dotenv
from playwright.sync_api import Page

load_dotenv()


class LoginHandler:
    def __init__(self):
        self.username = os.getenv("TUDELFT_USERNAME")
        self.password = os.getenv("TUDELFT_PASSWORD")
        if not self.username or not self.password:
            raise ValueError("TUDELFT_USERNAME and TUDELFT_PASSWORD must be set in .env")

    def login(self, page: Page) -> None:
        """Navigate to the site and authenticate. Raises on failure."""
        print("[Login] Navigating to booking page...")
        page.goto("https://x.tudelft.nl/bookings/activities?tags=28")

        # Click the login link/button (update selector from Task 2)
        page.click("SELECTOR_FOR_LOGIN_BUTTON")

        # Fill SSO credentials (update selectors from Task 2)
        page.fill("SELECTOR_FOR_USERNAME_FIELD", self.username)
        page.fill("SELECTOR_FOR_PASSWORD_FIELD", self.password)
        page.click("SELECTOR_FOR_SUBMIT_BUTTON")

        # Wait for a post-login element to confirm success (update selector from Task 2)
        try:
            page.wait_for_selector("SELECTOR_FOR_POST_LOGIN_ELEMENT", timeout=15000)
            print("[Login] Authenticated successfully.")
        except Exception:
            raise RuntimeError(
                "[Login] Authentication failed — check credentials or page selectors."
            )
```

- [ ] **Step 2: Manually verify login works**

Create a quick throwaway test script (don't commit it):

```python
from playwright.sync_api import sync_playwright
from login_handler import LoginHandler

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # non-headless to watch
    page = browser.new_page()
    LoginHandler().login(page)
    input("Logged in? Check the browser, then press Enter...")
    browser.close()
```

Run it: `python test_login.py`
Expected: Browser opens, logs in, lands on authenticated page.
Delete `test_login.py` after verification.

- [ ] **Step 3: Commit**

```bash
git add login_handler.py
git commit -m "feat: add LoginHandler for TU Delft SSO authentication"
```

---

## Task 4: BookingHandler

**Files:**
- Create: `booking_handler.py`

- [ ] **Step 1: Create `booking_handler.py`**

Replace selector strings with what you found in Task 2.

```python
import os
import time
from datetime import date
from dotenv import load_dotenv
from playwright.sync_api import Page

load_dotenv()


class BookingHandler:
    def __init__(self):
        self.retry_interval = int(os.getenv("RETRY_INTERVAL_SECONDS", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "0"))

    def book(self, page: Page, target_time: str) -> None:
        """
        Find today's timeslot at target_time and book it.
        Retries until successful or max_retries exceeded.
        target_time: "HH:MM" string, e.g. "18:00"
        """
        today = date.today().strftime("%Y-%m-%d")  # adjust format to match site
        attempt = 0

        while True:
            attempt += 1
            print(f"[{self._now()}] Attempt {attempt}: looking for slot at {target_time} on {today}...")

            try:
                page.goto("https://x.tudelft.nl/bookings/activities?tags=28")
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                print(f"[{self._now()}] Page load failed: {e}")
                self._maybe_retry(attempt)
                continue

            slot = self._find_slot(page, target_time, today)

            if slot is None:
                print(f"[{self._now()}] Slot not found. Retrying in {self.retry_interval}s...")
                self._maybe_retry(attempt)
                continue

            if self._is_already_booked(slot):
                print(f"[{self._now()}] Slot at {target_time} is already booked. Done.")
                return

            booked = self._attempt_booking(slot, page)
            if booked:
                print(f"[{self._now()}] Successfully booked {target_time} slot!")
                return

            print(f"[{self._now()}] Booking click failed (race condition?). Retrying in {self.retry_interval}s...")
            self._maybe_retry(attempt)

    def _find_slot(self, page: Page, target_time: str, today: str):
        """
        Return the slot element matching target_time for today, or None.
        Update selectors based on Task 2 inspection.
        """
        # Example: find all slot cards on the page
        # slots = page.locator("SELECTOR_FOR_SLOT_CARD").all()
        # For each slot, check date and time labels
        # Return the matching slot locator or None

        slots = page.locator("SELECTOR_FOR_SLOT_CARD").all()
        for slot in slots:
            slot_date = slot.locator("SELECTOR_FOR_DATE_LABEL").inner_text().strip()
            slot_time = slot.locator("SELECTOR_FOR_TIME_LABEL").inner_text().strip()
            if today in slot_date and target_time in slot_time:
                return slot
        return None

    def _is_already_booked(self, slot) -> bool:
        """Return True if the slot shows an 'already booked' state."""
        # Update selector to match "Cancel" button or booked indicator from Task 2
        return slot.locator("SELECTOR_FOR_CANCEL_OR_BOOKED_INDICATOR").count() > 0

    def _attempt_booking(self, slot, page: Page) -> bool:
        """Click Book and confirm. Return True on success."""
        try:
            slot.locator("SELECTOR_FOR_BOOK_BUTTON").click()
            # If there's a confirmation dialog, click confirm (update selector)
            page.wait_for_selector("SELECTOR_FOR_CONFIRM_BUTTON", timeout=5000)
            page.click("SELECTOR_FOR_CONFIRM_BUTTON")
            # Wait for success indicator (update selector)
            page.wait_for_selector("SELECTOR_FOR_SUCCESS_INDICATOR", timeout=10000)
            return True
        except Exception as e:
            print(f"[{self._now()}] Booking attempt error: {e}")
            return False

    def _maybe_retry(self, attempt: int) -> None:
        """Sleep before retry, or raise if max_retries exceeded."""
        if self.max_retries > 0 and attempt >= self.max_retries:
            raise RuntimeError(
                f"Max retries ({self.max_retries}) exceeded. Could not book slot."
            )
        time.sleep(self.retry_interval)

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
```

- [ ] **Step 2: Update all SELECTOR_* placeholders**

Go through `booking_handler.py` and replace every `SELECTOR_FOR_*` string with the real CSS/text selectors you found in Task 2. There should be no `SELECTOR_FOR_` strings remaining.

- [ ] **Step 3: Commit**

```bash
git add booking_handler.py
git commit -m "feat: add BookingHandler with retry loop"
```

---

## Task 5: CLI Entry Point

**Files:**
- Create: `booker.py`

- [ ] **Step 1: Create `booker.py`**

```python
import sys
from playwright.sync_api import sync_playwright
from login_handler import LoginHandler
from booking_handler import BookingHandler


def main():
    if len(sys.argv) != 2:
        print("Usage: python booker.py HH:MM")
        print("Example: python booker.py 18:00")
        sys.exit(1)

    target_time = sys.argv[1]

    # Basic format check
    parts = target_time.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        print(f"Invalid time format: {target_time!r}. Expected HH:MM (e.g. 18:00)")
        sys.exit(1)

    print(f"[Booker] Starting — will book {target_time} slot for today.")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            LoginHandler().login(page)
            BookingHandler().book(page, target_time)

            browser.close()
    except KeyboardInterrupt:
        print("\n[Booker] Stopped by user.")
        sys.exit(0)
    except RuntimeError as e:
        print(f"\n[Booker] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run end-to-end (non-headless first)**

Temporarily change `headless=True` to `headless=False` in `booker.py`, then run:

```bash
python booker.py 18:00
```

Watch the browser. Verify:
- It logs in correctly
- It navigates to the booking page
- It finds (or doesn't find) the 18:00 slot and either books it or retries

After verification, set `headless=True` again.

- [ ] **Step 3: Commit**

```bash
git add booker.py
git commit -m "feat: add CLI entry point for gym slot booker"
```

---

## Task 6: Final Verification

- [ ] **Step 1: Run headless end-to-end**

```bash
python booker.py 18:00
```

Expected outputs depending on state:
- Slot found and booked: `[HH:MM:SS] Successfully booked 18:00 slot!`
- Slot not yet available: `[HH:MM:SS] Slot not found. Retrying in 30s...` (repeating)
- Already booked: `[HH:MM:SS] Slot at 18:00 is already booked. Done.`

- [ ] **Step 2: Test Ctrl+C graceful exit**

While it's retrying, press Ctrl+C.
Expected: `[Booker] Stopped by user.` and clean exit.

- [ ] **Step 3: Test bad credentials**

Temporarily set wrong password in `.env`, run, restore.
Expected: `[Login] Authentication failed — check credentials or page selectors.` and exit code 1.

- [ ] **Step 4: Final commit**

```bash
git add booker.py login_handler.py booking_handler.py requirements.txt .env.example .gitignore
git commit -m "feat: complete TU Delft gym slot booker"
```
