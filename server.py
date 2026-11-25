"""Customer Loyalty Rewards System - stdlib only (http.server + sqlite3)."""
import os
import json
import hmac
import hashlib
import secrets
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse


# Load settings from .env file
def load_env():
    env_file = Path(__file__).with_name(".env")

    if env_file.exists():
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            # Existing system environment variables take priority
            os.environ.setdefault(key, value)


load_env()

# Application settings
DB = os.environ.get("DB_PATH", "loyalty.db")
SECRET = os.environ.get("CODE_SECRET", "change-me").encode()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-admin")
PORT = int(os.environ.get("PORT", "8000"))

MAX_FAILS, WINDOW = 5, 900
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TIERS = [(1000, "Gold"), (300, "Silver"), (0, "Bronze")]
SCHEMA = """
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, points INTEGER NOT NULL CHECK(points>0));
CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(id), qty INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS codes(hash TEXT PRIMARY KEY, batch_id INTEGER REFERENCES batches(id), redeemed_by INTEGER, redeemed_at INTEGER);
CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT, email TEXT UNIQUE, salt BLOB, pw TEXT, points INTEGER DEFAULT 0 CHECK(points>=0), created_at INTEGER);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, role TEXT, cid INTEGER, expires INTEGER);
CREATE TABLE IF NOT EXISTS rewards(id INTEGER PRIMARY KEY, name TEXT NOT NULL, cost INTEGER CHECK(cost>0), stock INTEGER CHECK(stock>=0), active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS claims(id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), reward_id INTEGER REFERENCES rewards(id), cost INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY, kind TEXT, key TEXT, ok INTEGER, created_at INTEGER);
CREATE TABLE IF NOT EXISTS earnings(id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER, points INTEGER, created_at INTEGER);
"""

class Fail(Exception):
    def __init__(s, status, msg): s.status, s.msg = status, msg

@contextmanager
def tx():
    c = sqlite3.connect(DB, timeout=15, isolation_level=None); c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON"); c.execute("BEGIN IMMEDIATE")
    try: yield c; c.execute("COMMIT")
    except BaseException: c.execute("ROLLBACK"); raise
    finally: c.close()

def init():
    with tx() as c:
        for s in SCHEMA.strip().split(";"):
            if s.strip(): c.execute(s)
        if not c.execute("SELECT 1 FROM products").fetchone():
            c.execute("INSERT INTO products(name,points) VALUES('Classic Biscuits 500g',10)")
            c.execute("INSERT INTO rewards(name,cost,stock) VALUES('10% discount coupon',100,50),('Free box of biscuits',250,20)")

now = lambda: int(time.time())
norm = lambda s: "".join(ch for ch in str(s).upper() if ch.isalnum())
hcode = lambda s: hmac.new(SECRET, norm(s).encode(), hashlib.sha256).hexdigest()
th = lambda t: hashlib.sha256(t.encode()).hexdigest()
tier = lambda p: next(n for m, n in TIERS if p >= m)
def newcode():
    s = "".join(secrets.choice(ALPHABET) for _ in range(12)); return "-".join(s[i:i+4] for i in (0, 4, 8))
def hpw(pw, salt): return hashlib.scrypt(pw.encode(), salt=salt, n=2**14, r=8, p=1).hex()
def fails(c, kind, key):
    return c.execute("SELECT COUNT(*) FROM attempts WHERE kind=? AND key=? AND ok=0 AND created_at>?", (kind, key, now()-WINDOW)).fetchone()[0]
def log(c, kind, key, ok): c.execute("INSERT INTO attempts(kind,key,ok,created_at) VALUES(?,?,?,?)", (kind, key, int(ok), now()))
def new_session(c, role, cid):
    t = secrets.token_urlsafe(32)
    c.execute("INSERT INTO sessions VALUES(?,?,?,?)", (th(t), role, cid, now()+86400*7))
    return f"sid={t}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800"

ROUTES = {}
def route(method, path, role=None):
    def d(f): ROUTES[(method, path)] = (f, role); return f
    return d

def need(b, *keys):
    for k in keys:
        if k not in b: raise Fail(400, f"Missing field: {k}")

