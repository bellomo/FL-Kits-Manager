"""Running Claude Code for a task (claude -p, stream-json): what it answered, the tokens it used, the usage limits it
reported; the log of the app's runs, the estimates made from it. The real CLI is never run: the events below have the
shape Claude Code 2.1.330 prints."""

import datetime
import json
import subprocess
from pathlib import Path

import pytest

from flkm import claude_run
from fake_claude import LIMITS_EVENT, RESET_5H, RESET_7D, FakeClaude, lines, result_event
from flkm.claude_run import Limits, Task, Window

ACCOUNT, RUN_TASK = claude_run.account, claude_run.run_task  # the real ones: conftest's no_claude replaces them

T0 = datetime.datetime(2026, 11, 23, 15, 0, tzinfo=datetime.timezone.utc)


class FakeRun:
    def __init__(self, stdout="", code=0, stderr="", fail=None):
        self.stdout, self.code, self.stderr, self.fail, self.calls = stdout, code, stderr, fail, []

    def __call__(self, args, **kw):
        self.calls.append((args, kw))
        if self.fail:
            raise self.fail
        return subprocess.CompletedProcess(args, self.code, self.stdout, self.stderr)


TASK = Task("check", "Check the usage limits", "Reply with the single word ok.", "haiku", (), 5000, 0.05, 60)


# --- account ---------------------------------------------------------------------------------------------------------


def test_account_signed_in():
    status = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro", "email": "someone@example.com"}
    run = FakeRun(json.dumps(status))
    acct = ACCOUNT(Path("c.exe"), run=run)
    assert acct == claude_run.Account(True, "Pro")  # nothing personal is kept
    assert run.calls[0][0] == ["c.exe", "auth", "status", "--json"]


def test_account_not_signed_in_or_unknown():
    assert ACCOUNT("c", run=FakeRun(json.dumps({"loggedIn": False}))) == claude_run.Account(False, None)
    assert ACCOUNT("c", run=FakeRun("not json")) is None
    assert ACCOUNT("c", run=FakeRun("{}", code=1)) is None
    assert ACCOUNT("c", run=FakeRun(fail=OSError("gone"))) is None
    assert ACCOUNT("c", run=FakeRun(json.dumps(["x"]))) is None


def test_account_text():
    assert claude_run.Account(True, "Max").text() == "Max"
    assert claude_run.Account(True, None).text() == "signed in"
    assert claude_run.Account(False, None).text() == "not signed in"


# --- a run -----------------------------------------------------------------------------------------------------------


def test_run_a_task(tmp_path):
    run = FakeRun(lines({"type": "system", "subtype": "init"}, LIMITS_EVENT, result_event("ok")))
    done = RUN_TASK(Path("c.exe"), TASK, tmp_path, run=run, now=lambda: T0)
    assert done.text == "ok" and done.model == "claude-haiku-5-5" and done.tokens == 4696
    assert done.cost_usd == 0.00082 and done.when == T0
    assert done.limits == Limits(
        Window(0.24, datetime.datetime.fromtimestamp(RESET_5H, datetime.timezone.utc), "allowed"),
        Window(0.25, datetime.datetime.fromtimestamp(RESET_7D, datetime.timezone.utc), "allowed"),
        T0,
    )
    args, kw = run.calls[0]
    assert args[:2] == ["c.exe", "-p"] and kw["input"] == TASK.prompt and kw["cwd"] == tmp_path
    for pair in (
        ["--model", "haiku"],
        ["--output-format", "stream-json"],
        ["--tools", ""],
        ["--max-budget-usd", "0.05"],
    ):
        i = args.index(pair[0])
        assert args[i : i + 2] == pair
    assert "--verbose" in args and "--no-session-persistence" in args and kw["timeout"] == 60
    assert "--allowedTools" not in args  # no tools, nothing to allow


