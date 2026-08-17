"""Tests for the Activity Classifier."""

import pytest

from codepulse.collector.classifier import (
    Category,
    ClassificationResult,
    ActivityClassifier,
    classify,
)


# ---------------------------------------------------------------------------
# ClassificationResult data structure tests
# ---------------------------------------------------------------------------

def test_classification_result_is_frozen():
    """ClassificationResult should be immutable."""
    result = ClassificationResult(category=Category.CODING, matched_rule="test")
    with pytest.raises(Exception):
        result.category = Category.OTHER  # type: ignore


def test_is_productive_for_coding():
    """CODING is productive."""
    result = ClassificationResult(category=Category.CODING, matched_rule="test")
    assert result.is_productive is True


def test_is_productive_for_documentation():
    """DOCUMENTATION is productive."""
    result = ClassificationResult(category=Category.DOCUMENTATION, matched_rule="test")
    assert result.is_productive is True


@pytest.mark.parametrize("cat", [Category.COMMUNICATION, Category.DISTRACTION, Category.OTHER, Category.IDLE])
def test_is_productive_false_for_non_work(cat):
    """COMMUNICATION, DISTRACTION, OTHER, and IDLE are not productive."""
    result = ClassificationResult(category=cat, matched_rule="test")
    assert result.is_productive is False


# ---------------------------------------------------------------------------
# IDLE state tests
# ---------------------------------------------------------------------------

def test_idle_state_overrides_everything():
    """When is_idle=True, the result is always IDLE regardless of process/title."""
    result = classify("Code.exe", "main.py - Visual Studio Code", is_idle=True)
    assert result.category == Category.IDLE
    assert "idle" in result.matched_rule.lower()


def test_idle_state_with_empty_inputs():
    """IDLE works even with empty process name and title."""
    result = classify("", "", is_idle=True)
    assert result.category == Category.IDLE


# ---------------------------------------------------------------------------
# Process name classification tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("process_name, expected_category", [
    ("Code.exe", Category.CODING),
    ("cursor.exe", Category.CODING),
    ("pycharm64.exe", Category.CODING),
    ("idea64.exe", Category.CODING),
    ("devenv.exe", Category.CODING),
    ("sublime_text.exe", Category.CODING),
    ("WindowsTerminal.exe", Category.CODING),
    ("powershell.exe", Category.CODING),
    ("pwsh.exe", Category.CODING),
    ("cmd.exe", Category.CODING),
    ("mintty.exe", Category.CODING),
    ("discord.exe", Category.COMMUNICATION),
    ("Slack.exe", Category.COMMUNICATION),
    ("Teams.exe", Category.COMMUNICATION),
    ("Telegram.exe", Category.COMMUNICATION),
    ("outlook.exe", Category.COMMUNICATION),
])
def test_process_name_rules(process_name, expected_category):
    """Known applications are classified by process name."""
    result = classify(process_name, "")
    assert result.category == expected_category


def test_unknown_process_returns_other():
    """An unrecognized process with no matching title returns OTHER."""
    result = classify("mystery_app.exe", "Some Random Window")
    assert result.category == Category.OTHER
    assert "no matching" in result.matched_rule.lower()


# ---------------------------------------------------------------------------
# Window title classification tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title, expected_category", [
    ("How to parse JSON in Python - Stack Overflow - Google Chrome", Category.DOCUMENTATION),
    ("codepulse-ai - GitHub - Mozilla Firefox", Category.DOCUMENTATION),
    ("Array.prototype.map() - JavaScript | MDN Web Docs", Category.DOCUMENTATION),
    ("Welcome to Python.org — docs.python.org", Category.DOCUMENTATION),
    ("DevDocs — Python 3.12", Category.DOCUMENTATION),
    ("Read the Docs", Category.DOCUMENTATION),
    ("API Reference - FastAPI", Category.DOCUMENTATION),
    ("GeeksforGeeks - DSA", Category.DOCUMENTATION),
    ("Microsoft Learn", Category.DOCUMENTATION),
    ("Funny Cat Video - YouTube", Category.DISTRACTION),
    ("r/python - Reddit", Category.DISTRACTION),
    ("Home / X.com", Category.DISTRACTION),
    ("twitter.com - notifications", Category.DISTRACTION),
    ("Instagram", Category.DISTRACTION),
    ("Netflix", Category.DISTRACTION),
    ("Discord | #general", Category.COMMUNICATION),
    ("Slack | codepulse-team", Category.COMMUNICATION),
    ("mail.google.com - Inbox", Category.COMMUNICATION),
])
def test_title_rules(title, expected_category):
    """Browser tabs and titled windows are classified by title patterns."""
    result = classify("chrome.exe", title)
    assert result.category == expected_category


# ---------------------------------------------------------------------------
# Case-insensitivity tests
# ---------------------------------------------------------------------------

def test_process_name_case_insensitive():
    """Process name matching is case-insensitive."""
    assert classify("CODE.EXE", "").category == Category.CODING
    assert classify("code.exe", "").category == Category.CODING
    assert classify("Code.Exe", "").category == Category.CODING


def test_title_case_insensitive():
    """Title matching is case-insensitive."""
    assert classify("chrome.exe", "STACK OVERFLOW - Python").category == Category.DOCUMENTATION
    assert classify("chrome.exe", "stack overflow - python").category == Category.DOCUMENTATION
    assert classify("chrome.exe", "Stack Overflow - Python").category == Category.DOCUMENTATION


# ---------------------------------------------------------------------------
# Priority tests (process rules come before title rules)
# ---------------------------------------------------------------------------

def test_process_rule_takes_priority_over_title():
    """If process matches CODING but title matches DISTRACTION, CODING wins."""
    result = classify("Code.exe", "youtube.com - Google Chrome")
    assert result.category == Category.CODING
    assert "process" in result.matched_rule.lower()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_process_and_title():
    """Empty process and title with no idle flag returns OTHER."""
    result = classify("", "")
    assert result.category == Category.OTHER


def test_none_like_process_name():
    """Process name 'Unknown' (from window_sensor fallback) returns OTHER if no title match."""
    result = classify("Unknown", "Untitled Window")
    assert result.category == Category.OTHER


def test_matched_rule_is_descriptive():
    """The matched_rule field provides human-readable context."""
    result = classify("Code.exe", "main.py")
    assert "Visual Studio Code" in result.matched_rule

    result = classify("chrome.exe", "Stack Overflow - Python")
    assert "Stack Overflow" in result.matched_rule


# ---------------------------------------------------------------------------
# ActivityClassifier class interface
# ---------------------------------------------------------------------------

def test_activity_classifier_class():
    """ActivityClassifier.classify delegates to the module function."""
    result = ActivityClassifier.classify("Code.exe", "main.py")
    assert result.category == Category.CODING

    result = ActivityClassifier.classify("", "", is_idle=True)
    assert result.category == Category.IDLE
