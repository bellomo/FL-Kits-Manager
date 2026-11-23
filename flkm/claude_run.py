"""Running Claude Code for one task of the app, and what the app knows of its usage.

A task runs as `claude -p` (the prompt on stdin) with `--output-format stream-json`: the last event is the result (the
answer, the tokens used, a cost equivalent in dollars); a `rate_limit_event` before it says how much of the
subscription's usage limits (5-hour and 7-day windows) is used. The session is not saved, the task gets only the tools
it needs, and a time limit and a spending cap (`--max-budget-usd`) stop a run that goes wrong.

Every run is logged in <app data>/claude_runs.jsonl (no answers, nothing personal): the estimates of the next runs and
the last limits known come from it.
"""

import datetime
import json
import statistics
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

WINDOWS = {"five_hour": "5-hour", "seven_day": "7-day"}  # the usage windows of a subscription, as the app names them
REACHED_NAME = {"five_hour": "5 hours", "seven_day": "7 days"}
WARN_AT = 0.8  # a window used this much: the next run could reach its limit
LOG = "claude_runs.jsonl"


class ClaudeError(Exception):
    def __init__(self, message: str, limits=None):
        super().__init__(message)
        self.limits = limits


@dataclass(frozen=True)
class Account:
    logged_in: bool
    plan: str | None  # "Pro", "Max"... when signed in with a subscription

    def text(self) -> str:
        if not self.logged_in:
            return "not signed in"
        return self.plan or "signed in"


@dataclass(frozen=True)
class Task:
    kind: str  # what kind of work: runs of the same kind give the estimates
    what: str  # said to the user before the run
    prompt: str
    model: str  # alias: haiku, sonnet, opus
    tools: tuple[str, ...]  # the built-in tools it may use (none: it only answers)
    tokens: int  # estimate before the app has runs of this kind
    budget_usd: float  # spending cap of the run
    timeout: int  # seconds


@dataclass(frozen=True)
class Window:
    utilization: float  # 0..1 of the limit used
    resets_at: datetime.datetime
    status: str  # "allowed", "allowed_warning", "rejected"


@dataclass(frozen=True)
class Limits:
    five_hour: Window | None
    seven_day: Window | None
    checked: datetime.datetime  # when Claude Code said so


