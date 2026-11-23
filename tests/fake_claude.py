"""A fake Claude Code CLI for the tests: it stands in for subprocess.run and answers what Claude Code 2.1.330 answers
(`--version`, `auth status --json`, and `-p ... --output-format stream-json --verbose` with its stream of events:
system init, rate limits, tool calls, the assistant's text, the result). The app's own code reads its output, as it
reads the real one; the real Claude Code is never run.

    fake = FakeClaude(answer="...")         # what Claude would answer
    use_fake_claude(monkeypatch, fake)      # the app finds it, reads its account and runs its tasks on it
    fake.runs[-1]["tools"], fake.runs[-1]["prompt"]   # what the app asked
"""

import json
import subprocess
from pathlib import Path

from flkm import claude, claude_run

VERSION = "2.1.330"
PATH = Path("C:/tools/claude.exe")
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
RESET_5H, RESET_7D = 1795457400, 1795982400  # epoch seconds, as Claude Code says them
USAGE = {"input_tokens": 2, "cache_creation_input_tokens": 4041, "cache_read_input_tokens": 649, "output_tokens": 4}

# the real functions, taken before conftest's no_claude replaces them in every test
_VERSION_OF, _ACCOUNT, _RUN_TASK = claude.version, claude_run.account, claude_run.run_task


def limits_event(five=0.24, week=0.25, five_status="allowed", week_status="allowed") -> dict:
    return {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed_warning",
            "resetsAt": RESET_7D,
            "rateLimitType": "seven_day",
            "utilization": week,
            "unifiedWindows": {
                "five_hour": {"utilization": five, "resetsAt": RESET_5H, "status": five_status},
                "seven_day": {"utilization": week, "resetsAt": RESET_7D, "status": week_status},
            },
        },
        "uuid": "00000000-0000-0000-0000-000000000001",
        "session_id": "00000000-0000-0000-0000-000000000000",
    }


LIMITS_EVENT = limits_event()


def result_event(text="ok", error=False, model="claude-haiku-5-5", usage=None, cost=0.00082, **kw) -> dict:
    return {
        "type": "result",
        "subtype": "error_during_execution" if error else "success",
        "is_error": error,
        "duration_ms": 2310,
        "num_turns": 1,
        "result": text,
        "session_id": "00000000-0000-0000-0000-000000000000",
        "total_cost_usd": cost,
        "usage": usage or USAGE,
        "modelUsage": {model: {"inputTokens": 2, "outputTokens": 4, "costUSD": cost}},
        **kw,
    }


def lines(*events) -> str:
    return "".join(json.dumps(e) + "\n" for e in events)


