import asyncio
import sys

import click

from manifold.config import settings
from manifold.domain.identity_backfill import backfill_identities
from manifold.domain.users import create_user_record


@click.group()
def cli() -> None:
    pass


@cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.option("--role", default="regular", type=click.Choice(["regular", "superadmin"]))
@click.option("--must-change-password", is_flag=True, default=False)
def create_user(username: str, password: str, role: str, must_change_password: bool) -> None:
    asyncio.run(
        create_user_record(
            username=username,
            password=password,
            role=role,
            must_change_password=must_change_password,
        )
    )
    click.echo(f"Created user '{username}' with role '{role}'.")


@cli.command("backfill-identities")
def backfill_identities_cmd() -> None:
    """Assign identity_id to existing accounts that have none (Phase 4 backfill).

    Idempotent — safe to run multiple times. A second run with no new data is a
    no-op and exits cleanly.
    """
    counts = asyncio.run(backfill_identities())
    click.echo(
        f"Backfill complete: "
        f"users={counts['users_processed']} "
        f"processed={counts['accounts_processed']} "
        f"skipped={counts['accounts_skipped']}"
    )


@cli.command("check-config")
def check_config() -> None:
    errors: list[str] = []
    if not settings.secret_key:
        errors.append("SECRET_KEY is not set")
    if not settings.admin_username:
        click.echo("WARN: ADMIN_USERNAME not set — required on first run (empty users table)")
    if not settings.admin_password:
        click.echo("WARN: ADMIN_PASSWORD not set — required on first run (empty users table)")
    if errors:
        for error in errors:
            click.echo(f"ERROR: {error}", err=True)
        sys.exit(1)
    click.echo(f"OK  database_url    = {settings.database_url}")
    click.echo(f"OK  redis_url       = {settings.redis_url}")
    click.echo("Configuration OK")


if __name__ == "__main__":
    cli()
