import logging
import time
from typing import Any
from typing import Dict
from typing import Iterable
from typing import Optional

import requests
from boltons.iterutils import get_path
from boltons.iterutils import PathAccessError
from requests import Response


log = logging.getLogger(__name__)


class Pipeline(dict):  # type: ignore
    """Pipeline Response Object"""

    @property
    def target_branch(self) -> Optional[str]:
        target = self["target"]
        if target["ref_type"] == "branch":
            return str(target["ref_name"])
        return None


class BitBucketClient:
    session: requests.Session
    repo_api: str

    def __init__(self, workspace: str, repo: str, user: str, password: str) -> None:
        self.workspace = workspace
        self.repo = repo
        self.repo_api = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}"
        session = requests.Session()
        session.auth = (user, password)
        self.session = session

    def _get(self, endpoint: str, *args: Any, **kwargs: Any) -> Response:
        r = self.session.get(self.repo_api + endpoint, *args, **kwargs)
        r.raise_for_status()
        return r

    def _post(self, endpoint: str, *args: Any, **kwargs: Any) -> Response:
        r = self.session.post(self.repo_api + endpoint, *args, **kwargs)
        r.raise_for_status()
        return r

    def get_pipeline(self, pipeline_id: str) -> Pipeline:
        r = self._get(f"/pipelines/{pipeline_id}")
        return Pipeline(r.json())

    def recent_pipelines(
        self, page_length: int = 10, initial_page_length: Optional[int] = None
    ) -> Iterable[Pipeline]:
        if page_length <= 0:
            raise ValueError("page_length must be a postive integer")
        if initial_page_length is not None and initial_page_length <= 0:
            raise ValueError("initial_page_length may not be a negative number")
        n = initial_page_length or page_length
        while True:
            data = self._get(
                "/pipelines/", params={"pagelen": n, "sort": "-created_on",}
            ).json()
            yield from (Pipeline(v) for v in data["values"])
            # Continue fetching pages at the regular length
            n = page_length

    def build_url(
        self, pipeline: Optional[Pipeline] = None, n: Optional[int] = None
    ) -> str:
        build_number = n or (pipeline and pipeline.get("build_number"))
        if build_number is None:
            raise TypeError("pipeline or n must be set")
        return (
            f"https://bitbucket.org/{self.workspace}/{self.repo}"
            f"/addon/pipelines/home#!/results/{build_number}"
        )

    def start_pipeline(
        self, branch_name: str, pipeline_name: str, extras: Dict[Any, Any]
    ) -> Pipeline:
        # Create Build
        payload = {
            "target": {
                "type": "pipeline_ref_target",
                "ref_type": "branch",
                "ref_name": branch_name,
                "selector": {"type": "custom", "pattern": pipeline_name,},
            },
            "variables": [{"key": str(k), "value": str(v),} for k, v in extras.items()],
        }
        return Pipeline(self._post("/pipelines/", json=payload).json())

    def wait(  # noqa: C901
        self, pipeline: Pipeline, sleep_time: int = 15, watchdog_max: int = 100
    ) -> Optional[bool]:
        """Wait on build to finish and return the result."""
        pipeline_id = pipeline["uuid"]
        state = pipeline["state"]
        log.debug(f"{state=}")

        def running(state: Dict[Any, Any]) -> bool:
            if state["name"] not in {"IN_PROGRESS", "PENDING"}:
                return False

            if "result" in state:
                return False

            try:
                stage_name = get_path(state, ("stage", "name"))
                if stage_name == "PAUSED":
                    return False
            except PathAccessError:
                pass

            return True

        watchdog_rounds = 0
        while running(state):
            # Check watchdog counter for infinite loop
            watchdog_rounds += 1
            if watchdog_rounds >= watchdog_max:
                raise Exception("Maximum waiting time exceeded")

            # Wait for set time
            log.debug(f"Sleeping for {sleep_time}s...")
            time.sleep(sleep_time)

            # Check with BitBucket for pipeline state
            pipeline = self.get_pipeline(pipeline_id)
            state = pipeline["state"]
            log.debug(f"{state=}")
        try:
            return bool(get_path(state, ["result", "name"]) == "SUCCESSFUL")
        except PathAccessError:
            return None  # None is paused, successful till now, but there are more steps
