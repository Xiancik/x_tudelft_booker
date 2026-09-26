import os
import time
from datetime import datetime
from playwright.sync_api import Page


class BookingHandler:
    BOOKING_URL = "https://x.tudelft.nl/bookings/activities?tags=28"

    def __init__(self):
        self.retry_interval = int(os.getenv("RETRY_INTERVAL_SECONDS", "30"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "0"))

    def book(self, page: Page, target_time: str) -> None:
        """
        Find today's slot at target_time and book it.
        Retries on failure. target_time e.g. "18:00".
        """
        attempt = 0
        while True:
            attempt += 1
            print(f"[{self._now()}] Attempt {attempt}: looking for {target_time} slot...")

            try:
                page.goto(self.BOOKING_URL)
                # Wait for Angular to render the actual slot items, not just the container
                page.wait_for_selector(
                    "activities-list-item[data-test-id='activities-list-item']",
                    timeout=15000
                )
            except Exception as e:
                print(f"[{self._now()}] Page load failed: {e}")
                self._maybe_retry(attempt)
                continue

            slot = self._find_today_slot(page, target_time)

            if slot is None:
                print(f"[{self._now()}] Slot not found. Retrying in {self.retry_interval}s...")
                self._maybe_retry(attempt)
                continue

            if slot.locator("[data-test-id='activities-list-item-badge-going']").count() > 0:
                print(f"[{self._now()}] Already booked. Done.")
                return

            booked = self._attempt_booking(slot, page)
            if booked:
                print(f"[{self._now()}] Successfully booked {target_time} slot!")
                return

            print(f"[{self._now()}] Booking failed (race condition?). Retrying in {self.retry_interval}s...")
            self._maybe_retry(attempt)

    def _find_today_slot(self, page: Page, target_time: str):
        """
        Return the activities-list-item locator for today's target_time slot, or None.
        Uses JS to find sibling slots under h2#day-0.
        """
        # Get the booking IDs of today's slots via JS sibling traversal
        booking_ids = page.evaluate("""() => {
            const dayHeader = document.querySelector('h2#day-0');
            if (!dayHeader) return [];
            const ids = [];
            let el = dayHeader.nextElementSibling;
            while (el && !el.matches('h2.date-header')) {
                const item = el.querySelector('activities-list-item[data-test-id="activities-list-item"]');
                if (item) {
                    const bookingId = item.getAttribute('data-test-booking-id');
                    if (bookingId) ids.push(bookingId);
                }
                el = el.nextElementSibling;
            }
            return ids;
        }""")

        print(f"[{self._now()}] Found {len(booking_ids)} slot(s) for today: {booking_ids}")
        if not booking_ids:
            return None

        for booking_id in booking_ids:
            slot = page.locator(f"activities-list-item[data-test-booking-id='{booking_id}']")
            time_el = slot.locator("[data-test-id='activities-list-item-start-time']")
            if time_el.count() > 0:
                slot_time = time_el.inner_text().strip()
                if slot_time == target_time:
                    return slot
                print(f"[{self._now()}] Skipping slot at {slot_time!r} (looking for {target_time!r})")

        return None

    def _attempt_booking(self, slot, page: Page) -> bool:
        """Click Book and wait for confirmation. Returns True on success."""
        try:
            book_btn = slot.locator("[data-test-id='activities-list-item-book-button']")
            if book_btn.count() == 0:
                return False
            book_btn.click()

            # A modal appears after clicking Book — click the confirm button inside it
            page.wait_for_selector("[data-test-id='details-book-button']", timeout=5000)
            page.click("[data-test-id='details-book-button']")

            # Wait for "Going" badge to appear as final success indicator
            slot.locator("[data-test-id='activities-list-item-badge-going']").wait_for(timeout=10000)
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
        return datetime.now().strftime("%H:%M:%S")