@dataclass(frozen=True)
class Done:
    kind: str
    text: str  # the answer (not kept in the log)
    model: str
    tokens: int  # input (with the cached context) and output
    cost_usd: float  # what the run would cost on the API: a measure, not a charge on a subscription
    when: datetime.datetime
    limits: Limits | None


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def account(cli, run: Callable = subprocess.run) -> Account | None:
    """whether Claude Code is signed in, and to which plan; None when it cannot tell"""
    try:
        done = run(
            [str(cli), "auth", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=_no_window(),
        )
        data = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    plan = data.get("subscriptionType")
    return Account(bool(data.get("loggedIn")), plan.capitalize() if isinstance(plan, str) and plan else None)


def minutes_text(seconds: int) -> str:
    n = max(1, round(seconds / 60))
    return f"{n} minute" if n == 1 else f"{n} minutes"


def _window(w: dict | None) -> Window | None:
    if not w:
        return None
    resets = datetime.datetime.fromtimestamp(w["resetsAt"], datetime.timezone.utc)
    return Window(float(w["utilization"]), resets, w.get("status", "allowed"))


def _limits(info: dict, when: datetime.datetime) -> Limits:
    windows = info.get("unifiedWindows", {})
    return Limits(_window(windows.get("five_hour")), _window(windows.get("seven_day")), when)


def _local(t: datetime.datetime) -> str:
    return t.astimezone().strftime("%d/%m %H:%M")


def _reached(limits: Limits | None) -> ClaudeError | None:
    for name in WINDOWS:
        w = getattr(limits, name) if limits else None
        if w and w.status == "rejected":
            return ClaudeError(
                f"Your Claude usage limit ({REACHED_NAME[name]}) is reached: it resets on {_local(w.resets_at)}.",
                limits,
            )
    return None


def _events(stdout: str) -> list[dict]:
    out = []
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            out.append(e)
    return out


def run_task(
    cli,
    task: Task,
    workdir: Path,
    model: str | None = None,
    run: Callable = subprocess.run,
    now: Callable[[], datetime.datetime] = _now,
) -> Done:
    """runs the task in workdir (model: instead of the task's); raises ClaudeError when it does not finish well"""
    args = [
        str(cli),
        "-p",
        "--model",
        model or task.model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--tools",
        ",".join(task.tools),
        "--max-budget-usd",
        f"{task.budget_usd:g}",
    ]
    if task.tools:  # in -p mode no one answers a permission prompt: the task's own tools (only them) are allowed
        args += ["--allowedTools", ",".join(task.tools)]
    try:
        done = run(
            args,
            input=task.prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=workdir,
            timeout=task.timeout,
            creationflags=_no_window(),
        )
    except subprocess.TimeoutExpired:
        raise ClaudeError(f"Claude did not finish within {minutes_text(task.timeout)}.") from None
    except OSError as e:
        raise ClaudeError(f"Claude Code could not be started: {e}") from None
    when = now()
    events = _events(done.stdout or "")
    limits = next((_limits(e["rate_limit_info"], when) for e in events if e.get("type") == "rate_limit_event"), None)
    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is None or result.get("is_error"):
        reached = _reached(limits)
        if reached:
            raise reached
        if result is not None:
            raise ClaudeError(f"Claude stopped: {result.get('result') or result.get('subtype')}", limits)
        last = [s for s in (done.stderr or "").splitlines() if s.strip()]
        raise ClaudeError(f"Claude Code stopped: {last[-1]}" if last else "Claude Code stopped without saying why.")
    denied = sorted({d.get("tool_name", "?") for d in result.get("permission_denials") or [] if isinstance(d, dict)})
    if denied:
        raise ClaudeError(
            f"Claude Code did not let Claude use {', '.join(denied)} (permission denied), so the task could not be "
            "done. Check the permissions in your Claude Code settings.",
            limits,
        )
    usage = result.get("usage", {})
    tokens = sum(
        int(usage.get(k, 0))
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    )
    by_model = (
        result.get("modelUsage") or {}
    )  # Claude Code also uses Haiku (to read web pages): the main one costs most
    used_model = max(by_model, key=lambda m: float((by_model[m] or {}).get("costUSD", 0)), default=model or task.model)
    return Done(
        task.kind, result.get("result", ""), used_model, tokens, float(result.get("total_cost_usd", 0)), when, limits
    )


# --- the log of runs -------------------------------------------------------------------------------------------------


def _window_dict(w: Window | None) -> dict | None:
    return {"utilization": w.utilization, "resets_at": w.resets_at.isoformat(), "status": w.status} if w else None


def _window_from(d: dict | None) -> Window | None:
    return Window(d["utilization"], datetime.datetime.fromisoformat(d["resets_at"]), d["status"]) if d else None


def log_run(home: Path, done: Done) -> None:
    lim = done.limits
    entry = {
        "when": done.when.isoformat(),
        "kind": done.kind,
        "model": done.model,
        "tokens": done.tokens,
        "cost_usd": done.cost_usd,
        "limits": (
            {
                "five_hour": _window_dict(lim.five_hour),
                "seven_day": _window_dict(lim.seven_day),
                "checked": lim.checked.isoformat(),
            }
            if lim
            else None
        ),
    }
    Path(home).mkdir(parents=True, exist_ok=True)
    with open(Path(home) / LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def runs(home: Path) -> list[Done]:
    """the runs logged, oldest first"""
    path = Path(home) / LOG
    out = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        try:
            e = json.loads(line)
            lim = e["limits"]
            limits = (
                Limits(
                    _window_from(lim["five_hour"]),
                    _window_from(lim["seven_day"]),
                    datetime.datetime.fromisoformat(lim["checked"]),
                )
                if lim
                else None
            )
            when = datetime.datetime.fromisoformat(e["when"])
            out.append(Done(e["kind"], "", e["model"], e["tokens"], e["cost_usd"], when, limits))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def estimate(done: list[Done], task: Task) -> int:
    """the tokens a task will use: the median of the last 10 runs of its kind (3 at least), else its own guess"""
    same = [d.tokens for d in done if d.kind == task.kind][-10:]
    return int(statistics.median(same)) if len(same) >= 3 else task.tokens


def used_since(done: list[Done], now: datetime.datetime, hours: int) -> int:
    start = now - datetime.timedelta(hours=hours)
    return sum(d.tokens for d in done if start <= d.when <= now)


def last_limits(done: list[Done]) -> Limits | None:
    return next((d.limits for d in reversed(done) if d.limits), None)


def limit_warning(limits: Limits | None, now: datetime.datetime) -> str | None:
    """a warning when the last limits known say the next run could hit one (a window reset since does not count)"""
    for name, label in WINDOWS.items():
        w = getattr(limits, name) if limits else None
        if not w or w.resets_at <= now:
            continue
        if w.status == "rejected" or w.utilization >= 1:
            return f"The {label} limit was reached: it resets on {_local(w.resets_at)}."
        if w.utilization >= WARN_AT:
            return f"The {label} limit was {w.utilization:.0%} used: this run could reach it."
    return None
