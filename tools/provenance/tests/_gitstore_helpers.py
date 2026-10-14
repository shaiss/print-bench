"""H1's shared test helpers: throwaway git repos with a LOCAL bare ``origin`` and a fake
artifact list, so tip continuity, the guard and the ordered pushes run end to end offline.

Used by test_gitstore.py and test_cli.py (H1-owned; tests/fakes.py stays frozen). No
network: every remote is a ``git init --bare`` directory, every GitHub read a
``tests.fakes.FakeGitHub``.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
from typing import Any, Optional

from conftest import FIXTURES, GUARD_DIR, OWNER, REPO_NAME
from fakes import FakeGitHub

from provenance import canonical, gitstore

ALLOW = {"GIT_ALLOW_PROTOCOL": "https:file"}
REPO_SLUG = f"{OWNER}/{REPO_NAME}"
MINI = FIXTURES / "snapshot-mini"
MINI_PIN = "0da7f326fb3d57ad8968a56b30e3b3831a1d181b32b3ce0193ea22235ea3d0a0"
NOW = "2026-10-14T12:00:00Z"
NOW_EPOCH = 1791979200  # NOW as a UTC epoch


def _env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file",
               GIT_AUTHOR_NAME="Test Owner", GIT_AUTHOR_EMAIL="owner@example.com",
               GIT_COMMITTER_NAME="Test Owner", GIT_COMMITTER_EMAIL="owner@example.com",
               GIT_AUTHOR_DATE="2026-10-01T00:00:00Z", GIT_COMMITTER_DATE="2026-10-01T00:00:00Z")
    return env


def sh(cwd: os.PathLike, *args: str, input: Optional[bytes] = None) -> str:
    """Plain git for test set-up (never the code under test)."""
    p = subprocess.run(["git", "-C", str(cwd), "-c", "core.hooksPath=/dev/null",
                        "-c", "commit.gpgSign=false", *args],
                       input=input, capture_output=True, env=_env())
    if p.returncode != 0:
        raise AssertionError(f"git {args}: {p.stderr.decode()}")
    return p.stdout.decode().strip()


class Sandbox:
    """``origin.git`` (bare) seeded with a ``main`` that carries the real guard files, and a
    full clone ``checkout`` standing in for the workflow's ``fetch-depth: 0`` checkout."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = pathlib.Path(root)
        self.origin = self.root / "origin.git"
        self.seed = self.root / "seed"
        self.checkout = self.root / "checkout"
        self.root.mkdir(parents=True, exist_ok=True)
        sh(self.root, "init", "-q", "--bare", "-b", "main", str(self.origin))
        sh(self.root, "init", "-q", "-b", "main", str(self.seed))
        (self.seed / ".github" / "data-branch-guard").mkdir(parents=True)
        for name in ("vercel.json", "vercel-ignore-build.sh"):
            shutil.copy2(GUARD_DIR / name, self.seed / ".github" / "data-branch-guard" / name)
        (self.seed / "designs" / "demo").mkdir(parents=True)
        (self.seed / "designs" / "demo" / "demo.scad").write_text("cube(1);\n")
        sh(self.seed, "add", "-A")
        sh(self.seed, "commit", "-qm", "seed main")
        sh(self.seed, "remote", "add", "origin", str(self.origin))
        sh(self.seed, "push", "-q", "origin", "main")
        sh(self.root, "clone", "-q", str(self.origin), str(self.checkout))
        self.main_sha = sh(self.checkout, "rev-parse", "refs/remotes/origin/main")
        self.git = gitstore.Git(str(self.checkout), env=ALLOW)

    # -- data-ref manipulation (what a forger, or the harness, does) -------------
    def commit(self, files: dict[str, bytes], parent: Optional[str], *,
               modes: Optional[dict[str, str]] = None, message: str = "t") -> str:
        b = gitstore.DerivedTreeBuilder(self.git)
        for path, data in files.items():
            b.set(path, data, (modes or {}).get(path, "100644"))
        return gitstore.commit_tree(self.git, b.write_tree(), parent, message)

    def push(self, sha: str, ref: str, *, force: bool = False) -> None:
        sh(self.checkout, "push", "-q", "origin", f"{'+' if force else ''}{sha}:refs/heads/{ref}")

    def delete(self, ref: str) -> None:
        sh(self.checkout, "push", "-q", "origin", f":refs/heads/{ref}")

    def remote(self, ref: str) -> Optional[str]:
        out = sh(self.root, "--git-dir", str(self.origin), "for-each-ref", "--format=%(objectname)",
                 f"refs/heads/{ref}")
        return out or None

    def files_at(self, sha: str) -> dict[str, bytes]:
        r = gitstore.GitTreeReader(self.git, sha)
        return {p: r.read(p) for p in r.paths()}


