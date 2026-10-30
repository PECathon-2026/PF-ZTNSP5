"""Reviewed, immutable acceptance tests in a separate verification view.

Generated tests never overwrite repository tests or enter the source candidate
patch. Approval is bound to the proposal, baseline and scope before execution.
"""

import ast
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from app.schemas.guild import AcceptanceTestProposal
from app.services.criterion_checks import SELECTOR
from app.services.test_reports import object_hash
from app.storage.guild import GuildConflict


def validate_proposal(proposal, baseline, missing_descriptions):
    paths = [file.path for file in proposal.files]
    if len(paths) != len(set(paths)):
        raise ValueError("Proposed acceptance test paths must be unique")
    required = set(missing_descriptions)
    descriptions = [m.criterion_description for m in proposal.mappings]
    if len(descriptions) != len(set(descriptions)) or set(descriptions) != required:
        raise ValueError("Every unmapped criterion needs one explicit test mapping")
    definitions = {}
    for file in proposal.files:
        if (baseline / file.path).exists():
            raise ValueError("A proposed test may not replace an existing file")
        tree = ast.parse(file.content)
        definitions[file.path] = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                   and n.name.startswith("test_")}
        if not definitions[file.path] or not any(isinstance(n, ast.Assert) or
            (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "raises") for n in ast.walk(tree)):
            raise ValueError("Proposed acceptance tests need test functions and assertions")
    used = set()
    for mapping in proposal.mappings:
        for selector in mapping.test_selectors:
            if len(selector) > 300 or not SELECTOR.fullmatch(selector) or ".." in selector:
                raise ValueError("Invalid acceptance test selector")
            parts = selector.split("::")
            if len(parts) != 2 or parts[0] not in definitions or parts[1].split("[", 1)[0] not in definitions[parts[0]]:
                raise ValueError("Mapping must name an actual proposed top-level test")
            used.add(parts[0])
    if used != set(paths):
        raise ValueError("Every proposed test file must support a criterion")


def bundle_hash(bundle):
    return object_hash({key: bundle[key] for key in ("proposal", "baseline_fingerprint", "scope_version")})


def checked_bundle(context, require_accepted=True):
    bundle = context.get("acceptance_tests")
    if not bundle:
        return None
    if bundle.get("hash") != bundle_hash(bundle):
        raise GuildConflict("Acceptance test proposal changed after review")
    if require_accepted and not bundle.get("accepted"):
        raise GuildConflict("New acceptance test expectations require human review")
    return AcceptanceTestProposal.model_validate(bundle["proposal"])


@contextmanager
def verification_view(workspaces, candidate, context):
    directory = workspaces.get_candidate_dir(candidate.mission_id, candidate.id)
    proposal = checked_bundle(context)
    if proposal is None:
        yield directory
        return
    if context["acceptance_tests"]["scope_version"] != candidate.criteria_version:
        raise GuildConflict("Accepted test scope is stale")
    if workspaces._compute_dir_hash(directory)[0] != candidate.content_fingerprint:
        raise GuildConflict("Candidate changed before acceptance checks")
    parent = workspaces.get_mission_workspace_dir(candidate.mission_id).parent / "verification-views"
    parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=parent, prefix="checks-") as temporary:
        view = Path(temporary) / "repo"
        shutil.copytree(directory, view, symlinks=True)
        for file in proposal.files:
            target = view / file.path
            if target.exists() or target.is_symlink():
                raise GuildConflict("Candidate collides with a reviewed acceptance test")
            target.write_bytes(file.content.encode("utf-8"))
        yield view


def test_files(context):
    proposal = checked_bundle(context)
    return {file.path: file.content for file in proposal.files} if proposal else {}
