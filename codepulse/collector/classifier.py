"""Activity Classifier for CodePulse.

Categorizes foreground window activity into productivity categories
using deterministic rules matched against process names and window titles.

All matching is case-insensitive. Rules are defined as simple lists
so students can easily add new applications or websites.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple


class Category(Enum):
    """Activity categories for window classification."""

    CODING = "Coding"
    DOCUMENTATION = "Documentation"
    COMMUNICATION = "Communication"
    DISTRACTION = "Distraction"
    OTHER = "Other"
    IDLE = "Idle"


@dataclass(frozen=True)
class ClassificationResult:
    """Immutable result of classifying a window observation."""

    category: Category
    matched_rule: str  # Human-readable description of why this category was chosen

    @property
    def is_productive(self) -> bool:
        """Returns True for categories considered productive work."""
        return self.category in (Category.CODING, Category.DOCUMENTATION)


# ---------------------------------------------------------------------------
# Classification Rules
#
# Each rule set is a list of (pattern, description) tuples.
# Patterns are matched case-insensitively against process names or titles.
# ---------------------------------------------------------------------------

# Rules matched against the PROCESS NAME (e.g. "Code.exe", "pycharm64.exe")
PROCESS_RULES: List[Tuple[str, Category, str]] = [
    # Coding — IDEs and editors
    ("code", Category.CODING, "Visual Studio Code"),
    ("cursor", Category.CODING, "Cursor editor"),
    ("pycharm", Category.CODING, "PyCharm IDE"),
    ("idea", Category.CODING, "IntelliJ IDEA"),
    ("webstorm", Category.CODING, "WebStorm IDE"),
    ("devenv", Category.CODING, "Visual Studio"),
    ("sublime_text", Category.CODING, "Sublime Text"),
    ("notepad++", Category.CODING, "Notepad++"),
    ("atom", Category.CODING, "Atom editor"),
    # Coding — Terminals
    ("windowsterminal", Category.CODING, "Windows Terminal"),
    ("powershell", Category.CODING, "PowerShell"),
    ("pwsh", Category.CODING, "PowerShell Core"),
    ("cmd", Category.CODING, "Command Prompt"),
    ("mintty", Category.CODING, "Git Bash / MinTTY"),
    ("wt", Category.CODING, "Windows Terminal (wt)"),
    ("alacritty", Category.CODING, "Alacritty terminal"),
    ("wezterm", Category.CODING, "WezTerm terminal"),
    # Communication
    ("discord", Category.COMMUNICATION, "Discord"),
    ("slack", Category.COMMUNICATION, "Slack"),
    ("teams", Category.COMMUNICATION, "Microsoft Teams"),
    ("telegram", Category.COMMUNICATION, "Telegram"),
    ("whatsapp", Category.COMMUNICATION, "WhatsApp"),
    ("outlook", Category.COMMUNICATION, "Microsoft Outlook"),
    ("thunderbird", Category.COMMUNICATION, "Thunderbird email"),
]

# Rules matched against the WINDOW TITLE (e.g. "main.py - VS Code", "Stack Overflow")
# These catch browser tabs and other title-based context.
TITLE_RULES: List[Tuple[str, Category, str]] = [
    # Documentation & Research
    ("stack overflow", Category.DOCUMENTATION, "Stack Overflow"),
    ("stackoverflow", Category.DOCUMENTATION, "Stack Overflow"),
    ("github.com", Category.DOCUMENTATION, "GitHub"),
    ("github", Category.DOCUMENTATION, "GitHub"),
    ("gitlab", Category.DOCUMENTATION, "GitLab"),
    ("docs.python.org", Category.DOCUMENTATION, "Python docs"),
    ("developer.mozilla", Category.DOCUMENTATION, "MDN Web Docs"),
    ("mdn web docs", Category.DOCUMENTATION, "MDN Web Docs"),
    ("devdocs", Category.DOCUMENTATION, "DevDocs"),
    ("read the docs", Category.DOCUMENTATION, "ReadTheDocs"),
    ("readthedocs", Category.DOCUMENTATION, "ReadTheDocs"),
    ("geeksforgeeks", Category.DOCUMENTATION, "GeeksForGeeks"),
    ("w3schools", Category.DOCUMENTATION, "W3Schools"),
    ("learn.microsoft", Category.DOCUMENTATION, "Microsoft Learn"),
    ("microsoft learn", Category.DOCUMENTATION, "Microsoft Learn"),
    ("docs.microsoft", Category.DOCUMENTATION, "Microsoft Docs"),
    ("medium.com", Category.DOCUMENTATION, "Medium (tech articles)"),
    ("dev.to", Category.DOCUMENTATION, "DEV Community"),
    ("hashnode", Category.DOCUMENTATION, "Hashnode blog"),
    ("documentation", Category.DOCUMENTATION, "Documentation page"),
    ("api reference", Category.DOCUMENTATION, "API reference"),
    # Distraction
    ("youtube.com", Category.DISTRACTION, "YouTube"),
    ("youtube", Category.DISTRACTION, "YouTube"),
    ("reddit.com", Category.DISTRACTION, "Reddit"),
    ("reddit", Category.DISTRACTION, "Reddit"),
    ("twitter.com", Category.DISTRACTION, "Twitter/X"),
    ("x.com", Category.DISTRACTION, "X (Twitter)"),
    ("instagram", Category.DISTRACTION, "Instagram"),
    ("facebook", Category.DISTRACTION, "Facebook"),
    ("tiktok", Category.DISTRACTION, "TikTok"),
    ("netflix", Category.DISTRACTION, "Netflix"),
    ("twitch.tv", Category.DISTRACTION, "Twitch"),
    # Communication (browser-based)
    ("discord", Category.COMMUNICATION, "Discord (browser)"),
    ("slack", Category.COMMUNICATION, "Slack (browser)"),
    ("teams.microsoft", Category.COMMUNICATION, "Teams (browser)"),
    ("mail.google", Category.COMMUNICATION, "Gmail"),
    ("outlook.live", Category.COMMUNICATION, "Outlook web"),
]


def classify(
    process_name: str,
    window_title: str,
    is_idle: bool = False,
) -> ClassificationResult:
    """Classify a window observation into a productivity category.

    The classifier checks rules in this priority order:
    1. If is_idle is True, immediately return IDLE.
    2. Match process name against PROCESS_RULES.
    3. Match window title against TITLE_RULES.
    4. If no rules match, return OTHER.

    Args:
        process_name: Executable name (e.g. "Code.exe").
        window_title: Window title text (e.g. "main.py - Visual Studio Code").
        is_idle: Whether the user is currently idle.

    Returns:
        ClassificationResult with the assigned category and matched rule.
    """
    # 1. Idle state takes top priority
    if is_idle:
        return ClassificationResult(
            category=Category.IDLE,
            matched_rule="User is idle",
        )

    proc_lower = process_name.lower() if process_name else ""
    title_lower = window_title.lower() if window_title else ""

    # 2. Check process name rules
    for pattern, category, description in PROCESS_RULES:
        if pattern in proc_lower:
            return ClassificationResult(
                category=category,
                matched_rule=f"Process: {description}",
            )

    # 3. Check window title rules
    for pattern, category, description in TITLE_RULES:
        if pattern in title_lower:
            return ClassificationResult(
                category=category,
                matched_rule=f"Title: {description}",
            )

    # 4. No match — classify as OTHER
    return ClassificationResult(
        category=Category.OTHER,
        matched_rule="No matching rule",
    )


class ActivityClassifier:
    """Classifier interface wrapping the classify function.

    Provides the same rule-based classification with an object-oriented
    interface for consistency with WindowSensor and IdleSensor.
    """

    @staticmethod
    def classify(
        process_name: str,
        window_title: str,
        is_idle: bool = False,
    ) -> ClassificationResult:
        """Classify activity. See module-level classify() for details."""
        return classify(process_name, window_title, is_idle)
