# AI Log

Tool used: Claude (claude.ai chat). All entries below come from the real conversation used to build this project. Prompts were written in Hinglish and are quoted as typed.

## 1. Building the whole system
- **Prompt:** (uploaded the assignment PDF) "Ye website full design and backend sabkuch karke dede"
- **AI output:** A Python (standard library) + SQLite backend, a single-page web UI, 8 automated tests, and the required docs.
- **Was it right?** Mostly yes. Key design decisions made here: codes stored only as HMAC hashes (a DB leak does not expose usable codes), single-use enforced by one atomic SQL `UPDATE ... WHERE redeemed_by IS NULL`, lockout after 5 wrong codes, same error message for unknown and used codes.
- **How I checked:** Ran the tests, including one where 8 users redeem the same code at the same moment; exactly one succeeds.

## 2. AI was wrong: handler method name clash
- **AI output:** `server.py` defined `H.handle(self, method)` for routing.
- **Problem:** `BaseHTTPRequestHandler` already calls `self.handle()` with no arguments, so every request crashed (`RemoteDisconnected` in the tests).
- **How it was noticed:** The AI ran the automated tests before handing over the code; the test run failed.
- **Fix:** Renamed the method to `dispatch()`. All 8 tests pass.

## 3. UI redesign
- **Prompt:** "thoda luxury type website banana ki jisme animation ho aisa"
- **AI output:** New dark emerald and gold design with count-up points, a tier progress ring, a stamp animation on successful redeem, and reduced-motion support. Backend untouched; tests re-run and still pass.
- **Was it right?** Yes for logic. The AI could not view the page in a browser, so I checked the animations myself by running the app.

## 4. AI was wrong: README implied `.env` was loaded
- **Prompt:** "wrong pass kyu aarha hain"
- **Problem:** The README told me to copy `.env.example` to `.env`, which suggests it is read automatically. `server.py` never read it, so the admin login rejected my password (the default `change-me-admin` was still active). The shell command in the README also did not work on Windows.
- **How I noticed:** I got "Wrong password" while logging in as the factory owner.
- **Fix:** Added a small `.env` loader to `server.py` and rewrote the README run steps for Windows and Mac/Linux.

## 5. AI was wrong: assumed Git was installed
- **Prompt:** "ab is website ko github pe kaise upload karna hain"
- **Problem:** The AI first gave Git command-line steps and later asked me to run `git update-ref` in Command Prompt. My PC has no Git installed, so the commands failed ("'git' is not recognized").
- **How I noticed:** I ran them and got the error (screenshot sent to the AI).
- **Fix:** Switched to GitHub Desktop only, no command line.

## 6. GitHub Desktop bundled everything into one commit
- **Problem:** When I created the repository, GitHub Desktop made one "Initial commit" containing all 10 files. The assignment penalises a single commit, and the AI's steps had not warned about this.
- **How I noticed:** The History tab showed "10 changed files" in one commit.
- **Fix:** Used the **Undo** button, then committed in groups: setup files, backend, tests, web interface, docs. The repository was published only after that, as public.