# ---------- customer ----------
@route("POST", "/api/register")
def register(h, b, u):
    need(b, "name", "email", "password")
    email, name, pw = str(b["email"]).strip().lower(), str(b["name"]).strip(), str(b["password"])
    if "@" not in email or not name or len(pw) < 8: raise Fail(400, "Enter a name, a valid email and a password of 8+ characters.")
    salt = secrets.token_bytes(16)
    with tx() as c:
        try: cid = c.execute("INSERT INTO customers(name,email,salt,pw,created_at) VALUES(?,?,?,?,?)", (name, email, salt, hpw(pw, salt), now())).lastrowid
        except sqlite3.IntegrityError: raise Fail(409, "This email is already registered.")
        return 200, {"ok": True}, new_session(c, "customer", cid)

@route("POST", "/api/login")
def login(h, b, u):
    need(b, "email", "password"); ip = h.client_address[0]
    with tx() as c:
        if fails(c, "login", ip) >= 10: raise Fail(429, "Too many failed logins. Try again later.")
        r = c.execute("SELECT * FROM customers WHERE email=?", (str(b["email"]).strip().lower(),)).fetchone()
        ok = r is not None and hmac.compare_digest(r["pw"], hpw(str(b["password"]), r["salt"]))
        log(c, "login", ip, ok)
        if not ok: return 401, {"error": "Wrong email or password."}
        return 200, {"ok": True}, new_session(c, "customer", r["id"])

@route("POST", "/api/logout")
def logout(h, b, u):
    with tx() as c: c.execute("DELETE FROM sessions WHERE cid IS ? AND role=?", (u["cid"] if u else None, u["role"] if u else ""))
    return 200, {"ok": True}, "sid=; Path=/; Max-Age=0"

@route("GET", "/api/me", "customer")
def me(h, b, u):
    with tx() as c:
        r = c.execute("SELECT name,email,points FROM customers WHERE id=?", (u["cid"],)).fetchone()
        hist = c.execute("SELECT p.name,e.points,e.created_at FROM earnings e JOIN products p ON p.id=e.product_id WHERE e.customer_id=? ORDER BY e.id DESC LIMIT 20", (u["cid"],)).fetchall()
        cl = c.execute("SELECT w.name,l.cost,l.created_at FROM claims l JOIN rewards w ON w.id=l.reward_id WHERE l.customer_id=? ORDER BY l.id DESC LIMIT 20", (u["cid"],)).fetchall()
    return 200, {**dict(r), "tier": tier(r["points"]), "earned": [dict(x) for x in hist], "claimed": [dict(x) for x in cl]}

@route("POST", "/api/redeem", "customer")
def redeem(h, b, u):
    need(b, "code"); key = str(u["cid"]); code = norm(b["code"])
    with tx() as c:
        if fails(c, "redeem", key) >= MAX_FAILS: raise Fail(429, "Too many invalid codes. Your account is locked for 15 minutes.")
        if len(code) != 12 or any(ch not in ALPHABET for ch in code):
            log(c, "redeem", key, 0); return 400, {"error": "Invalid or already used code."}
        hh = hcode(code)
        # Atomic single-use claim: only one UPDATE can ever match an unredeemed row.
        n = c.execute("UPDATE codes SET redeemed_by=?, redeemed_at=? WHERE hash=? AND redeemed_by IS NULL", (u["cid"], now(), hh)).rowcount
        if n != 1:
            log(c, "redeem", key, 0); return 400, {"error": "Invalid or already used code."}  # same message: no oracle
        p = c.execute("SELECT p.id,p.name,p.points FROM codes k JOIN batches b ON b.id=k.batch_id JOIN products p ON p.id=b.product_id WHERE k.hash=?", (hh,)).fetchone()
        c.execute("UPDATE customers SET points=points+? WHERE id=?", (p["points"], u["cid"]))
        c.execute("INSERT INTO earnings(customer_id,product_id,points,created_at) VALUES(?,?,?,?)", (u["cid"], p["id"], p["points"], now()))
        log(c, "redeem", key, 1)
        return 200, {"ok": True, "product": p["name"], "points": p["points"]}