def test_run_with_tools_and_another_model(tmp_path):
    task = Task("logo", "Find a logo", "find it", "sonnet", ("WebSearch", "WebFetch"), 40000, 0.5, 300)
    run = FakeRun(lines(result_event("found")))
    done = RUN_TASK("c", task, tmp_path, model="opus", run=run, now=lambda: T0)
    args = run.calls[0][0]
    assert args[args.index("--tools") + 1] == "WebSearch,WebFetch" and args[args.index("--model") + 1] == "opus"
    assert args[args.index("--allowedTools") + 1] == "WebSearch,WebFetch"  # -p has no one to ask: allowed beforehand
    assert done.limits is None  # no limits event


def test_run_errors(tmp_path):
    def fails(run):
        with pytest.raises(claude_run.ClaudeError) as e:
            RUN_TASK("c", TASK, tmp_path, run=run, now=lambda: T0)
        return str(e.value)

    assert fails(FakeRun(fail=subprocess.TimeoutExpired("c", 60))) == "Claude did not finish within 1 minute."
    assert fails(FakeRun(fail=OSError("gone"))) == "Claude Code could not be started: gone"
    assert fails(FakeRun("", code=1, stderr="boom\nlast line")) == "Claude Code stopped: last line"
    assert fails(FakeRun("", code=1)) == "Claude Code stopped without saying why."
    assert fails(FakeRun(lines(result_event("Budget exceeded", error=True)))) == "Claude stopped: Budget exceeded"
    assert fails(FakeRun("garbage\n" + lines(LIMITS_EVENT))) == "Claude Code stopped without saying why."


def test_a_limit_reached_says_when_it_resets(tmp_path):
    reached = json.loads(json.dumps(LIMITS_EVENT))
    reached["rate_limit_info"]["unifiedWindows"]["five_hour"] = {
        "utilization": 1.0,
        "resetsAt": RESET_5H,
        "status": "rejected",
    }
    run = FakeRun(lines(reached, result_event("limit", error=True)), code=1)
    with pytest.raises(claude_run.ClaudeError) as e:
        RUN_TASK("c", TASK, tmp_path, run=run, now=lambda: T0)
    reset = datetime.datetime.fromtimestamp(RESET_5H).strftime("%d/%m %H:%M")
    assert str(e.value) == f"Your Claude usage limit (5 hours) is reached: it resets on {reset}."
    assert e.value.limits.five_hour.status == "rejected"


def test_time_text():
    assert claude_run.minutes_text(60) == "1 minute" and claude_run.minutes_text(300) == "5 minutes"


# --- the log of runs -------------------------------------------------------------------------------------------------


def done(when, tokens, kind="check", limits=None):
    return claude_run.Done(kind, "ok", "claude-haiku-5-5", tokens, 0.001, when, limits)


def test_the_runs_are_logged_and_read_back(home):
    lim = Limits(Window(0.24, T0, "allowed"), None, T0)
    claude_run.log_run(home, done(T0, 4696, limits=lim))
    claude_run.log_run(home, done(T0 + datetime.timedelta(hours=1), 5000, kind="logo"))
    runs = claude_run.runs(home)
    assert [(r.kind, r.tokens) for r in runs] == [("check", 4696), ("logo", 5000)]
    assert runs[0].limits == lim and runs[1].limits is None and runs[0].text == ""  # answers are not kept
    (home / "claude_runs.jsonl").write_text("not json\n" + (home / "claude_runs.jsonl").read_text(), encoding="utf-8")
    assert len(claude_run.runs(home)) == 2  # a damaged line is skipped
    assert claude_run.runs(home / "nowhere") == []


def test_estimate_from_past_runs():
    assert claude_run.estimate([], TASK) == 5000  # the task's own guess
    runs = [done(T0, n) for n in (4000, 9000, 6000)] + [done(T0, 99999, kind="logo")]
    assert claude_run.estimate(runs[:2], TASK) == 5000  # fewer than 3 runs of the kind
    assert claude_run.estimate(runs, TASK) == 6000  # their median