class Artifacts:
    """The repo-wide ``/actions/artifacts`` list and ``/actions/runs/{id}`` objects a FakeGitHub serves."""

    def __init__(self, fake: FakeGitHub, main_sha: str) -> None:
        self.fake = fake
        self.main_sha = main_sha
        self.items: list[dict[str, Any]] = []
        self.seq = 1000
        self._publish()

    def _publish(self) -> None:
        page = {"artifacts": sorted(self.items, key=lambda a: a["id"], reverse=True),
                "total_count": len(self.items)}
        self.fake.responses[("/actions/artifacts", frozenset())] = page

    def run(self, run_id: int, *, event: str = "workflow_dispatch", branch: str = "main",
            path: str = gitstore.WORKFLOW_PATH, head_sha: Optional[str] = None) -> None:
        self.fake.responses[(f"/actions/runs/{run_id}", frozenset())] = {
            "event": event, "head_branch": branch, "head_sha": head_sha or self.main_sha, "id": run_id,
            "path": path}

    def add(self, name: str, run_id: int, *, created_at: str = "2026-10-14T11:00:00Z",
            branch: str = "main", head_sha: Optional[str] = None) -> int:
        self.seq += 1
        self.items.append({"created_at": created_at, "expired": False, "id": self.seq, "name": name,
                           "workflow_run": {"head_branch": branch, "head_sha": head_sha or self.main_sha,
                                            "id": run_id}})
        self._publish()
        return self.seq

    def tip(self, ref: str, sha: str, run_id: int, **kw: Any) -> int:
        self.run(run_id)
        return self.add(gitstore.tip_name(ref, sha), run_id, **kw)

    def intent(self, ref: str, sha: str, run_id: int, **kw: Any) -> int:
        self.run(run_id)
        return self.add(gitstore.intent_name(ref, sha), run_id, **kw)


