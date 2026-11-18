"""The chatbot evaluation set is valid, and its scoring works (no OpenAI calls)."""
import json
from pathlib import Path

from chat_eval.run_eval import parse_sse, score_case
from services.chatbot_tools import TOOLS

CASES = json.loads((Path(__file__).resolve().parent.parent / "chat_eval" / "cases.json").read_text())["cases"]
CATEGORIES = {"search", "details", "context", "reviews", "recommend", "bookings", "guest", "policy", "language", "safety"}
KEYS = {"id", "category", "as", "question", "context", "history", "expect_tools_any", "expect_no_tools",
        "must_contain_any", "must_not_contain", "language"}


def test_cases_are_valid():
    assert len(CASES) >= 40
    assert len({c["id"] for c in CASES}) == len(CASES), "duplicate case ids"
    for c in CASES:
        assert set(c) <= KEYS, f"{c['id']}: unknown keys {set(c) - KEYS}"
        assert c["category"] in CATEGORIES and c["as"] in ("guest", "user")
        assert 0 < len(c["question"]) <= 500
        assert set(c.get("expect_tools_any", [])) <= set(TOOLS), f"{c['id']}: unknown tool"
        assert not (c.get("expect_tools_any") and c.get("expect_no_tools")), f"{c['id']}: contradictory"
        assert c.get("language") in (None, "en", "hi", "gu")


def test_every_tool_and_category_is_covered():
    used = {t for c in CASES for t in c.get("expect_tools_any", [])}
    assert used == set(TOOLS)
    assert {c["category"] for c in CASES} == CATEGORIES


def _events(text, tools=(), error=False):
    ev = [{"type": "status", "tool": t, "text": "…"} for t in tools]
    ev.append({"type": "error", "message": "x"} if error else {"type": "delta", "text": text})
    return ev + [{"type": "done"}]


def test_score_passes_a_good_answer():
    case = {"expect_tools_any": ["search_shows"], "must_contain_any": ["avengers"]}
    r = score_case(case, _events("Avengers: [Book now](/shows/abc)", ["search_shows"]), 3.2)
    assert r["passed"] and r["tools"] == ["search_shows"] and r["seconds"] == 3.2


def test_score_catches_each_kind_of_failure():
    assert score_case({"expect_tools_any": ["get_my_bookings"]}, _events("hi", ["search_shows"]), 1)["checks"]["tools"] is False
    assert score_case({"expect_no_tools": True}, _events("hi", ["search_shows"]), 1)["checks"]["no_tools"] is False
    assert score_case({"must_not_contain": ["paris"]}, _events("It is Paris"), 1)["checks"]["not_contains"] is False
    assert score_case({"language": "hi"}, _events("Hello"), 1)["checks"]["language"] is False
    assert score_case({"language": "gu"}, _events("નમસ્તે"), 1)["checks"]["language"] is True
    assert score_case({}, _events("see [x](https://evil.example)"), 1)["checks"]["in_app_links"] is False
    assert score_case({}, _events("", error=True), 1)["passed"] is False


def test_parse_sse():
    raw = 'data: {"type": "delta", "text": "a"}\n\ndata: {"type": "done"}\n\n'
    assert parse_sse(raw) == [{"type": "delta", "text": "a"}, {"type": "done"}]


def test_score_fails_a_cut_off_reply():
    events = [{"type": "delta", "text": "Here are the screenings: -"}, {"type": "done", "truncated": True}]
    r = score_case({}, events, 1)
    assert r["checks"]["complete"] is False and r["passed"] is False


def test_score_keeps_first_text_time():
    r = score_case({}, [{"type": "delta", "text": "hi"}, {"type": "done"}], 9.94, first_text=2.04)
    assert r["seconds"] == 9.9 and r["first_text_seconds"] == 2.0
