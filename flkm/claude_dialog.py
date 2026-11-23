"""The window shown before every Claude run: what it will do, the model, the tokens it should use (estimated from the
past runs of the same kind), what the app used in the last 5 hours and 7 days, the usage limits last known and a
warning when one is close. Claude runs only after Run."""

import datetime

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flkm import claude_run
from flkm.claude_run import Account, Done, Limits, Task

MODELS = {
    "haiku": "Haiku: fast, uses the least",
    "sonnet": "Sonnet: balanced",
    "opus": "Opus: the strongest, uses the most",
}


def _local(t: datetime.datetime) -> str:
    return t.astimezone().strftime("%d/%m %H:%M")


def limits_text(limits: Limits) -> str:
    parts = [
        f"{label}: {w.utilization:.0%} used, resets {_local(w.resets_at)}"
        for name, label in claude_run.WINDOWS.items()
        if (w := getattr(limits, name))
    ]
    return " · ".join(parts) + f" (as of {_local(limits.checked)})"


class ClaudeRunDialog(QDialog):
    def __init__(
        self,
        task: Task,
        account: Account | None,
        runs: list[Done],
        now: datetime.datetime,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Run Claude")
        self.setMinimumWidth(620)
        self.what = QLabel(task.what, wordWrap=True)
        self.what.setStyleSheet("font-weight: bold")
        self.model_box = QComboBox()
        for alias, text in MODELS.items():
            self.model_box.addItem(text, alias)
        self.model_box.setCurrentIndex(self.model_box.findData(task.model))
        self.model_box.setToolTip("The Claude model for this run: a stronger one uses more of your usage limits")
        same = [r for r in runs if r.kind == task.kind]
        tokens = claude_run.estimate(runs, task)
        how = (
            f"the median of your last {min(len(same), 10)} runs of this kind"
            if len(same) >= 3
            else "a first guess: no runs of this kind yet"
        )
        self.estimate = QLabel(f"About {tokens:,} tokens ({how})")
        five, week = claude_run.used_since(runs, now, 5), claude_run.used_since(runs, now, 24 * 7)
        self.used = QLabel(f"Last 5 hours: {five:,} tokens · last 7 days: {week:,} tokens")
        known = claude_run.last_limits(runs)
        self.limits = QLabel(
            limits_text(known) if known else "Not known yet: Claude Code says them at the end of each run.",
            wordWrap=True,
        )
        plan = f"Claude {account.plan}" if account and account.plan else "Claude"
        self.plan = QLabel(
            (
                f"Uses the usage limits of your {plan} subscription. The app cannot see how much is left right now: "
                "claude.ai → Settings → Usage shows it."
            ),
            wordWrap=True,
        )
        self.plan.setStyleSheet("color: gray")
        warning = claude_run.limit_warning(known, now)
        self.warning = QLabel(warning or "", wordWrap=True)
        self.warning.setStyleSheet("color: #e08000; font-weight: bold")
        self.warning.setVisible(bool(warning))
        form = QFormLayout()
        form.addRow("Model:", self.model_box)
        form.addRow("Estimated:", self.estimate)
        form.addRow("Used by this app:", self.used)
        form.addRow("Usage limits:", self.limits)
        self.run_button = QPushButton("Run")
        self.run_button.setToolTip("Start Claude now: the run uses your Claude usage limits")
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setToolTip("Do not run Claude: nothing is used")
        self.cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.what)
        layout.addLayout(form)
        layout.addWidget(self.plan)
        layout.addWidget(self.warning)
        layout.addLayout(buttons)

    def model(self) -> str:
        return self.model_box.currentData()