@route("GET", "/api/rewards", "customer")
def rewards(h, b, u):
    with tx() as c: return 200, [dict(r) for r in c.execute("SELECT id,name,cost,stock FROM rewards WHERE active=1 AND stock>0 ORDER BY cost")]

@route("POST", "/api/claim", "customer")
def claim(h, b, u):
    need(b, "reward_id")
    with tx() as c:
        r = c.execute("SELECT * FROM rewards WHERE id=? AND active=1", (b["reward_id"],)).fetchone()
        if not r: raise Fail(404, "Reward not available.")
        if c.execute("UPDATE customers SET points=points-? WHERE id=? AND points>=?", (r["cost"], u["cid"], r["cost"])).rowcount != 1: raise Fail(400, "Not enough points.")
        if c.execute("UPDATE rewards SET stock=stock-1 WHERE id=? AND stock>0", (r["id"],)).rowcount != 1: raise Fail(400, "Out of stock.")
        c.execute("INSERT INTO claims(customer_id,reward_id,cost,created_at) VALUES(?,?,?,?)", (u["cid"], r["id"], r["cost"], now()))
    return 200, {"ok": True, "reward": r["name"]}

# ---------- admin ----------
@route("POST", "/api/admin/login")
def admin_login(h, b, u):
    need(b, "password"); ip = h.client_address[0]
    with tx() as c:
        if fails(c, "admin", ip) >= 5: raise Fail(429, "Too many attempts. Try again later.")
        ok = hmac.compare_digest(str(b["password"]).encode(), ADMIN_PASSWORD.encode()); log(c, "admin", ip, ok)
        if not ok: return 401, {"error": "Wrong password."}
        return 200, {"ok": True}, new_session(c, "admin", None)

@route("GET", "/api/admin/stats", "admin")
def stats(h, b, u):
    d = now() - 86400
    with tx() as c:
        g = lambda s, *a: c.execute(s, a).fetchone()[0]
        return 200, {
            "customers": g("SELECT COUNT(*) FROM customers"), "codes": g("SELECT COUNT(*) FROM codes"),
            "redeemed": g("SELECT COUNT(*) FROM codes WHERE redeemed_by IS NOT NULL"),
            "points_issued": g("SELECT COALESCE(SUM(points),0) FROM earnings"), "points_spent": g("SELECT COALESCE(SUM(cost),0) FROM claims"),
            "failed_24h": g("SELECT COUNT(*) FROM attempts WHERE kind='redeem' AND ok=0 AND created_at>?", d),
            "suspicious": [dict(r) for r in c.execute("SELECT c.id,c.email,COUNT(*) fails FROM attempts a JOIN customers c ON CAST(c.id AS TEXT)=a.key WHERE a.kind='redeem' AND a.ok=0 AND a.created_at>? GROUP BY c.id HAVING fails>=3 ORDER BY fails DESC", (d,))],
            "top": [dict(r) for r in c.execute("SELECT name,email,points FROM customers ORDER BY points DESC LIMIT 5")],
            "claims": [dict(r) for r in c.execute("SELECT c.email,w.name,l.cost,l.created_at FROM claims l JOIN customers c ON c.id=l.customer_id JOIN rewards w ON w.id=l.reward_id ORDER BY l.id DESC LIMIT 20")],
            "products": [dict(r) for r in c.execute("SELECT p.id,p.name,p.points,(SELECT COUNT(*) FROM codes k JOIN batches b ON b.id=k.batch_id WHERE b.product_id=p.id) generated,(SELECT COUNT(*) FROM codes k JOIN batches b ON b.id=k.batch_id WHERE b.product_id=p.id AND k.redeemed_by IS NOT NULL) redeemed FROM products p")],
            "rewards": [dict(r) for r in c.execute("SELECT * FROM rewards")]}

@route("POST", "/api/admin/products", "admin")
def add_product(h, b, u):
    need(b, "name", "points")
    try: pts = int(b["points"]); assert pts > 0
    except (ValueError, AssertionError): raise Fail(400, "Points must be a positive number.")
    with tx() as c: c.execute("INSERT INTO products(name,points) VALUES(?,?)", (str(b["name"]).strip(), pts))
    return 200, {"ok": True}

