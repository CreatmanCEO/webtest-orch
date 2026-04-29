"""Tests for scripts/preflight.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import preflight


def test_check_url_rejects_empty() -> None:
    ok, msg = preflight.check_url("")
    assert ok is False
    assert "empty" in msg.lower()


def test_check_url_rejects_non_http() -> None:
    ok, _ = preflight.check_url("ftp://example.com")
    assert ok is False


def test_auth_flow_label_public_when_no_creds() -> None:
    env: dict[str, str] = {}
    assert preflight.auth_flow_label(env) == "public"


def test_auth_flow_label_supabase_when_url_and_key_set() -> None:
    env = {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "eyJ..."}
    assert preflight.auth_flow_label(env) == "supabase"


def test_auth_flow_label_custom_api_when_login_path_set() -> None:
    env = {"TEST_API_LOGIN_PATH": "/api/auth/login"}
    assert preflight.auth_flow_label(env) == "custom-api"


def test_auth_flow_label_ui_fallback_with_creds_only() -> None:
    env = {"TEST_USER_EMAIL": "a@b.c", "TEST_USER_PASSWORD": "x"}
    assert preflight.auth_flow_label(env) == "ui-fallback"


def test_check_auth_env_supabase_warns_on_invalid_key() -> None:
    env = {
        "TEST_USER_EMAIL": "a@b.c", "TEST_USER_PASSWORD": "x",
        "SUPABASE_URL": "https://x.supabase.co",
        "SUPABASE_ANON_KEY": "not-a-jwt",
    }
    warns = preflight.check_auth_env(env)
    assert any("SUPABASE_ANON_KEY" in w for w in warns)


def test_check_auth_env_passes_for_public() -> None:
    assert preflight.check_auth_env({}) == []


def test_load_env_test_reads_project_file(tmp_path: Path) -> None:
    (tmp_path / ".env.test").write_text(
        'TEST_BASE_URL=https://x.example.com\n# comment\nTEST_USER_EMAIL="a@b.c"\n'
    )
    env = preflight.load_env_test(tmp_path)
    assert env["TEST_BASE_URL"] == "https://x.example.com"
    assert env["TEST_USER_EMAIL"] == "a@b.c"


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "preflight.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "preflight" in result.stdout.lower()


def test_cli_passes_for_public_site_with_real_url(scripts_dir: Path, tmp_path: Path) -> None:
    """Smoke: public flow against example.com should pass."""
    (tmp_path / ".env.test").write_text("TEST_BASE_URL=https://example.com\n")
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "preflight.py"), "--cwd", str(tmp_path), "--timeout", "5"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
