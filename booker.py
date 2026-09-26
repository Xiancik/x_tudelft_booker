import sys
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from login_handler import LoginHandler
from booking_handler import BookingHandler


def main():
    load_dotenv()

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    headless = "--visible" not in flags

    if len(args) != 1:
        print("Usage: python booker.py HH:MM [--visible]")
        print("Example: python booker.py 18:00")
        print("         python booker.py 18:00 --visible")
        sys.exit(1)

    target_time = args[0]

    parts = target_time.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        print(f"Invalid time format: {target_time!r}. Expected HH:MM (e.g. 18:00)")
        sys.exit(1)

    print(f"[Booker] Starting — will book {target_time} slot for today{' (visible)' if not headless else ''}.")

    try:
        with sync_playwright() as p:
            with p.chromium.launch(headless=headless) as browser:
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                LoginHandler().login(page)
                BookingHandler().book(page, target_time)
    except KeyboardInterrupt:
        print("\n[Booker] Stopped by user.")
        sys.exit(0)
    except (RuntimeError, ValueError) as e:
        print(f"\n[Booker] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
