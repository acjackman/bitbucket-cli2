"""bb --- BitBucket CLI tool.

Useful for working with BitBucket and BitBucket pipelines.

Set BB_WORKSPACE and BB_REPO with [direnv](https://direnv.net).

Set BB_USER and BB_PASSWORD using environment variables or keychain.
"""
import json
import logging
import subprocess
import sys  # noqa: S404
from typing import Any
from typing import Dict
from typing import Optional

import click

from .bitbucket import BitBucketClient
from .bitbucket import Pipeline
from .profilekeys import ProfileKeys

log = logging.getLogger(__name__)


def _start_cli(
    client: BitBucketClient,
    branch_name: str,
    pipeline_name: str,
    extras: Dict[Any, Any],
) -> Pipeline:
    pipeline = client.start_pipeline(branch_name, pipeline_name, extras)
    build_number = pipeline["build_number"]
    build_url = client.build_url(pipeline)
    log.info(f"Build #{build_number} started. View build: {build_url}")
    return pipeline


def _wait_cli(client: BitBucketClient, pipeline: Pipeline) -> None:
    build_number = pipeline["build_number"]
    build_url = client.build_url(pipeline)

    build_result = client.wait(pipeline)
    log.debug(f"{build_result=}")
    if build_result is False:
        log.info(f"Build #{build_number} incomplete. View build: {build_url}")
        sys.exit(1)

    log.info(f"Build #{build_number} complete! View build: {build_url}")


def user_callback() -> Optional[str]:
    return ProfileKeys.from_envrion().username


def password_callback() -> Optional[str]:
    return ProfileKeys.from_envrion().password


@click.group(name="bb")
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["WARNING", "INFO", "DEBUG"], case_sensitive=False),
)
@click.pass_context
def cli(ctx: Any, log_level: str) -> None:
    logging.basicConfig(
        format=(
            log_level.upper() == "DEBUG"
            and "%(asctime)s %(levelname)-8s| %(message)s"
            or "%(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        # level=log_level.upper(),
    )
    log.setLevel(log_level.upper())


@cli.command()
def login() -> None:
    """Save BitBucket credentials to system keychain."""
    keys = ProfileKeys.from_envrion()
    new_username = click.prompt(
        "Please enter your BitBucket username", default=keys.username
    )
    keys.set_username(new_username)
    new_password = click.prompt(
        "Please enter your BitBucket password",
        hide_input=True,
        confirmation_prompt=True,
    )
    keys.set_password(new_password)
    click.secho("Credentials saved", fg="green")


@cli.group()
@click.option("--workspace", required=True, envvar="BB_WORKSPACE")
@click.option("--repo", required=True, envvar="BB_REPO")
@click.option("--user", required=True, envvar="BB_USER", default=user_callback)
@click.option(
    "--password", required=True, envvar="BB_PASSWORD", default=password_callback
)
@click.pass_context
def project(ctx: Any, workspace: str, repo: str, user: str, password: str) -> None:
    log.debug(f"Configuring client with {workspace=} {repo=} {user=}")
    ctx.obj = BitBucketClient(workspace, repo, user, password)


def branch_callback() -> str:
    branch_cmd = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD", "--"], capture_output=True
    )
    if branch_cmd.returncode != 0:
        raise Exception("Unable to identify git branch")
    return branch_cmd.stdout.decode("utf-8").split("\n")[0]


@project.command(name="start")
@click.option("--branch", required=True, default=branch_callback)
@click.option("--wait/--no-wait", required=True, default=True)
@click.option("--extras-json", nargs=1)
@click.argument("pipeline", nargs=1)
@click.pass_obj
def start_command(
    client: BitBucketClient, branch: str, pipeline: str, extras_json: str, wait: bool
) -> None:
    log.debug("running start")

    if extras_json:
        vars = json.loads(extras_json)
    else:
        vars = {}
    log.info(f"Attempting to run '{pipeline}' on branch '{branch}' with {vars=}")

    pipeline_obj = _start_cli(client, branch, pipeline, vars)
    _wait_cli(client, pipeline_obj)


@project.command(name="wait")
@click.option("--branch", required=True, default=branch_callback())
@click.pass_obj
def wait_command(client: BitBucketClient, branch: str) -> None:
    log.debug(f"running wait on branch {branch}")
    for pipeline in client.recent_pipelines(initial_page_length=3):
        pipeline_branch = pipeline.target_branch
        build_number = pipeline["build_number"]
        log.debug(f"Checking #{build_number}: '{pipeline_branch}'")
        if pipeline.target_branch == branch:
            build_url = client.build_url(pipeline)
            log.info(f"Waiting on build #{build_number}. View build: {build_url}")
            break
    else:
        log.critical(f"Unable to identify build for {branch=}")
        sys.exit(1)

    _wait_cli(client, pipeline)


if __name__ == "__main__":
    cli(prog_name="bb")  # pragma: no cover
