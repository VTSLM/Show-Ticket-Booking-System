"""
Score the TicketFlow Assistant against chat_eval/cases.json.

Runs every case through the live streaming endpoint (POST /api/chat/stream) of a
running backend, records which tools were called (from the stream's status
events), checks each case's expectations and prints a scorecard.

    cd backend
    python chat_eval/run_eval.py                    # guest cases only
    python chat_eval/run_eval.py --login            # also logged-in cases (asks email + password)
    python chat_eval/run_eval.py --only search,policy --base-url http://localhost:8000

Needs the backend running with OPENAI_API_KEY set. Uses the standard library only.
Results are written to chat_eval/results/ (git-ignored). Each case is one OpenAI
conversation, so a full run costs a little API usage.
"""
import argparse
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
LINK = re.compile(r"\]\(([^)\s]+)\)")
SCRIPTS = {"hi": re.compile(r"[ऀ-ॿ]"), "gu": re.compile(r"[઀-૿]")}


# ── scoring (pure, unit-tested) ──────────────────────────────────────────────

def score_case(case: dict, events: list, seconds: float, first_text: Optional[float] = None) -> dict:
    """Return {'passed': bool, 'checks': {name: bool}, 'tools': [...], 'reply': str}."""
    tools = [e["tool"] for e in events if e.get("type") == "status"]
    reply = "".join(e.get("text", "") for e in events if e.get("type") == "delta")
    low = reply.lower()
    checks = {"no_error": not any(e.get("type") == "error" for e in events) and bool(reply.strip()),
              "complete": not any(e.get("type") == "done" and e.get("truncated") for e in events)}

    if case.get("expect_tools_any"):
        checks["tools"] = any(t in tools for t in case["expect_tools_any"])
    if case.get("expect_no_tools"):
        checks["no_tools"] = not tools
    if case.get("must_contain_any"):
        checks["contains"] = any(s.lower() in low for s in case["must_contain_any"])
    if case.get("must_not_contain"):
        checks["not_contains"] = not any(s.lower() in low for s in case["must_not_contain"])
    if case.get("language") in SCRIPTS:
        checks["language"] = bool(SCRIPTS[case["language"]].search(reply))
    links = LINK.findall(reply)
    checks["in_app_links"] = all(u.startswith("/") and not u.startswith("//") for u in links)

    return {"passed": all(checks.values()), "checks": checks, "tools": tools, "reply": reply,
            "seconds": round(seconds, 1),
            "first_text_seconds": round(first_text, 1) if first_text is not None else None}


def parse_sse(raw: str) -> list:
    return [json.loads(chunk[6:]) for chunk in raw.split("\n\n") if chunk.startswith("data: ")]


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _request(url: str, body: Optional[dict] = None, token: Optional[str] = None, timeout: int = 120) -> str:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8")


