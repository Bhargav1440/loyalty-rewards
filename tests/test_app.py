import os, sys, json, tempfile, threading, unittest, urllib.request, urllib.error
os.environ.update(DB_PATH=tempfile.mktemp(suffix=".db"), CODE_SECRET="t", ADMIN_PASSWORD="adm")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import server
from http.server import ThreadingHTTPServer

class Client:
    def __init__(s, base): s.base, s.cookie = base, None
    def call(s, method, path, body=None):
        req = urllib.request.Request(s.base + path, method=method, data=json.dumps(body or {}).encode() if method == "POST" else None, headers={"Content-Type": "application/json"})
        if s.cookie: req.add_header("Cookie", s.cookie)
        try: r = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e: r = e
        ck = r.headers.get("Set-Cookie")
        if ck: s.cookie = ck.split(";")[0]
        return r.status, json.loads(r.read())

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.init(); cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        cls.admin = Client(cls.base); cls.admin.call("POST", "/api/admin/login", {"password": "adm"})
    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()
    n = 0
    def user(s):
        T.n += 1; c = Client(s.base); c.call("POST", "/api/register", {"name": "U", "email": f"u{T.n}@x.com", "password": "password1"}); return c
    def codes(s, qty=3): return s.admin.call("POST", "/api/admin/batches", {"product_id": 1, "qty": qty})[1]["codes"]

    def test_valid_code_awards_points(s):
        u, code = s.user(), s.codes(1)[0]
        st, d = u.call("POST", "/api/redeem", {"code": code.lower().replace("-", " ")}); s.assertEqual(st, 200)
        s.assertEqual(u.call("GET", "/api/me")[1]["points"], 10)
    def test_code_cannot_be_reused_even_by_another_user(s):
        a, b, code = s.user(), s.user(), s.codes(1)[0]
        s.assertEqual(a.call("POST", "/api/redeem", {"code": code})[0], 200)
        s.assertEqual(a.call("POST", "/api/redeem", {"code": code})[0], 400)
        s.assertEqual(b.call("POST", "/api/redeem", {"code": code})[0], 400)
        s.assertEqual(b.call("GET", "/api/me")[1]["points"], 0)
    def test_concurrent_redeem_only_one_wins(s):
        code, res = s.codes(1)[0], []
        us = [s.user() for _ in range(8)]
        ts = [threading.Thread(target=lambda u=u: res.append(u.call("POST", "/api/redeem", {"code": code})[0])) for u in us]
        [t.start() for t in ts]; [t.join() for t in ts]
        s.assertEqual(res.count(200), 1)
    def test_guessing_locks_account(s):
        u = s.user()
        for _ in range(5): s.assertEqual(u.call("POST", "/api/redeem", {"code": "AAAA-BBBB-CCCC"})[0], 400)
        s.assertEqual(u.call("POST", "/api/redeem", {"code": s.codes(1)[0]})[0], 429)
    def test_db_stores_no_plaintext_codes(s):
        import sqlite3; code = s.codes(1)[0]
        raw = sqlite3.connect(server.DB).execute("SELECT group_concat(hash) FROM codes").fetchone()[0]
        s.assertNotIn(server.norm(code), raw)
    def test_claim_needs_points_and_stock(s):
        u = s.user(); s.assertEqual(u.call("POST", "/api/claim", {"reward_id": 1})[0], 400)
        for c in s.codes(10): u.call("POST", "/api/redeem", {"code": c})
        s.assertEqual(u.call("POST", "/api/claim", {"reward_id": 1})[0], 200)
        s.assertEqual(u.call("GET", "/api/me")[1]["points"], 0)
    def test_admin_routes_protected(s):
        u = s.user(); s.assertEqual(u.call("GET", "/api/admin/stats")[0], 401)
        s.assertEqual(Client(s.base).call("POST", "/api/admin/batches", {"product_id": 1, "qty": 1})[0], 401)
    def test_admin_stats(s):
        st, d = s.admin.call("GET", "/api/admin/stats"); s.assertEqual(st, 200); s.assertIn("suspicious", d)
if __name__ == "__main__": unittest.main()
