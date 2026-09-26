from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://x.tudelft.nl/bookings/activities?tags=28')
    input('Browser open — press Enter when done inspecting...')
    browser.close()