# Box Rewards - Customer Loyalty System

A factory prints a unique single-use code inside every product box. Customers create an account, enter the code to earn points, climb tiers (Bronze/Silver/Gold) and claim rewards. The factory owner has a dashboard to print codes, manage rewards and watch for fraud.

**Tech stack:** Python 3.10+ (standard library only: `http.server`, `sqlite3`, `hmac`, `hashlib.scrypt`), SQLite, vanilla HTML/CSS/JS. No `pip install` needed.

## Run
```bash
copy .env.example .env      # Windows (Mac/Linux: cp .env.example .env)
# open .env in Notepad and set your own ADMIN_PASSWORD and CODE_SECRET
python server.py            # http://localhost:8000
```
`server.py` reads `.env` automatically. Without a `.env` the defaults are used (admin password `change-me-admin`).
Customer area = default view. Factory owner = "Factory owner" button, password from `ADMIN_PASSWORD`.
First start seeds one demo product and two rewards.

## Demo flow
1. Admin: log in, pick product, generate e.g. 5 codes (CSV downloads).
2. Customer: register, enter a code, see points; enter it again to see rejection.
3. Claim a reward once you have enough points; admin sees it under "Recent claims".

## Tests
`python3 -m unittest discover -s tests` (8 automated tests, see ARCHITECTURE.md).

Deployed link: _add here after deploying (e.g. Render/Railway: start command `python server.py`)._