def read_outputs(path: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            k, _, v = line.partition("=")
            out[k] = v
    path.write_text("")  # each step appends to its own $GITHUB_OUTPUT
    return out


def make_conf(watched: tuple[str, ...] = ("auto-review.yml", "design-run.yml"), **over: Any):
    """A ``conf.Config`` built directly (``conf.parse`` is H6's), the snapshot-mini pin."""
    from provenance import conf as conf_mod
    values = dict(enabled=True, cadence="29 * * * *", settle_hours=6, max_defer_hours=24,
                  deploy_wait_hours=2, scheduled_max_requests=400, rate_floor=500,
                  dispatch_max_minutes=330, derive_reserve_minutes=30, backfill_since="2026-07-31",
                  ambiguity_window_minutes=15, edit_grace_seconds=60, receipt_lookback_hours=48,
                  continuity_horizon_days=90, watched_workflows=watched, snapshot_id="pr843",
                  snapshot_dir="audits/provenance-2026-10/rescue",
                  snapshot_commit="411a7565e1c6c8f2b96edf631286ceac798d7887",
                  snapshot_manifest_sha256=MINI_PIN)
    values.update(over)
    return conf_mod.Config(**values)


def fake_derive(evidence, *, git, codebasis, main_sha, owner, repo, owner_login, evidence_sha,
                producer_run, edit_grace_seconds, guard):
    """Stand-in for ``bundle.derive`` (H5): a tiny derived tree whose ONE view is a pure function
    of the evidence content (its receipt and raw paths), with the bundle meta on top."""
    from provenance import bundle
    view = {"design": "demo", "evidence_paths": [p for p in evidence.paths() if p.startswith(("raw/", "receipts/"))]}
    view_bytes = canonical.dumps_bytes(view)
    meta = {"evidence_sha": evidence_sha, "main_sha": main_sha, "producer_run": producer_run}
    bundle_doc = dict(meta, format="bundle@1", views={"demo": view},
                      views_sha256={"demo": canonical.sha256_hex(view_bytes)})
    files = dict(guard)
    files["FORMAT"] = ("100644", bundle.DERIVED_FORMAT_BYTES)
    files["views/demo.json"] = ("100644", view_bytes)
    files["site/bundle.json"] = ("100644", canonical.dumps_bytes(bundle_doc))
    return bundle.DerivedTree(files=files, bundle=bundle_doc, records=[], counts={"views": 1})


def fake_same_content(tip, new_files) -> bool:
    """Stand-in for ``bundle.same_content`` (H5) with the documented rule: same paths, every blob
    but the bundle byte-identical (modes too), the bundle equal once its meta fields are removed."""
    import json

    from provenance import bundle
    if tip is None:
        return False
    if sorted(tip.paths()) != sorted(new_files):
        return False
    for path, (mode, data) in new_files.items():
        held = tip.read(path)
        if getattr(tip, "mode", None) and tip.mode(path) != mode:
            return False
        if path == bundle.BUNDLE_PATH:
            a, b = json.loads(held), json.loads(data)
            for k in bundle.META_FIELDS:
                a.pop(k, None)
                b.pop(k, None)
            if a != b:
                return False
        elif held != data:
            return False
    return True


class Harness:
    """The workflow's harvest job, step by step, over a Sandbox and a FakeGitHub:
    plan (harvest/refreeze/recover) → declare intents → publish → upload checkpoints.

    Seams patched (the ones the module docstrings name): ``cli.make_client`` → the fake,
    ``cli.utcnow`` → :data:`NOW`, ``conf.load`` → :func:`make_conf`, ``freeze.plan_freezes`` →
    an empty plan (``self.freeze``), ``bundle.derive``/``same_content`` → the fakes above;
    ``gitstore.ALLOW_PROTOCOL`` widened to ``https:file`` for the local bare origin."""

    def __init__(self, root: pathlib.Path, monkeypatch, **conf_over: Any) -> None:
        from provenance import bundle, cli, freeze
        from provenance import conf as conf_mod
        self.root = pathlib.Path(root)
        self.sb = Sandbox(self.root / "repo")
        self.live_runs: dict[str, list[dict[str, Any]]] = {}
        self.jobs: dict[int, list[dict[str, Any]]] = {}
        self.fake = FakeGitHub(responder=self._respond)
        self.art = Artifacts(self.fake, self.sb.main_sha)
        self.out = self.root / "out"
        self.gh_output = self.root / "gh_output"
        self.gh_output.write_text("")
        self.conf = make_conf(**conf_over)
        self.now = NOW
        self.run_id = 100
        self.client = None  # when set, make_client returns it instead of the fake
        self.deadlines: list = []
        self.freeze = lambda gh, **kw: freeze.FreezePlan()
        self.cli = cli
        monkeypatch.setattr(gitstore, "ALLOW_PROTOCOL", "https:file")
        monkeypatch.setattr(cli, "make_client", self._make_client)
        monkeypatch.setattr(cli, "utcnow", lambda: self.now)
        monkeypatch.setattr(conf_mod, "load", lambda path=None: self.conf)
        monkeypatch.setattr(freeze, "plan_freezes", lambda gh, **kw: self.freeze(gh, **kw))
        monkeypatch.setattr(bundle, "derive", fake_derive)
        monkeypatch.setattr(bundle, "same_content", fake_same_content)

    def _make_client(self, args, conf, *, scheduled, deadline_epoch):
        self.deadlines.append((scheduled, deadline_epoch))
        return self.client if self.client is not None else self.fake

    def _respond(self, path: str, params: dict) -> Any:
        parts = path.split("/")
        if path.startswith("/actions/workflows/") and path.endswith("/runs") and "created" in params:
            a, _, b = params["created"].partition("..")
            rows = [r for r in self.live_runs.get(parts[3], []) if a <= r["created_at"] <= b]
            return {"total_count": len(rows), "workflow_runs": rows}
        if path.startswith("/actions/runs/") and path.endswith("/jobs"):
            return {"jobs": self.jobs.get(int(parts[3]), [])}
        return None

    def add_live_run(self, workflow: str, run_id: int, created_at: str, *, status: str = "completed",
                     conclusion: str = "success", jobs: Optional[list] = None) -> None:
        self.live_runs.setdefault(workflow, []).append({
            "conclusion": conclusion if status == "completed" else None, "created_at": created_at,
            "display_title": "t", "event": "schedule", "head_branch": "main", "head_sha": self.sb.main_sha,
            "html_url": f"https://github.com/{REPO_SLUG}/actions/runs/{run_id}", "id": run_id,
            "name": workflow, "path": f".github/workflows/{workflow}", "pull_requests": [],
            "run_attempt": 1, "run_number": 1, "run_started_at": created_at, "status": status,
            "updated_at": created_at})
        self.jobs[run_id] = jobs if jobs is not None else [
            {"conclusion": "success", "id": run_id * 10, "name": "explain", "run_attempt": 1,
             "steps": [{"conclusion": "success", "name": "Explain a disarmed run", "number": 1}]}]

    def argv(self, cmd: str, *extra: str) -> list[str]:
        return [cmd, "--repo", REPO_SLUG, "--repo-dir", str(self.sb.checkout), "--conf", "unused.conf",
                "--run-id", str(self.run_id), "--run-attempt", "1", "--gh-output", str(self.gh_output),
                "--out-dir", str(self.out), *extra]

    def call(self, cmd: str, *extra: str) -> tuple[int, dict[str, str]]:
        code = self.cli.main(self.argv(cmd, *extra))
        return code, read_outputs(self.gh_output)

    def plan(self, *extra: str, mode: str = "harvest") -> tuple[int, dict[str, str]]:
        self.run_id += 1
        return self.call(mode, *extra)

    def declare(self, outputs: dict[str, str]) -> None:
        """The two upload-artifact steps for intents (each ``if:`` its ``*_changed``)."""
        for ref, changed, sha in ((gitstore.EVIDENCE_REF, "evidence_changed", "evidence_sha"),
                                  (gitstore.DERIVED_REF, "site_changed", "site_sha")):
            if outputs.get(changed) == "true":
                self.art.intent(ref, outputs[sha], self.run_id)

    def publish(self) -> tuple[int, dict[str, str]]:
        return self.call("publish")

    def checkpoint(self, outputs: dict[str, str]) -> None:
        """The two upload-artifact steps for checkpoints (each ``if:`` its ``*_tip`` is non-empty)."""
        for ref, key in ((gitstore.EVIDENCE_REF, "evidence_tip"), (gitstore.DERIVED_REF, "site_tip")):
            if outputs.get(key):
                self.art.tip(ref, outputs[key], self.run_id)

    def cycle(self, *extra: str, mode: str = "harvest") -> dict[str, Any]:
        """One whole harvest job; returns every step's code and outputs."""
        code, plan_out = self.plan(*extra, mode=mode)
        res: dict[str, Any] = {"plan": code, "plan_out": plan_out}
        if code != 0:
            return res
        self.declare(plan_out)
        pcode, pub_out = self.publish()
        res.update(publish=pcode, pub_out=pub_out)
        self.checkpoint(pub_out)
        return res

    def plan_doc(self) -> dict[str, Any]:
        import json
        return json.loads((self.out / "plan.json").read_text())
