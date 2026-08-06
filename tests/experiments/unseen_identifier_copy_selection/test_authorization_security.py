"""Security tests for the hardened unseen-ID authorization (provenance + capability forgery).

Closes AUTHORIZATION_PROVENANCE_FORGEABLE and AUTHORIZATION_CONTEXT_FORGEABLE. Uses only temporary
local Git repositories and synthetic committed *security-fixture* authorization documents — never a
scientific authorization for the real repository, never a scientific pool/cohort/checkpoint/replay.
The one positive path authorizes a scientific seed against a synthetic temp repo and STOPS at the
primitive guard with generation patched to abort (an intercepted scientific policy path).
"""
from __future__ import annotations

import copy
import dataclasses
import json
import pickle
import subprocess

import pytest

from experiments.unseen_identifier_copy_selection import execution as ex
from experiments.unseen_identifier_copy_selection.execution import (
    AuthorizationContext,
    AuthorizationRecordError,
    DOC_SCHEMA_VERSION,
    ExecutionNotAuthorized,
    SMOKE_EXECUTION_STATE,
    active_authorization,
    authorize,
    compute_record_digest,
    require_execution_authorization,
    sha256_hex,
)
from experiments.unseen_identifier_copy_selection.manifest import frozen_recipe_source_hashes

DOC_PATH = "docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_EXECUTION_AUTHORIZATION.json"
SMOKE = 9070


# --------------------------------------------------------------------------- helpers

def _git(repo, *args, check=True, input_bytes=None):
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, input=input_bytes)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {args} failed: {proc.stderr.decode()}")
    return proc


def _init_repo(tmp_path):
    repo = tmp_path / "authority_repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "sec@test")
    _git(repo, "config", "user.name", "sec")
    _git(repo, "config", "commit.gpgsign", "false")
    return repo


def _commit_empty(repo, message):
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.decode().strip()


def _commit_doc(repo, doc_bytes, *, path=DOC_PATH, message="authorize"):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(doc_bytes)
    _git(repo, "add", path)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.decode().strip()


def _default_ref(repo):
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()


def _valid_doc(merge_oid, *, state=SMOKE_EXECUTION_STATE, cohort="unseen", seeds=(SMOKE,),
               approved=True, hashes=None, params=ex.FROZEN_PARAMETER_COUNT, scope="one-run",
               impl_commit=None, extra=None, drop=None):
    doc = {
        "schema_version": DOC_SCHEMA_VERSION,
        "approved": approved,
        "authorization_state": state,
        "permitted_cohort": cohort,
        "permitted_seeds": list(seeds),
        "protocol_lock_commit": "PL",
        "implementation_authorization_commit": merge_oid,
        "implementation_commit": impl_commit if impl_commit is not None else merge_oid,
        "model_recipe_hashes": hashes if hashes is not None else frozen_recipe_source_hashes(),
        "parameter_count": params,
        "authorization_scope": scope,
    }
    if extra:
        doc.update(extra)
    if drop:
        for k in drop:
            doc.pop(k, None)
    return json.dumps(doc, sort_keys=True).encode("utf-8")


def _record_for(doc_bytes, auth_commit, merge_oid, *, state=SMOKE_EXECUTION_STATE, cohort="unseen",
                seeds=(SMOKE,), path=DOC_PATH, doc_digest=None, impl_commit=None):
    record = {
        "authorization_state": state,
        "cohort": cohort,
        "permitted_seeds": list(seeds),
        "protocol_lock_commit": "PL",
        "implementation_authorization_commit": merge_oid,
        "implementation_commit": impl_commit if impl_commit is not None else merge_oid,
        "model_recipe_hashes": frozen_recipe_source_hashes(),
        "parameter_count": ex.FROZEN_PARAMETER_COUNT,
        "scope": "one-run",
        "authorization_document_commit": auth_commit,
        "authorization_document_path": path,
        "authorization_document_digest": doc_digest if doc_digest is not None else sha256_hex(doc_bytes),
    }
    record["record_digest"] = compute_record_digest(record)
    return record


