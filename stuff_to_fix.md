# Stuff to fix

All issues from the original list are addressed. Notes below describe
what was wrong and what changed.

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
