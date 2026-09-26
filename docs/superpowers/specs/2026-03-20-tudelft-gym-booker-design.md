# TU Delft Gym Slot Booker — Design Spec

**Date:** 2026-03-20
**Status:** Approved

---

## Overview

A Python CLI script that automatically books a gym fitness timeslot on [x.tudelft.nl](https://x.tudelft.nl/bookings/activities?tags=28) for today at a user-specified time. If the slot is not yet available, the script retries on a configurable interval until it succeeds or is manually stopped.

**Usage:**
```
python booker.py 18:00
```

---

## Architecture

Three modules with single, clear responsibilities:

| File | Responsibility |
|---|---|
| `booker.py` | CLI entry point — parses args, initializes Playwright, orchestrates login and booking |
| `login_handler.py` | `LoginHandler` class — reads credentials from `.env`, navigates to login page, authenticates |
| `booking_handler.py` | `BookingHandler` class — finds today's slot matching target time, clicks to book, handles retry loop |

### Configuration

`.env` file in the project root:
```
TUDELFT_USERNAME=your_netid
TUDELFT_PASSWORD=your_password
RETRY_INTERVAL_SECONDS=30   # optional, default: 30
MAX_RETRIES=0               # optional, default: 0 (unlimited, Ctrl+C to stop)
```

---

## Data Flow

```
booker.py
  │  parse CLI arg (target_time = "18:00")
  │  launch Playwright headless Chromium
  │
  ├─► LoginHandler.login(page)
  │     navigate to login page
  │     fill username + password from .env
  │     submit form
  │     wait for successful redirect
  │     return authenticated page
  │
  └─► BookingHandler.book(page, target_time)
        navigate to https://x.tudelft.nl/bookings/activities?tags=28
        scan timeslots for today matching target_time
        if found → click Book → confirm → print success → exit
        if not found → wait RETRY_INTERVAL_SECONDS → retry
        on max retries exceeded → print error → exit with code 1
```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Bad credentials / login fails | Print clear error, exit immediately (no retry) |
| Slot not found | Retry after `RETRY_INTERVAL_SECONDS` (default 30s) |
| Slot found but booking fails (race condition) | Treat as not found, retry |
| Slot already booked by this user | Print "already booked" message, exit with code 0 |
| Network error or page load failure | Print timestamped error, retry up to `MAX_RETRIES` |
| Max retries exceeded | Print error summary, exit with code 1 |
| Keyboard interrupt (Ctrl+C) | Graceful exit with message |

All output is timestamped for visibility when running in background.

---

## Dependencies

- `playwright` (with Chromium) — browser automation
- `python-dotenv` — `.env` loading
- Python 3.10+

---

## Out of Scope

- Automated tests (manual verification sufficient for this script)
- Booking future dates (today only)
- Multiple slot booking in one run
