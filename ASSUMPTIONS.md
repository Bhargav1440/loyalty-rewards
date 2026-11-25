# Assumptions
| Gap | Choice | Why |
|---|---|---|
| Proof of purchase | Unique code printed inside each box (under the flap) | Cheap for a factory to print; opening the box = proof of owning product. No retailer integration needed. |
| Code format | 12 chars from a 32-letter alphabet without 0/O/1/I, shown as XXXX-XXXX-XXXX | 32^12 ≈ 1.1e18 combinations: guessing is infeasible; no look-alike characters on print. |
| Who prints | Factory generates batches in the admin panel and downloads a CSV for the printer | Matches factory workflow. |
| Code storage | Only an HMAC-SHA256 of the code is stored; plaintext shown once at generation | A database leak does not leak usable codes. |
| Customer identity | Email + password account | Points must belong to a person; simple and standard. |
| Points | Fixed points per product (set by owner) | Lets expensive products earn more. |
| Tiers | Bronze 0, Silver 300, Gold 1000 current points | Visible loyalty goal. Tier is display-only; no tier-specific perks yet. |
| Rewards | Owner-defined catalogue with cost and stock; claim deducts points | Owner controls budget. Fulfilment (shipping/coupon delivery) happens outside the app. |
| Points expiry / returns | None | Out of scope; documented as future work. |
| Fraud limits | 5 wrong codes per account per 15 min -> locked; 10 failed logins per IP; 5 admin logins per IP | Stops brute force while tolerating typos. |
| Error message | Same message for unknown and already-used codes | Prevents attackers learning which codes exist. |
| Admin | Single admin password from environment variable | One factory owner; no multi-user need. |
| Scale | Thousands of customers, SQLite | Fits a single-factory client; swap to Postgres later. |
| Transport | Deployment must use HTTPS (platform proxy) | Cookies are HttpOnly + SameSite=Strict; add `Secure` flag when behind HTTPS. |
| Known limitation | A stolen *physical* box/code can be redeemed by the thief; stolen-code disputes are manual | Inherent to printed codes; admin can see who redeemed what. |