def stream_chat(url: str, body: dict, token: Optional[str], start: float):
    """POST and read the event stream as it arrives. Returns (events, seconds_to_first_text)."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    events, first_text = [], None
    with urllib.request.urlopen(req, timeout=180) as res:
        for raw in res:
            line = raw.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("type") == "delta" and first_text is None:
                first_text = time.monotonic() - start
            events.append(event)
    return events, first_text


def _firebase_web_key() -> Optional[str]:
    key = os.getenv("FIREBASE_WEB_API_KEY")
    env_local = HERE.parent.parent / "frontend" / ".env.local"
    if not key and env_local.exists():
        for line in env_local.read_text().splitlines():
            if line.startswith("NEXT_PUBLIC_FIREBASE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key


def login() -> str:
    key = _firebase_web_key()
    if not key:
        sys.exit("Set FIREBASE_WEB_API_KEY or keep NEXT_PUBLIC_FIREBASE_API_KEY in frontend/.env.local")
    email = input("Customer email: ").strip()
    password = getpass.getpass("Password: ")
    raw = _request(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={key}",
                   {"email": email, "password": password, "returnSecureToken": True})
    return json.loads(raw)["idToken"]


def resolve_context(case: dict, base: str, token: Optional[str]) -> dict:
    ctx = case.get("context") or {}
    if "event_title" in ctx:
        shows = json.loads(_request(f"{base}/api/browse/shows"))
        match = next((s for s in shows if s["title"].lower() == ctx["event_title"].lower()), None)
        return {"event_id": str(match["event_id"])} if match else {}
    if ctx.get("booking") == "latest" and token:
        bookings = json.loads(_request(f"{base}/api/bookings", token=token))
        return {"booking_id": str(bookings[0]["id"])} if bookings else {}
    return {}


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--login", action="store_true", help="log in to also run the logged-in cases")
    ap.add_argument("--only", help="comma-separated categories")
    ap.add_argument("--delay", type=float, default=3.5, help="seconds between cases (rate limit is 20/min)")
    args = ap.parse_args()

    cases = json.loads((HERE / "cases.json").read_text())["cases"]
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["category"] in wanted]
    token = login() if args.login else None

    results, skipped = [], []
    consecutive_errors = 0
    for i, case in enumerate(cases, 1):
        if case["as"] == "user" and not token:
            skipped.append(case["id"])
            continue
        body = {"message": case["question"], "history": case.get("history", []),
                "context": resolve_context(case, args.base_url, token)}
        start = time.monotonic()
        first_text = None
        try:
            events, first_text = stream_chat(f"{args.base_url}/api/chat/stream", body,
                                             token if case["as"] == "user" else None, start)
        except urllib.error.HTTPError as exc:
            events = [{"type": "error", "message": f"HTTP {exc.code}"}]
        except urllib.error.URLError as exc:
            sys.exit(f"Cannot reach {args.base_url}: {exc.reason}. Is the backend running?")
        result = {"id": case["id"], "category": case["category"], **score_case(case, events, time.monotonic() - start, first_text)}
        results.append(result)
        errors = [e for e in events if e.get("type") == "error"]
        consecutive_errors = consecutive_errors + 1 if errors else 0
        failed = [k for k, ok in result["checks"].items() if not ok]
        print(f"[{i:>2}/{len(cases)}] {'PASS' if result['passed'] else 'FAIL'} {case['id']:<28} "
              f"{result['seconds']:>5}s (first text {result['first_text_seconds'] or '-'}s)  "
              f"tools={','.join(result['tools']) or '-'}"
              + (f"  failed={','.join(failed)}" if failed else ""))
        if consecutive_errors >= 3:
            print(f"\nStopping: 3 errors in a row ({errors[0].get('message')}).")
            print("Check the backend log; an OpenAI rate or quota limit is the usual cause.")
            break
        time.sleep(args.delay)

    if not results:
        sys.exit("No cases ran.")
    passed = sum(r["passed"] for r in results)
    times = sorted(r["seconds"] for r in results)
    by_cat = {}
    for r in results:
        p, n = by_cat.get(r["category"], (0, 0))
        by_cat[r["category"]] = (p + r["passed"], n + 1)

    print(f"\nScore: {passed}/{len(results)} passed ({100 * passed / len(results):.0f}%)")
    firsts = sorted(r["first_text_seconds"] for r in results if r["first_text_seconds"] is not None)
    print(f"Full reply: median {times[len(times) // 2]}s, slowest {times[-1]}s")
    if firsts:
        print(f"First text appears: median {firsts[len(firsts) // 2]}s, slowest {firsts[-1]}s")
    for cat, (p, n) in sorted(by_cat.items()):
        print(f"  {cat:<10} {p}/{n}")
    if skipped:
        print(f"Skipped {len(skipped)} logged-in cases (run with --login): {', '.join(skipped)}")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    path = out / f"eval-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({"score": passed, "total": len(results),
                                "provider": os.getenv("CHAT_PROVIDER") or "openai",
                                "model": os.getenv("CHAT_MODEL") or os.getenv("OPENAI_CHAT_MODEL"),
                                "results": results},
                               ensure_ascii=False, indent=2))
    print(f"Details: {path}")


if __name__ == "__main__":
    main()
