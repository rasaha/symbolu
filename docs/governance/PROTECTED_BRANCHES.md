# Protected Branch Configuration Guide

**Purpose:** This document provides guidance for configuring GitHub branch protection rules to enforce the Ontology Freeze Contract.

> **Note:** This document describes the *recommended* configuration. Actual branch protection rules must be configured through the GitHub UI or API by a repository administrator.

---

## 1. Overview

The Symbolu repository uses branch protection to enforce governance rules for critical paths, particularly the frozen ontology files. This guide outlines the recommended configuration for protecting the `main` branch.

---

## 2. Recommended Branch Protection Rules

### 2.1 Target Branch

**Branch name pattern:** `main` (or `master` if applicable)

### 2.2 Required Settings

| Setting | Recommended Value | Purpose |
|---------|-------------------|---------|
| Require a pull request before merging | **Enabled** | Prevents direct pushes to main |
| Required approvals | **1** (minimum) | Ensures code review |
| Dismiss stale reviews on new pushes | **Enabled** | Invalidates approvals when code changes |
| Require review from Code Owners | **Enabled** | Enforces CODEOWNERS rules |
| Require status checks to pass | **Enabled** | CI must pass before merge |
| Require branches to be up to date | **Enabled** | Prevents merge conflicts |
| Require conversation resolution | **Enabled** | All comments must be addressed |
| Do not allow bypassing | **Enabled** | Prevents admin bypass |

### 2.3 Required Status Checks

The following CI checks should be required:

| Check Name | Description |
|------------|-------------|
| `ontology-freeze-guard` | Validates ontology freeze contract |
| `ontology-changelog-check` | Ensures changelog entry for ontology changes |

---

## 3. CODEOWNERS Enforcement

### 3.1 Protected Paths

The following paths are protected by CODEOWNERS and require approval from `@rasaha/ontology-stewards`:

```
# Frozen Ontology Files
docs/data/varna_bridge_map_v*.json
docs/data/ontological_layers_v*.json
docs/data/varna_layer_interaction_v*.json
docs/data/varna_polarity_map_v*.json
docs/data/varna_distortion_map_v*.json

# Phase-4A Module
symbolu/ontology/phase4a/**

# Governance Files
ONTOLOGY_FREEZE_CONTRACT.md
tests/test_ontology_freeze_contract.py
.github/workflows/ontology-freeze-ci.yml
.github/CODEOWNERS

# Documentation
docs/ontology/**
docs/governance/PROTECTED_BRANCHES.md
```

### 3.2 How CODEOWNERS Works

1. When a PR modifies a protected file, GitHub identifies the code owners
2. At least one code owner must approve before merge
3. If "Dismiss stale reviews" is enabled, editing the file dismisses existing approvals

---

## 4. Configuration Steps (GitHub UI)

To configure branch protection via the GitHub UI:

### Step 1: Navigate to Branch Protection

1. Go to your repository on GitHub
2. Click **Settings** > **Branches**
3. Under "Branch protection rules", click **Add rule**

### Step 2: Configure Rule

1. **Branch name pattern:** Enter `main`
2. Check the following boxes:

   **Protect matching branches:**
   - [x] Require a pull request before merging
     - [x] Require approvals: `1`
     - [x] Dismiss stale pull request approvals when new commits are pushed
     - [x] Require review from Code Owners

   **Require status checks to pass before merging:**
   - [x] Require status checks to pass before merging
   - [x] Require branches to be up to date before merging
   - Search and select: `ontology-freeze-guard`, `ontology-changelog-check`

   **Additional settings:**
   - [x] Require conversation resolution before merging
   - [x] Do not allow bypassing the above settings

3. Click **Create** or **Save changes**

### Step 3: Verify CODEOWNERS

1. Ensure `.github/CODEOWNERS` file exists in the repository
2. Create the team `@rasaha/ontology-stewards` with appropriate members
3. Test by creating a PR that modifies a protected file

---

## 5. Configuration via GitHub API

For automated setup, use the GitHub API:

```bash
# Example using gh CLI
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ontology-freeze-guard","ontology-changelog-check"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":true,"required_approving_review_count":1}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

---

## 6. Ontology Change Workflow

When an ontology change is necessary (rare), follow this workflow:

### 6.1 Pre-Change Requirements

1. **Justification:** Document why the change is necessary
2. **Version Bump:** Increment `meta.version` in the JSON file
3. **Changelog:** Add entry to `docs/ontology/CHANGELOG.md`
4. **Migration:** Document migration steps if applicable

### 6.2 PR Process

1. Create a feature branch
2. Make the ontology changes following the requirements above
3. Open a PR against `main`
4. Request review from `@rasaha/ontology-stewards`
5. Address all review comments
6. Wait for CI to pass
7. Obtain code owner approval
8. Merge

### 6.3 Post-Change Actions

1. Update Phase-4A loader if version changed
2. Run full test suite to verify compatibility
3. Document any breaking changes

---

## 7. Emergency Procedures

In case of critical issues requiring immediate ontology fixes:

1. **Do NOT bypass branch protection**
2. Create an emergency PR with `[EMERGENCY]` prefix
3. Document the issue severity and justification
4. Request expedited review from ontology stewards
5. Follow up with proper documentation after the fix

---

## 8. Troubleshooting

### Problem: PR blocked by Code Owners

**Solution:** Request review from a member of `@rasaha/ontology-stewards`

### Problem: Status checks not appearing

**Solution:**
1. Verify the workflow file exists in `.github/workflows/`
2. Ensure the workflow triggers on the PR's base branch
3. Check workflow run logs for errors

### Problem: Stale review after changes

**Solution:** This is expected behavior. Request re-review after making changes.

---

## 9. Related Documentation

- [ONTOLOGY_FREEZE_CONTRACT.md](../../ONTOLOGY_FREEZE_CONTRACT.md) - Full ontology freeze rules
- [docs/ontology/CHANGELOG.md](../ontology/CHANGELOG.md) - Ontology change history
- [.github/CODEOWNERS](../../.github/CODEOWNERS) - Code ownership definitions

---

**Last Updated:** 2025-12-18
