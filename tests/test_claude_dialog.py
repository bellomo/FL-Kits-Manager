"""The window shown before every Claude run: what it will do, the model, the tokens it should use, what the app used
lately, the usage limits last known and a warning when one is close. Nothing runs until Run."""

import datetime

from conftest import buttons_without_tooltip
from flkm.claude_dialog import ClaudeRunDialog, limits_text
from flkm.claude_run import Account, Done, Limits, Task, Window

NOW = datetime.datetime(2026, 11, 23, 15, 0, tzinfo=datetime.timezone.utc)
TASK = Task("logo", "Find the crest of Test FC on the web", "...", "sonnet", ("WebSearch",), 40000, 0.5, 300)


def at(hours_ago, tokens=1000, kind="logo", limits=None):
    return Done(kind, "", "claude-sonnet-5-5", tokens, 0.01, NOW - datetime.timedelta(hours=hours_ago), limits)


def local(t):
    return t.astimezone().strftime("%d/%m %H:%M")


LOW = Limits(
    Window(0.24, NOW + datetime.timedelta(hours=2), "allowed"),
    Window(0.25, NOW + datetime.timedelta(days=3), "allowed"),
    NOW - datetime.timedelta(hours=1),
)


def make(qtbot, runs=(), account=Account(True, "Pro")):
    d = ClaudeRunDialog(TASK, account, list(runs), NOW)
    qtbot.addWidget(d)
    return d


def test_what_and_the_model(qtbot):
    d = make(qtbot)
    assert d.what.text() == "Find the crest of Test FC on the web"
    assert d.model() == "sonnet" and d.model_box.count() == 3
    d.model_box.setCurrentIndex(d.model_box.findData("haiku"))
    assert d.model() == "haiku"


def test_first_guess_without_runs(qtbot):
    d = make(qtbot)
    assert d.estimate.text() == "About 40,000 tokens (a first guess: no runs of this kind yet)"
    assert d.used.text() == "Last 5 hours: 0 tokens · last 7 days: 0 tokens"
    assert d.limits.text() == "Not known yet: Claude Code says them at the end of each run."
    assert not d.warning.isVisibleTo(d)


def test_from_the_runs_logged(qtbot):
    runs = [at(1, 30000), at(2, 50000), at(30, 20000, limits=LOW), at(400, 99999, kind="check")]
    d = make(qtbot, runs)
    assert d.estimate.text() == "About 30,000 tokens (the median of your last 3 runs of this kind)"
    assert d.used.text() == "Last 5 hours: 80,000 tokens · last 7 days: 100,000 tokens"
    assert d.limits.text() == limits_text(LOW)
    assert "Pro" in d.plan.text() and "claude.ai" in d.plan.text()


def test_limits_text():
    assert limits_text(LOW) == (
        f"5-hour: 24% used, resets {local(LOW.five_hour.resets_at)} · "
        f"7-day: 25% used, resets {local(LOW.seven_day.resets_at)} (as of {local(LOW.checked)})"
    )
    only = Limits(None, LOW.seven_day, LOW.checked)
    assert limits_text(only).startswith("7-day: 25% used")


def test_a_limit_close_is_a_warning(qtbot):
    high = Limits(Window(0.9, NOW + datetime.timedelta(hours=1), "allowed"), None, NOW)
    d = make(qtbot, [at(1, limits=high)])
    assert d.warning.isVisibleTo(d) and d.warning.text() == "The 5-hour limit was 90% used: this run could reach it."


def test_a_plan_unknown(qtbot):
    d = make(qtbot, account=None)
    assert d.plan.text().startswith("Uses the usage limits of your Claude subscription")


def test_run_and_cancel(qtbot):
    d = make(qtbot)
    d.run_button.click()
    assert d.result() == ClaudeRunDialog.Accepted
    d = make(qtbot)
    d.cancel_button.click()
    assert d.result() == ClaudeRunDialog.Rejected


def test_every_button_has_a_tooltip(qtbot):
    assert buttons_without_tooltip(make(qtbot)) == []
