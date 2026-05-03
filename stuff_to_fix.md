# Stuff to fix

All issues are addressed. Notes below describe what was wrong and
what changed.

Items #1–#5 were the original list; #6 was a follow-up surfaced
during the #1 investigation; #7–#8 were added afterwards. Everything
is fixed.

---

1. **Sparkline graph on the Properties list — does it actually update?**
   _Status: verified wired; no code change needed._

   The graph IS connected to the real `connected_device_counts` data
   (24 hourly buckets per property). Verified end-to-end: Park Lane,
   Hanalei, Koko Head Labs all return varying values. When a
   sparkline looks flat it's because that property genuinely has flat
   numbers in the window — e.g. Pakalana shows zeros because its
   eeros have all been chronic-offline for months, and freshly-added
   properties don't have history yet.

   _Worth noting separately:_ the polling worker has fallen behind on
   some properties (Park Lane's last device-count is from 01:00 UTC
   while Pacific 19 is current to within minutes). That's an
   operational issue, not a wiring issue, and is not on this list —
   call it out if you want it tracked.

2. **Pakalana shows "online" but no networks are alive.**
   _Status: fixed._

   The dashboard rollup was looking only at the network-level
   `is_online` flag (does the eero cloud return 200 for `/network`).
   The cloud was happily reporting "OK" even though every physical
   eero unit at Pakalana has been chronic-offline since Feb/Mar.

   The rollup now also checks the eero device state: a network is
   only "online" for the dashboard if the network is reachable AND
   at least one of its eero units is online (when units are known).
   Pakalana now correctly shows "degraded / 1 offline".

3. **Time zone should be HST.**
   _Status: audited; already HST throughout._

   Walked every date formatter on both sides:
   - All frontend `Intl.DateTimeFormat` calls already pin
     `timeZone: "Pacific/Honolulu"` (header clock, today's date,
     greeting, area chart axis, status history, maintenance card,
     device-counts chart).
   - Backend pre-formats human-facing strings (alert times,
     `hst_now`) in HST. UTC datetimes only appear in storage and
     query cutoffs (correct — those are time math, not display).

   No code change. If you noticed something specific showing the
   wrong zone, point me at the page and I'll dig deeper.

4. **eero Models + Firmware Versions panels on the property page are empty.**
   _Status: fixed._

   The two side panels expected `eero_models` and `firmware_versions`
   dictionaries on the API response, but the DB-backed builder never
   populated them — they were always empty. Added the aggregation:
   walks every eero unit on every common area in the property and
   counts by model / firmware string. Verified Park Lane now returns
   `{eero PoE 6: 22, eero PoE Gateway: 10, eero Pro 6E: 2}` with
   firmware mix.

5. **Live Alerts streamer + "Mark all as read" wiring.**
   _Status: fixed._

   - "Mark all as read" was a button with no `onClick`. Now wired —
     bulk-dismisses every currently-unread alert.
   - Read state persists in your browser (`localStorage`) so a
     refresh doesn't bring all the noise back. Backend has no
     acknowledgement endpoint, so this is a per-browser preference
     by design.
   - The top streamer ("LIVE … LIVE …") now hides anything you've
     dismissed.
   - Each property only appears once in the streamer. The most
     recent alert wins (backend already returns alerts most-recent
     first, so we just keep the first per-property as we walk the
     list).
   - The Live Alerts card header now shows
     `N UNREAD · LAST 24H · M READ` so you can see how much you've
     dismissed.

6. **Polling worker was falling behind on most properties.**
   _Status: fixed._

   The worker process was alive but **every scheduled poll tick was
   crashing immediately** with `RuntimeError: no running event loop`.
   The recent device-counts I'd seen on Pacific 19 / Pakalana / etc.
   were from the manual "Force check now" button (a different code
   path), not from the scheduled worker — it just looked like the
   worker was running unevenly. In reality it was running 0% of the
   time.

   Cause: each scheduled job was registered as a sync lambda that
   called `asyncio.create_task(...)`. APScheduler executes sync
   callables on a worker thread that has no event loop, so
   `create_task` blew up before the job body could even start.

   Fix: pass the async function directly to `add_job(...)` —
   `AsyncIOScheduler` schedules coroutines natively on its own loop.
   Single-line change in `app/worker.py`. After a worker restart the
   next 15-min cron tick should successfully poll all 12 properties
   for the first time since cutover.

7. **Island moves to the Property; auto-detect from address; remove from Common Area form.**
   _Status: fixed._

   - **Schema** — added `properties.island`. Backfilled from the
     existing per-area islands (most-common-per-property, deterministic
     tie-break). All migrated properties picked up the right island;
     Ka Eo Kai stayed null and can be set on first edit.

   - **Auto-detect from address** — new heuristic looks for explicit
     island names + well-known town keywords (Honolulu / Waikiki →
     Oahu, Lahaina / Wailuku → Maui, Hilo / Kona → Hawaii, Lihue /
     Princeville → Kauai, Kaunakakai → Molokai, Lanai City → Lanai).
     Ambiguous addresses ("Kailua, HI" — exists on both Oahu and
     Hawaii) intentionally return null so the operator picks.

   - **Add Property form** — gains an Island dropdown. Auto-populates
     as the operator types the address (debounced). Once they
     manually pick, auto-detect stops overriding. Hint line shows
     MANUALLY SET / AUTO-DETECTED / WILL AUTO-DETECT.

   - **Edit Property form** — same dropdown, pre-populated from the
     existing value. Auto-detect only runs if the property didn't
     already have an island set, so a typo in the address doesn't
     blow away a manual choice.

   - **Common Area form** — Island input removed. Property is now the
     single source of truth.

   - **Display** — "Big Island" renamed to "Hawaii" everywhere
     user-facing. Internal slug (`big-island`) stays for URL/map-key
     stability.

   - **Map** — Molokai and Lanai now show on the dashboard map (they
     were missing entirely before), so pins for properties on either
     land in the right place.

8. **Property list on the dashboard: show address, not Central Office.**
   _Status: fixed._

   The little grey line under each property name was showing the OLT
   CLLI (e.g. `LHNAHICO` for Aston Kaanapali Shores). Replaced with
   the property's address; falls back to `—` when no address is set.

   - PropertyPin gained an `address` field on the wire.
   - Dashboard property table + standalone /properties index page
     both updated (desktop and mobile layouts).
   - Search box on the /properties page now filters on
     name/address (was name/central-office).
   - Central Office stays available on the property detail-page
     header (where it's actually useful), just not in the list.