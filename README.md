# Box Rewards - Customer Loyalty System

A factory prints a unique single-use code inside every product box. Customers create an account, enter the code to earn points, climb tiers (Bronze/Silver/Gold) and claim rewards. The factory owner has a dashboard to print codes, manage rewards and watch for fraud.

**Tech stack:** Python 3.10+ (standard library only: `http.server`, `sqlite3`, `hmac`, `hashlib.scrypt`), SQLite, vanilla HTML/CSS/JS. No `pip install` needed.

## Run
```bash
cp .env.example .env        # then edit values
set -a; source .env; set +a  # load env vars (Linux/Mac). Windows: set each var manually
python3 server.py            # http://localhost:8000
```
Customer area = default view. Factory owner = "Factory owner" button, password from `ADMIN_PASSWORD`.
First start seeds one demo product and two rewards.

## Demo flow
1. Admin: log in, pick product, generate e.g. 5 codes (CSV downloads).
2. Customer: register, enter a code, see points; enter it again to see rejection.
3. Claim a reward once you have enough points; admin sees it under "Recent claims".

## Tests
`python3 -m unittest discover -s tests` (8 automated tests, see ARCHITECTURE.md).

Deployed link: _add here after deploying (e.g. Render/Railway: start command `python server.py`)._