def _authority_fixture(tmp_path, **doc_kw):
    """Build a temp repo with a committed valid security-fixture authorization document.

    Returns (repo, merge_oid, auth_commit, default_ref, committed_bytes, record)."""
    repo = _init_repo(tmp_path)
    merge_oid = _commit_empty(repo, "implementation merge anchor")
    doc_bytes = _valid_doc(merge_oid, **doc_kw)
    auth_commit = _commit_doc(repo, doc_bytes)
    committed = _git(repo, "show", f"{auth_commit}:{DOC_PATH}").stdout
    record = _record_for(committed, auth_commit, merge_oid,
                         state=doc_kw.get("state", SMOKE_EXECUTION_STATE),
                         cohort=doc_kw.get("cohort", "unseen"),
                         seeds=doc_kw.get("seeds", (SMOKE,)))
    return repo, merge_oid, auth_commit, _default_ref(repo), committed, record


def _authorize(record, repo, merge_oid, ref, *, seed=SMOKE, cohort="unseen"):
    return authorize(record, seed=seed, cohort=cohort, repo_dir=str(repo),
                     authoritative_ref=ref, implementation_merge=merge_oid)


# --------------------------------------------------------------------------- positive path

def test_positive_committed_document_authorizes_and_reaches_guard_only(tmp_path, monkeypatch):
    from experiments.unseen_identifier_copy_selection import identifiers

    monkeypatch.setattr(identifiers, "_draw_distinct",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no generation")))
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    ctx = _authorize(record, repo, merge_oid, ref)
    assert ctx.authorization_state == SMOKE_EXECUTION_STATE and ctx.seed == SMOKE
    assert ctx.document_commit == auth_commit and ctx.document_digest == sha256_hex(committed)
    with active_authorization(ctx):
        require_execution_authorization(SMOKE, ctx.capability)   # guard PASSES; no generation called
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(SMOKE, ctx.capability)   # capability is one-run scoped


# --------------------------------------------------------------------------- Blocker A regressions

def test_fabricated_artifact_recomputed_digest_rejected(tmp_path):
    # A record naming a commit that does not exist in the repo is rejected (no committed doc).
    repo = _init_repo(tmp_path)
    merge_oid = _commit_empty(repo, "anchor")
    doc = _valid_doc(merge_oid)
    record = _record_for(doc, "a" * 40, merge_oid)
    with pytest.raises(AuthorizationRecordError):
        _authorize(record, repo, merge_oid, _default_ref(repo))


def test_nonexistent_and_short_commit_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    for bad in ("f" * 40, "abc123"):
        forged = {**record, "authorization_document_commit": bad}
        forged["record_digest"] = compute_record_digest(forged)
        with pytest.raises(AuthorizationRecordError):
            _authorize(forged, repo, merge_oid, ref)


def test_blob_or_tree_substituted_for_commit_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    blob_oid = _git(repo, "rev-parse", f"{auth_commit}:{DOC_PATH}").stdout.decode().strip()  # a blob
    forged = {**record, "authorization_document_commit": blob_oid}
    forged["record_digest"] = compute_record_digest(forged)
    with pytest.raises(AuthorizationRecordError):
        _authorize(forged, repo, merge_oid, ref)


def test_commit_not_reachable_from_authoritative_default_rejected(tmp_path):
    # Commit the doc on a feature branch NOT merged into the default ref.
    repo = _init_repo(tmp_path)
    merge_oid = _commit_empty(repo, "anchor")
    default_ref = _default_ref(repo)
    _git(repo, "checkout", "-q", "-b", "feature")
    doc = _valid_doc(merge_oid)
    auth_commit = _commit_doc(repo, doc)
    committed = _git(repo, "show", f"{auth_commit}:{DOC_PATH}").stdout
    record = _record_for(committed, auth_commit, merge_oid)
    # authoritative_ref = the default branch, which does NOT contain the feature commit
    with pytest.raises(AuthorizationRecordError):
        _authorize(record, repo, merge_oid, default_ref)


def test_commit_not_descending_from_implementation_merge_rejected(tmp_path):
    # doc committed BEFORE the merge anchor -> anchor is a descendant, chronology fails.
    repo = _init_repo(tmp_path)
    doc_pre = _valid_doc("0" * 40)  # impl fields fixed up below via record/merge mismatch
    # First commit the doc, THEN create the merge anchor as a later commit.
    auth_commit = _commit_doc(repo, _valid_doc("x"), message="doc first")
    merge_oid = _commit_empty(repo, "later merge anchor")
    committed = _git(repo, "show", f"{auth_commit}:{DOC_PATH}").stdout
    record = _record_for(committed, auth_commit, merge_oid)
    with pytest.raises(AuthorizationRecordError):
        _authorize(record, repo, merge_oid, _default_ref(repo))


def test_wrong_document_path_and_traversal_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    for bad_path in ("docs/other.json", "../etc/passwd",
                     "docs/research/hybrid_llm/benchmarks/OTHER.json"):
        forged = {**record, "authorization_document_path": bad_path}
        forged["record_digest"] = compute_record_digest(forged)
        with pytest.raises(AuthorizationRecordError):
            _authorize(forged, repo, merge_oid, ref)


def test_committed_document_digest_mismatch_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    forged = {**record, "authorization_document_digest": "d" * 64}
    forged["record_digest"] = compute_record_digest(forged)
    with pytest.raises(AuthorizationRecordError):
        _authorize(forged, repo, merge_oid, ref)


def test_record_digest_mismatch_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    forged = {**record, "record_digest": "0" * 64}  # not recomputed
    with pytest.raises(AuthorizationRecordError):
        _authorize(forged, repo, merge_oid, ref)


@pytest.mark.parametrize("doc_kw", [
    {"approved": False},
    {"state": "DEVELOPMENT_EXECUTION_AUTHORIZED"},   # doc state != record smoke state
    {"seeds": (9071,)},                              # doc seed scope excludes 9070
    {"hashes": {"config.py": "00"}},                 # wrong model hashes
    {"params": 1},                                   # wrong parameter count
    {"scope": "forever"},                            # unrecognized scope
    {"extra": {"expiry": "2099-01-01"}},             # any expiry fails closed
    {"drop": ["approved"]},                          # missing field
    {"extra": {"surprise": 1}},                      # unknown field (strict schema)
])
def test_committed_document_content_defects_rejected(tmp_path, doc_kw):
    # Build a repo whose COMMITTED document is defective; the record binds its real digest.
    repo = _init_repo(tmp_path)
    merge_oid = _commit_empty(repo, "anchor")
    doc_bytes = _valid_doc(merge_oid, **doc_kw)
    auth_commit = _commit_doc(repo, doc_bytes)
    committed = _git(repo, "show", f"{auth_commit}:{DOC_PATH}").stdout
    record = _record_for(committed, auth_commit, merge_oid)  # smoke/unseen/9070 record
    with pytest.raises(AuthorizationRecordError):
        _authorize(record, repo, merge_oid, _default_ref(repo))


def test_record_commit_disagrees_with_committed_document_rejected(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    forged = {**record, "implementation_authorization_commit": "z" * 40}
    forged["record_digest"] = compute_record_digest(forged)
    with pytest.raises(AuthorizationRecordError):
        _authorize(forged, repo, merge_oid, ref)


def test_duplicate_keys_in_committed_document_rejected(tmp_path):
    repo = _init_repo(tmp_path)
    merge_oid = _commit_empty(repo, "anchor")
    raw = b'{"schema_version": "x", "approved": true, "approved": true}'
    auth_commit = _commit_doc(repo, raw)
    committed = _git(repo, "show", f"{auth_commit}:{DOC_PATH}").stdout
    record = _record_for(committed, auth_commit, merge_oid)
    with pytest.raises(AuthorizationRecordError):
        _authorize(record, repo, merge_oid, _default_ref(repo))


# --------------------------------------------------------------------------- Blocker B regressions

def _minted_ctx(tmp_path):
    repo, merge_oid, auth_commit, ref, committed, record = _authority_fixture(tmp_path)
    return _authorize(record, repo, merge_oid, ref)


def test_direct_construction_rejected():
    with pytest.raises(AuthorizationRecordError):
        AuthorizationContext(
            mint_key=object(), authorization_state=SMOKE_EXECUTION_STATE, seed=SMOKE, cohort="unseen",
            record_digest="x", document_commit="c", document_digest="d", protocol_lock_commit="p",
            implementation_authorization_commit="i", implementation_commit="j",
            model_recipe_hashes=(), parameter_count=ex.FROZEN_PARAMETER_COUNT, scope="one-run")


def test_object_new_bypass_rejected():
    obj = object.__new__(AuthorizationContext)   # uninitialized; never minted
    with pytest.raises(AuthorizationRecordError):
        with active_authorization(obj):
            pass


def test_replace_copy_deepcopy_pickle_all_rejected(tmp_path):
    ctx = _minted_ctx(tmp_path)
    forgeries = [
        dataclasses.replace(ctx, seed=SMOKE),
        copy.copy(ctx),
        copy.deepcopy(ctx),
        pickle.loads(pickle.dumps(ctx)),
    ]
    for forged in forgeries:
        with pytest.raises(AuthorizationRecordError):
            with active_authorization(forged):
                pass


def test_stale_capability_after_context_exit_rejected(tmp_path):
    ctx = _minted_ctx(tmp_path)
    with active_authorization(ctx):
        require_execution_authorization(SMOKE, ctx.capability)
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(SMOKE, ctx.capability)


def test_capability_removed_after_exception(tmp_path):
    ctx = _minted_ctx(tmp_path)
    with pytest.raises(RuntimeError):
        with active_authorization(ctx):
            raise RuntimeError("boom")
    assert ex._ACTIVE_CAPABILITIES == {}
    with pytest.raises(ExecutionNotAuthorized):
        require_execution_authorization(SMOKE, ctx.capability)


def test_active_context_rejects_wrong_seed(tmp_path):
    ctx = _minted_ctx(tmp_path)
    with active_authorization(ctx):
        with pytest.raises(ExecutionNotAuthorized):
            require_execution_authorization(9071, ctx.capability)   # bound to 9070


def test_revoked_context_rejected(tmp_path):
    ctx = _minted_ctx(tmp_path)
    ex.revoke_minted_context(ctx)
    with pytest.raises(AuthorizationRecordError):
        with active_authorization(ctx):
            pass


# --------------------------------------------------------------------------- primitive-guard tests

def test_primitive_guard_only_reached_by_valid_fixture_context(tmp_path, monkeypatch):
    from experiments.unseen_identifier_copy_selection import identifiers
    from experiments.unseen_identifier_copy_selection.tasks import generate_split

    monkeypatch.setattr(identifiers, "_draw_distinct",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no generation")))
    ctx = _minted_ctx(tmp_path)
    # forged contexts never reach the guard
    with pytest.raises(AuthorizationRecordError):
        with active_authorization(copy.deepcopy(ctx)):
            pass
    # a valid minted context reaches the guard; we assert the guard passes but never generate
    with active_authorization(ctx):
        require_execution_authorization(SMOKE, ctx.capability)
    # direct primitive call for a reserved seed with no active context still fails closed
    with pytest.raises(ExecutionNotAuthorized):
        generate_split("C2", "unseen", SMOKE, n=1)


# --------------------------------------------------------------------------- no-execution instrumentation

def test_no_scientific_execution_during_security_tests(tmp_path, monkeypatch):
    # Trap every execution primitive; run the positive provenance path; prove zero scientific work.
    from experiments.unseen_identifier_copy_selection import identifiers, tasks

    tripped = {"draw": 0, "split": 0}

    def _no_draw(*a, **k):
        tripped["draw"] += 1
        raise AssertionError("pool draw must not run")

    orig_split = tasks.generate_split

    def _count_split(*a, **k):
        tripped["split"] += 1
        return orig_split(*a, **k)

    monkeypatch.setattr(identifiers, "_draw_distinct", _no_draw)
    monkeypatch.setattr(tasks, "generate_split", _count_split)

    ctx = _minted_ctx(tmp_path)
    with active_authorization(ctx):
        require_execution_authorization(SMOKE, ctx.capability)
    assert tripped == {"draw": 0, "split": 0}