def _arg(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args else None


class FakeClaude:
    """answers like Claude Code; every call is kept in `calls`, every -p run in `runs` (model, tools, budget, prompt)

    answer: the assistant's final text; plan/logged_in: `auth status`; five/week: usage of the limits windows;
    limit_reached: the 5-hour window is used up (the run stops, as the real one does); error: the run ends with
    is_error and this text; fail: an exception the program raises instead of running (not installed, time out);
    knows_auth=False: an older Claude Code without `auth status`; deny: tools the user's own settings deny.

    Like the real one in -p mode, a tool made available with --tools but not allowed with --allowedTools is denied (no
    one is there to answer the permission prompt): Claude then answers without it, and the result lists the denials."""

    def __init__(
        self,
        answer="ok",
        plan="pro",
        logged_in=True,
        five=0.24,
        week=0.25,
        limit_reached=False,
        error=None,
        fail=None,
        knows_auth=True,
        deny=(),
    ):
        self.deny = tuple(deny)
        self.knows_auth = knows_auth
        self.answer, self.plan, self.logged_in = answer, plan, logged_in
        self.five, self.week, self.limit_reached, self.error, self.fail = five, week, limit_reached, error, fail
        self.calls, self.runs = [], []

    def __call__(self, args, **kw):
        args = [str(a) for a in args]
        self.calls.append((args, kw))
        if self.fail:
            raise self.fail
        if args[1:] == ["--version"]:
            return self._done(args, f"{VERSION} (Claude Code)\n")
        if args[1:] == ["auth", "status", "--json"] and self.knows_auth:
            return self._done(args, json.dumps(self._status(), indent=2) + "\n")
        if "-p" in args:
            return self._print(args, kw)
        return self._done(args, "", code=1, stderr=f"error: unknown option '{args[1]}'\n")

    def _done(self, args, stdout, code=0, stderr=""):
        return subprocess.CompletedProcess(args, code, stdout, stderr)

    def _status(self) -> dict:
        if not self.logged_in:
            return {"loggedIn": False}
        return {
            "loggedIn": True,
            "authMethod": "claude.ai",
            "apiProvider": "firstParty",
            "email": "someone@example.com",  # the real one says the account's email: the app must not keep it
            "orgId": "00000000-0000-0000-0000-00000000000a",
            "subscriptionType": self.plan,
        }

    def _print(self, args, kw):
        model = MODELS.get(_arg(args, "--model"), _arg(args, "--model"))
        tools = [t for t in (_arg(args, "--tools") or "").split(",") if t]
        allowed = [t for t in (_arg(args, "--allowedTools") or "").split(",") if t and t not in self.deny]
        self.runs.append(
            {
                "model": model,
                "tools": tools,
                "allowed": allowed,
                "budget": _arg(args, "--max-budget-usd"),
                "prompt": kw.get("input"),
            }
        )
        events = [
            {
                "type": "system",
                "subtype": "init",
                "cwd": str(kw.get("cwd")),
                "session_id": "00000000-0000-0000-0000-000000000000",
                "tools": tools,
                "mcp_servers": [],
                "model": model,
                "permissionMode": "default",
                "claude_code_version": VERSION,
            }
        ]
        if self.limit_reached:
            events += [
                limits_event(1.0, self.week, five_status="rejected"),
                result_event("Claude AI usage limit reached", error=True, model=model),
            ]
            return self._done(args, lines(*events), code=1)
        events.append(limits_event(self.five, self.week))
        denials = []
        for n, tool in enumerate(tools, 1):  # a task with tools uses each once, like a web search then a fetch
            use = f"toolu_{n:02d}"
            ok = tool in allowed
            if not ok:
                denials.append({"tool_name": tool, "tool_use_id": use, "tool_input": {"query": "..."}})
            said = "..." if ok else f"Claude requested permissions to use {tool}, but you haven't granted it yet."
            events += [
                _assistant(model, [{"type": "tool_use", "id": use, "name": tool, "input": {"query": "..."}}]),
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": use, "content": said, "is_error": not ok}],
                    },
                },
            ]
        text = self.error or (
            self.answer
            if not denials
            else "[]\n\nI could not search: the web tools were denied (permission not granted)."
        )
        events.append(_assistant(model, [{"type": "text", "text": text}]))
        usage = dict(USAGE, input_tokens=2 + 9000 * len(tools), output_tokens=4 + 400 * len(tools))
        result = result_event(
            text, error=bool(self.error), model=model, usage=usage, num_turns=1 + len(tools), cost=0.0123
        )
        result["permission_denials"] = denials
        if tools:  # Claude Code summarises the pages fetched with Haiku: it comes first in modelUsage
            result["modelUsage"] = {
                "claude-haiku-5-5": {"inputTokens": 3000, "outputTokens": 200, "costUSD": 0.004},
                model: {"inputTokens": 6000, "outputTokens": 400, "costUSD": 0.0083},
            }
        events.append(result)
        return self._done(args, lines(*events), code=1 if self.error else 0)


def _assistant(model: str, content: list) -> dict:
    return {
        "type": "assistant",
        "message": {"model": model, "role": "assistant", "content": content, "usage": USAGE},
        "session_id": "00000000-0000-0000-0000-000000000000",
    }


def use_fake_claude(monkeypatch, fake: FakeClaude, now=None) -> None:
    """the app finds the fake Claude Code, reads its account and runs its tasks on it (through its real code)"""
    monkeypatch.setattr(claude, "find", lambda saved: claude.Cli(PATH, _VERSION_OF(PATH, run=fake), "desktop app"))
    monkeypatch.setattr(claude, "check", lambda path: claude.Cli(Path(path), _VERSION_OF(path, run=fake), "chosen"))
    monkeypatch.setattr(claude_run, "account", lambda cli: _ACCOUNT(cli, run=fake))

    def run_task(cli, task, workdir, model=None):
        return _RUN_TASK(cli, task, workdir, model, run=fake, **({"now": now} if now else {}))

    monkeypatch.setattr(claude_run, "run_task", run_task)
