from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_deploy_workflow_copies_optional_telegram_username_env():
    deploy_workflow = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

    body = deploy_workflow.read_text()

    assert "TELEGRAM_BOT_USERNAME: ${{ secrets.TELEGRAM_BOT_USERNAME }}" in body
    assert 'bot.get("username_env", "")' in body
    assert "requested.append((username_env, False))" in body


def test_migration_script_copies_telegram_username_env():
    migration_script = REPO_ROOT / "deploy" / "scripts" / "migrate-smaller-droplet.sh"

    body = migration_script.read_text()

    assert "TELEGRAM_BOT_USERNAME=%s" in body
