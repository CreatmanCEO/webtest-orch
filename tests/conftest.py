"""Shared pytest fixtures for webtest-orch tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Make `scripts/*.py` importable as `import detect_state`, `import fingerprint_bugs`, etc.
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


import pytest  # noqa: E402


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def scripts_dir() -> Path:
    return SCRIPTS_DIR


@pytest.fixture
def sample_playwright_results() -> dict:
    """Minimal Playwright JSON reporter output with 1 failure."""
    return {
        "stats": {"expected": 5, "unexpected": 1, "skipped": 0, "flaky": 0},
        "suites": [
            {
                "title": "Landing",
                "specs": [
                    {
                        "title": "home loads",
                        "file": "tests/specs/landing.spec.ts",
                        "tests": [
                            {
                                "projectName": "chromium-mobile",
                                "results": [
                                    {
                                        "status": "failed",
                                        "duration": 1234,
                                        "retry": 0,
                                        "error": {
                                            "message": "\x1b[2mError: 2 issues found:\x1b[22m\n  - a11y[serious] color-contrast: text fails (3x nodes)\n  - touch-target: BUTTON:\"X\" 20x20\n\nReceived: ['a', 'b']",
                                            "stack": "at /path/landing.spec.ts:5:3",
                                            "snippet": "expect(issues).toEqual([])",
                                            "location": {"file": "tests/specs/landing.spec.ts", "line": 5},
                                        },
                                        "attachments": [
                                            {
                                                "name": "screenshot",
                                                "contentType": "image/png",
                                                "path": "/tmp/test-results/screenshot.png",
                                            },
                                            {
                                                "name": "trace",
                                                "contentType": "application/zip",
                                                "path": "/tmp/test-results/trace.zip",
                                            },
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "suites": [],
            }
        ],
    }


@pytest.fixture
def sample_raw_bugs() -> dict:
    return {
        "runId": "run-test-1",
        "stats": {"unexpected": 1, "expected": 4},
        "bugs": [
            {
                "title": "Auth > rejects invalid creds",
                "specFile": "tests/specs/auth.spec.ts",
                "specTitle": "rejects invalid creds",
                "project": "chromium-desktop",
                "status": "failed",
                "issueLine": "a11y[serious] color-contrast: text fails (3x nodes)",
                "error": {
                    "message": "TimeoutError: timeout 10000ms",
                    "stack": "",
                    "snippet": "await page.getByRole('button').click()",
                    "location": {"file": "/checkout/123", "line": 42},
                },
                "discoveredAt": "2026-04-29T08:00:00Z",
                "firstSeenRunId": "run-test-1",
                "lastSeenRunId": "run-test-1",
                "occurrenceCount": 1,
            },
        ],
    }


@pytest.fixture
def sample_console_messages() -> list[dict]:
    return [
        {"text": "GET https://www.googletagmanager.com/gtag/js status=200"},
        {"text": "Hydration failed because text content did not match"},
        {"text": "Some weird unknown thing happened"},
        {"text": "Uncaught TypeError: Cannot read prop 'foo' of undefined"},
        {"text": "[Stripe.js] You called .createToken with deprecated arg"},
    ]