def test_tokens_used_in_a_window():
    runs = [done(T0 - datetime.timedelta(hours=h), 1000) for h in (1, 4, 30, 200)]
    assert claude_run.used_since(runs, T0, hours=5) == 2000
    assert claude_run.used_since(runs, T0, hours=24 * 7) == 3000


def test_last_limits_known():
    lim = Limits(Window(0.3, T0, "allowed"), None, T0)
    assert claude_run.last_limits([done(T0, 1, limits=lim), done(T0, 1)]) == lim
    assert claude_run.last_limits([done(T0, 1)]) is None


def test_limit_warning():
    soon = T0 + datetime.timedelta(hours=2)
    assert claude_run.limit_warning(None, T0) is None
    low = Limits(Window(0.24, soon, "allowed"), Window(0.25, soon, "allowed"), T0)
    assert claude_run.limit_warning(low, T0) is None
    high = Limits(Window(0.85, soon, "allowed"), Window(0.25, soon, "allowed"), T0)
    assert claude_run.limit_warning(high, T0) == "The 5-hour limit was 85% used: this run could reach it."
    gone = Limits(Window(1.0, soon, "rejected"), None, T0)
    assert claude_run.limit_warning(gone, T0).startswith("The 5-hour limit was reached")
    past = Limits(Window(1.0, T0 - datetime.timedelta(minutes=1), "rejected"), None, T0)
    assert claude_run.limit_warning(past, T0) is None  # reset since


def test_now_is_utc():
    assert claude_run._now().tzinfo is datetime.timezone.utc


def test_events_that_are_not_objects_and_a_window_missing(tmp_path):
    only_week = json.loads(json.dumps(LIMITS_EVENT))
    del only_week["rate_limit_info"]["unifiedWindows"]["five_hour"]
    run = FakeRun("[1, 2]\n" + lines(only_week, result_event("ok")))
    done = RUN_TASK("c", TASK, tmp_path, run=run, now=lambda: T0)
    assert done.limits.five_hour is None and done.limits.seven_day.utilization == 0.25


def test_a_run_on_the_fake_claude_code(tmp_path):
    """the whole stream the fake Claude Code prints, with its tool calls, read as the real one"""
    fake = FakeClaude(answer="found it")
    task = Task("logo", "Find a logo", "find it", "sonnet", ("WebSearch", "WebFetch"), 40000, 0.5, 300)
    done = RUN_TASK("c", task, tmp_path, run=fake, now=lambda: T0)
    assert done.text == "found it" and done.model == "claude-sonnet-5-5" and done.tokens == 4696 + 18000 + 800
    assert done.limits.five_hour.utilization == 0.24 and fake.runs[0]["tools"] == ["WebSearch", "WebFetch"]
    assert fake.runs[0]["allowed"] == ["WebSearch", "WebFetch"]
    assert ACCOUNT("c", run=fake) == claude_run.Account(True, "Pro")
    assert ACCOUNT("c", run=FakeClaude(knows_auth=False)) is None
    assert FakeClaude()(["c", "--nope"]).returncode == 1


def test_tools_denied_stop_the_run(tmp_path):
    """when Claude Code denies the task's tools (the user's own settings), the run says so instead of answering"""
    task = Task("logo", "Find a logo", "find it", "sonnet", ("WebSearch", "WebFetch"), 40000, 0.5, 300)
    with pytest.raises(claude_run.ClaudeError) as e:
        RUN_TASK("c", task, tmp_path, run=FakeClaude(deny=("WebFetch",)), now=lambda: T0)
    assert str(e.value) == (
        "Claude Code did not let Claude use WebFetch (permission denied), so the task could not be done. "
        "Check the permissions in your Claude Code settings."
    )
    assert e.value.limits.five_hour.utilization == 0.24