@route("POST", "/api/admin/batches", "admin")
def gen(h, b, u):
    need(b, "product_id", "qty")
    try: qty = int(b["qty"]); assert 1 <= qty <= 10000
    except (ValueError, AssertionError): raise Fail(400, "Quantity must be 1-10000.")
    with tx() as c:
        if not c.execute("SELECT 1 FROM products WHERE id=?", (b["product_id"],)).fetchone(): raise Fail(404, "Unknown product.")
        bid = c.execute("INSERT INTO batches(product_id,qty,created_at) VALUES(?,?,?)", (b["product_id"], qty, now())).lastrowid
        out = []
        while len(out) < qty:
            code = newcode()
            if c.execute("INSERT OR IGNORE INTO codes(hash,batch_id) VALUES(?,?)", (hcode(code), bid)).rowcount: out.append(code)
    return 200, {"batch_id": bid, "codes": out}  # plaintext returned ONCE, never stored

@route("POST", "/api/admin/rewards", "admin")
def add_reward(h, b, u):
    need(b, "name", "cost", "stock")
    try: cost, stock = int(b["cost"]), int(b["stock"]); assert cost > 0 and stock >= 0
    except (ValueError, AssertionError): raise Fail(400, "Cost must be positive and stock 0 or more.")
    with tx() as c: c.execute("INSERT INTO rewards(name,cost,stock) VALUES(?,?,?)", (str(b["name"]).strip(), cost, stock))
    return 200, {"ok": True}

@route("POST", "/api/admin/rewards/toggle", "admin")
def toggle(h, b, u):
    need(b, "id")
    with tx() as c: c.execute("UPDATE rewards SET active=1-active WHERE id=?", (b["id"],))
    return 200, {"ok": True}

# ---------- http ----------
class H(BaseHTTPRequestHandler):
    def log_message(s, *a): pass
    def reply(s, st, data, cookie=None, ctype="application/json"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        s.send_response(st); s.send_header("Content-Type", ctype); s.send_header("Content-Length", str(len(body)))
        s.send_header("X-Content-Type-Options", "nosniff"); s.send_header("Cache-Control", "no-store")
        if cookie: s.send_header("Set-Cookie", cookie)
        s.end_headers(); s.wfile.write(body)
    def session(s):
        for part in (s.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid" and v:
                with tx() as c:
                    r = c.execute("SELECT role,cid FROM sessions WHERE token=? AND expires>?", (th(v), now())).fetchone()
                return dict(r) if r else None
    def dispatch(s, method):
        path = urlparse(s.path).path
        if method == "GET" and not path.startswith("/api/"):
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"), "rb") as f:
                return s.reply(200, f.read(), ctype="text/html; charset=utf-8")
        ent = ROUTES.get((method, path))
        if not ent: return s.reply(404, {"error": "Not found"})
        fn, role = ent
        try:
            n = int(s.headers.get("Content-Length") or 0)
            if n > 1_000_000: raise Fail(413, "Request too large.")
            body = json.loads(s.rfile.read(n) or b"{}") if method == "POST" else {}
            if not isinstance(body, dict): raise Fail(400, "Bad request.")
            if method == "POST" and "json" not in (s.headers.get("Content-Type") or ""): raise Fail(415, "JSON only.")
            user = s.session()
            if role and (not user or user["role"] != role): raise Fail(401, "Please log in.")
            res = fn(s, body, user)
            s.reply(res[0], res[1], res[2] if len(res) > 2 else None)
        except Fail as e: s.reply(e.status, {"error": e.msg})
        except (ValueError, json.JSONDecodeError): s.reply(400, {"error": "Bad request."})
        except Exception as e: print("ERR", repr(e)); s.reply(500, {"error": "Server error."})
    do_GET = lambda s: s.dispatch("GET")
    do_POST = lambda s: s.dispatch("POST")

if __name__ == "__main__":
    init(); print(f"Running on http://localhost:{PORT}")
    ThreadingHTTPServer(("", PORT), H).serve_forever()
