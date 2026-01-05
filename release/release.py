#!/usr/bin/env python3
"""
Release script for the NodeTool monorepo.

This script automates the release process across multiple NodeTool repositories,
handling version updates, git tagging, GitHub Actions workflow monitoring, and
registry index generation.

PROCESS OVERVIEW:

1. Phase 1 - nodetool-core (priority):
   - Updates version in pyproject.toml if --update-versions is specified
   - Creates and pushes git tag with the version tag (e.g., v1.2.3)
   - Waits for the GitHub Actions release workflow to complete (unless --no-wait-core)
   - Only proceeds after nodetool-core is successfully published

2. Phase 2 - Remaining repositories:
   - For each repository in REPOS (excluding nodetool-core):
     * Updates version files if --update-versions is enabled:
       - pyproject.toml: version field and nodetool-core dependency pinning
       - .github/workflows/copilot-setup-steps.yml: NODETOOL_CORE_REF
       - Dockerfiles: git package reference tags
       - package_metadata/*.json: regenerated via `nodetool package scan`
     * For nodetool repo specifically:
       - web/package.json: version field
       - electron/package.json: version field
       - web/src/config/constants.ts: VERSION constant
     * Commits changes with message "Bump version to <version>"
     * Pushes commit to main branch
     * Creates and pushes git tag

3. Workflow Monitoring:
   - Polls GitHub Actions for release workflows (Build and Publish Wheel, Release)
   - Waits up to 30 minutes (MAX_WAIT) with 30-second intervals (POLL_INTERVAL)
   - Displays workflow logs if any release fails
   - Exits with error if any workflow fails or is cancelled

4. Registry Workflow:
   - Triggers the registry workflow in nodetool-registry to rebuild the package index
   - Provides GitHub Actions URL for monitoring the workflow

VERSION UPDATE DETAILS:

When --update-versions is enabled:
- Version format: v<major>.<minor>.<patch> (e.g., v1.2.3)
- Updates all pyproject.toml files with the new version
- Pins nodetool-core dependencies to exact version across all repos
- Regenerates package_metadata JSON files using `nodetool package scan`
- Updates all relevant Dockerfiles to reference the new tag
- Updates VERSION constants in TypeScript files

USAGE:

    python release.py <version_tag> [options]

ARGUMENTS:

    version_tag        Version tag following format v<major>.<minor>.<patch>
                       Example: v1.2.3

OPTIONS:

    -u, --update-versions
                       Enable version file updates. Without this flag, the script
                       only creates and pushes tags without modifying any files.

    --no-wait-core     Skip waiting for nodetool-core workflow to complete.
                       By default, the script waits for nodetool-core to publish
                       before processing other repositories to ensure they can
                       depend on the new version.

    --repo             Only process this specific repository (e.g., nodetool-lib-audio)

REPOSITORIES PROCESSED:

The script processes these repositories in order:
- nodetool-core (always first, waited for by default)
- nodetool-apple, nodetool-base, nodetool-comfy, nodetool-elevenlabs
- nodetool-fal, nodetool-huggingface, nodetool-lib-ml, nodetool-mlx
- nodetool-lib-audio, nodetool-replicate, nodetool-whispercpp
- nodetool (main desktop application)

EXAMPLES:

    # Release with version updates (full process)
    python release.py v1.2.3 --update-versions

    # Release without version updates (just tagging)
    python release.py v1.2.3

    # Release without waiting for nodetool-core (risky if dependencies break)
    python release.py v1.2.3 --update-versions --no-wait-core

    # Release only a single repository
    python release.py v1.2.3 --update-versions --repo nodetool-lib-audio

PREREQUISITES:

- All repositories must be in sibling directories in the current working directory
- GitHub authentication token (GH_PAT, GITHUB_TOKEN, or GH_TOKEN) must be set in environment
- `gh` CLI tool must be installed for workflow monitoring
- `nodetool` CLI tool must be installed and in PATH (for package scan)
- All repositories must have clean git working directories
- Each repository must be a valid git repository

EXIT CODES:

    0    Success - All workflows completed and registry triggered
    1    Failure - Workflow failed, timeout, or missing dependencies
"""

import argparse
import sys
import os
import re
import subprocess
import json
import time
from pathlib import Path
from typing import List, Optional

# Colors for output
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"  # No Color


def print_info(msg):
    print(f"{GREEN}[INFO]{NC} {msg}")


def print_error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")


def print_warning(msg):
    print(f"{YELLOW}[WARNING]{NC} {msg}")


def setup_git_auth(repo_path: Path) -> bool:
    """
    Configure git to use GH_PAT, GITHUB_TOKEN, or GH_TOKEN for authentication if available.
    Returns True if authentication was configured, False otherwise.
    """
    gh_token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    if not gh_token:
        print_warning("No GH_PAT, GITHUB_TOKEN, or GH_TOKEN found in environment")
        return False
    
    # Get the remote URL
    result = run_command(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        check=False,
        capture_output=True
    )
    
    if result.returncode != 0:
        print_warning(f"Could not get remote URL for {repo_path}")
        return False
    
    remote_url = result.stdout.strip()
    print_info(f"Original remote URL: {remote_url}")
    
    # Convert to authenticated HTTPS URL if needed
    if remote_url.startswith("https://github.com/"):
        # Already HTTPS, update to include token
        auth_url = remote_url.replace(
            "https://github.com/",
            f"https://x-access-token:{gh_token}@github.com/"
        )
    elif remote_url.startswith("git@github.com:"):
        # Convert SSH to HTTPS with token
        repo_part = remote_url.replace("git@github.com:", "").replace(".git", "")
        auth_url = f"https://x-access-token:{gh_token}@github.com/{repo_part}.git"
    else:
        print_warning(f"Unexpected remote URL format: {remote_url}")
        return False
    
    # Set the authenticated URL
    run_command(
        ["git", "remote", "set-url", "origin", auth_url],
        cwd=repo_path,
        check=True,
        capture_output=True
    )
    
    print_info(f"Configured git authentication for {repo_path}")
    return True


def print_git_diagnostics(repo_path: Path):
    """Print diagnostic information about git configuration"""
    print_info(f"\n=== Git Diagnostics for {repo_path} ===")
    
    # Check git user config
    for cmd, desc in [
        (["git", "config", "user.name"], "user.name"),
        (["git", "config", "user.email"], "user.email"),
        (["git", "remote", "-v"], "remotes"),
        (["git", "status", "--porcelain"], "status"),
        (["git", "branch", "--show-current"], "current branch"),
    ]:
        result = run_command(cmd, cwd=repo_path, check=False, capture_output=True)
        if result.returncode == 0:
            output = result.stdout.strip() if result.stdout else "(empty)"
            print_info(f"  {desc}: {output}")
        else:
            print_warning(f"  {desc}: Failed to get")
    
    # Check if we're in a git repo
    is_git_repo = (repo_path / ".git").is_dir()
    print_info(f"  Is git repository: {is_git_repo}")
    
    # Check environment variables
    for var in ["GH_PAT", "GITHUB_TOKEN", "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL"]:
        val = os.environ.get(var)
        if val:
            # Mask token values
            if "TOKEN" in var or "PAT" in var:
                masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
                print_info(f"  {var}: {masked}")
            else:
                print_info(f"  {var}: {val}")
        else:
            print_warning(f"  {var}: not set")
    
    print_info("=== End Diagnostics ===\n")


REPOS = [
    "nodetool-core",
    "nodetool-apple",
    "nodetool-base",
    "nodetool-comfy",
    "nodetool-elevenlabs",
    "nodetool-fal",
    "nodetool-huggingface",
    "nodetool-lib-ml",
    "nodetool-mlx",
    "nodetool-lib-audio",
    "nodetool-replicate",
    "nodetool-whispercpp",
]


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    check=True,
    capture_output=True,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    try:
        # Log command for diagnostics
        print_info(f"Running: {' '.join(cmd)} (cwd={cwd})")
        result = subprocess.run(
            cmd, cwd=cwd, check=check, capture_output=capture_output, text=True, env=env
        )
        if result.returncode != 0 and not check:
            print_warning(f"Command returned {result.returncode}")
            if result.stdout:
                print(f"stdout: {result.stdout}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
        return result
    except subprocess.CalledProcessError as e:
        if check:
            print_error(f"Command failed: {' '.join(cmd)}")
            print_error(f"Exit code: {e.returncode}")
            if e.stdout:
                print(f"stdout: {e.stdout}")
            if e.stderr:
                print(f"stderr: {e.stderr}")
            raise
        return e


def update_nodetool_core_dependency(file_path: Path, version: str) -> bool:
    if not file_path.exists():
        return False

    text = file_path.read_text()
    if "nodetool-core" not in text:
        return False

    pattern = re.compile(r'"nodetool-core[^"]*"')
    updated = False

    def replacement(match):
        nonlocal updated
        start = match.start()
        line_start = text.rfind("\n", 0, start) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)

        line = text[line_start:line_end]
        if re.search(r"^\s*name\s*=", line):
            return match.group(0)

        updated = True
        return f'"nodetool-core=={version}"'

    new_text = pattern.sub(replacement, text)

    if updated and new_text != text:
        file_path.write_text(new_text)
        print_info(
            f"  Pinned nodetool-core dependencies to {version} in {file_path.name}"
        )
        return True
    return False


def update_package_json_version(file_path: Path, version: str) -> bool:
    if not file_path.exists():
        return False

    try:
        data = json.loads(file_path.read_text())
        if data.get("version") == version:
            return False

        data["version"] = version
        file_path.write_text(json.dumps(data, indent=2) + "\n")
        print_info(f"  Updated version in {file_path}")
        return True
    except json.JSONDecodeError:
        print_warning(f"  Could not parse JSON in {file_path}")
        return False


def update_constants_version(file_path: Path, version: str) -> bool:
    if not file_path.exists():
        return False

    text = file_path.read_text()
    pattern = r'(export const VERSION = ")[^"]+(")'
    new_text, count = re.subn(pattern, f"\g<1>{version}\g<2>", text, count=1)

    if count > 0 and new_text != text:
        file_path.write_text(new_text)
        print_info(f"  Updated VERSION constant in {file_path}")
        return True
    return False


def update_pyproject_version(file_path: Path, version: str) -> bool:
    if not file_path.exists():
        return False

    print_info(f"  Updating version in {file_path.name}...")
    text = file_path.read_text()
    pattern = re.compile(r'^(\s*)version = "[^"]+"', re.MULTILINE)

    new_text, count = pattern.subn(f'\g<1>version = "{version}"', text)

    if count > 0:
        file_path.write_text(new_text)
        print_info(f"  Updated {file_path.name}")
        return True
    return False


def update_copilot_core_ref(file_path: Path, version_tag: str) -> bool:
    if not file_path.exists():
        return False

    text = file_path.read_text()
    pattern = re.compile(r"^(\s*NODETOOL_CORE_REF:\s*)(\S+)(\s*)$", re.MULTILINE)
    new_text, count = pattern.subn(rf"\1{version_tag}\3", text)

    if count > 0 and new_text != text:
        file_path.write_text(new_text)
        print_info(f"  Updated NODETOOL_CORE_REF in {file_path}")
        return True
    return False


def update_git_package_refs(file_path: Path, version_tag: str) -> bool:
    if not file_path.exists():
        return False

    text = file_path.read_text()
    pattern = re.compile(
        r"(git\+https://github\.com/nodetool-ai/[^\s\"']+?\.git@)([^\s\"'\\]+)"
    )
    new_text, count = pattern.subn(rf"\1{version_tag}", text)

    if count > 0 and new_text != text:
        file_path.write_text(new_text)
        print_info(f"  Updated git package refs in {file_path}")
        return True
    return False


def update_dockerfile_pypi_versions(file_path: Path, version: str) -> bool:
    if not file_path.exists():
        return False

    text = file_path.read_text()
    updated = False

    pattern = re.compile(r"(nodetool-[a-z-]+)==([0-9]+\.[0-9]+\.[0-9]+[^\s\"]*)")
    new_text, count = pattern.subn(rf"\1=={version}", text)
    if count > 0 and new_text != text:
        text = new_text
        updated = True

    if updated and text != file_path.read_text():
        file_path.write_text(text)
        print_info(f"  Updated PyPI package versions in {file_path}")
        return True
    return False


def find_dockerfiles(repo_path: Path) -> List[Path]:
    return [
        path
        for path in repo_path.rglob("Dockerfile*")
        if path.is_file()
        and ".venv" not in path.parts
        and "node_modules" not in path.parts
    ]


def find_metadata_dirs(repo_path: Path) -> List[Path]:
    found = []
    for path in repo_path.rglob("package_metadata"):
        if (
            path.is_dir()
            and ".git" not in path.parts
            and ".venv" not in path.parts
            and "node_modules" not in path.parts
        ):
            found.append(path)
    return found


def run_package_scan(repo_path: Path) -> bool:
    if repo_path.name == "nodetool-core":
        print_info("  Skipping nodetool package scan for nodetool-core")
        return False
    print_info(f"  Running nodetool package scan in {repo_path.name}...")
    cmd = ["nodetool", "package", "scan"]
    try:
        run_command(cmd, cwd=repo_path, check=True)
        print_info(f"  nodetool package scan completed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_warning(f"  Failed to run nodetool package scan in {repo_path.name}")
        return False


def generate_uv_lock(repo_path: Path) -> bool:
    pyproject_path = repo_path / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    print_info(f"  Generating uv.lock in {repo_path.name}...")

    result = run_command(
        ["uv", "lock"],
        cwd=repo_path,
        check=False,
        capture_output=True,
    )
    if result.returncode == 0:
        lock_path = repo_path / "uv.lock"
        if lock_path.exists():
            print_info(f"  Generated uv.lock in {repo_path.name}")
            return True
    else:
        print_warning(f"  Failed to generate uv.lock in {repo_path.name}")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[:5]:
                print(f"    {line}")
    return False


def get_release_run(repo_path: Path, tag: str) -> tuple[Optional[dict], bool]:
    cmd = [
        "gh",
        "run",
        "list",
        "--limit",
        "20",
        "--json",
        "databaseId,status,conclusion,headBranch,headSha,event,workflowName",
    ]
    try:
        proc = run_command(cmd, cwd=repo_path, check=True)
        runs = json.loads(proc.stdout)
    except (json.JSONDecodeError, subprocess.CalledProcessError):
        return None, False

    RELEASE_WORKFLOWS = ["Build and Publish Wheel", "Release"]

    for run in runs:
        branch = run.get("headBranch", "")
        workflow_name = run.get("workflowName", "")

        if branch == tag:
            if workflow_name in RELEASE_WORKFLOWS:
                return run, True

    return None, True


def print_workflow_logs(repo_path: Path, tag: str) -> None:
    run, ok = get_release_run(repo_path, tag)
    if not ok:
        print_warning("  Could not fetch workflow logs (gh run list failed)")
        return
    if not run or not run.get("databaseId"):
        print_warning("  Could not find workflow run to fetch logs")
        return

    run_id = str(run["databaseId"])
    print_info(f"  Fetching workflow logs (run {run_id})...")
    proc = run_command(
        ["gh", "run", "view", run_id, "--log"], cwd=repo_path, check=False
    )
    if proc.returncode == 0 and proc.stdout:
        print(proc.stdout)
    else:
        print_warning("  Failed to retrieve workflow logs")


def check_workflow_completed(repo_path: Path, tag: str) -> int:
    run, ok = get_release_run(repo_path, tag)
    if not ok:
        proc_release = run_command(
            ["gh", "release", "view", tag], cwd=repo_path, check=False
        )
        if proc_release.returncode == 0:
            return 0
        return 1

    if not run:
        proc_release = run_command(
            ["gh", "release", "view", tag], cwd=repo_path, check=False
        )
        if proc_release.returncode == 0:
            return 0
        return 1

    status = run.get("status")
    conclusion = run.get("conclusion")

    if status == "completed":
        if conclusion == "success":
            return 0
        if conclusion in ["failure", "cancelled"]:
            return 2
        return 0

    return 1


REGISTRY_WORKFLOW_ID = "188184531"
MAX_WAIT = 1800  # 30 minutes
POLL_INTERVAL = 30  # 30 seconds


def process_repo(
    repo: str,
    repos_to_process: List[str],
    version: str,
    version_tag: str,
    args,
    cwd: Path,
):
    repo_path = cwd / repo
    print_info(f"DEBUG process_repo: cwd={cwd}, repo={repo}, repo_path={repo_path}, exists={repo_path.exists()}, is_dir={repo_path.is_dir()}")
    
    if not repo_path.is_dir():
        print_error(f"Repository directory '{repo}' not found. Skipping...")
        return

    if not (repo_path / ".git").is_dir():
        print_error(f"{repo} is not a git repository. Skipping...")
        return

    # Print diagnostics before starting
    print_git_diagnostics(repo_path)
    
    # Set up git authentication
    setup_git_auth(repo_path)

    print_info(f"Processing {repo}...")

    files_updated = False
    is_nodetool = repo == "nodetool"

    pyproject_path = repo_path / "pyproject.toml"
    copilot_workflow = repo_path / ".github/workflows/copilot-setup-steps.yml"
    dockerfiles = []

    if args.update_versions and not is_nodetool:
        if update_pyproject_version(pyproject_path, version):
            files_updated = True

        if update_nodetool_core_dependency(pyproject_path, version):
            files_updated = True

        if update_copilot_core_ref(copilot_workflow, version_tag):
            files_updated = True

        dockerfiles = find_dockerfiles(repo_path)
        for dockerfile in dockerfiles:
            if update_git_package_refs(dockerfile, version_tag):
                files_updated = True
            if update_dockerfile_pypi_versions(dockerfile, version):
                files_updated = True

        metadata_dirs = find_metadata_dirs(repo_path)

        if (repo_path / "pyproject.toml").exists() or metadata_dirs:
            if run_package_scan(repo_path):
                files_updated = True

    if args.update_versions and is_nodetool:
        if update_package_json_version(repo_path / "web/package.json", version):
            files_updated = True
        if update_package_json_version(repo_path / "electron/package.json", version):
            files_updated = True
        if update_package_json_version(repo_path / "mobile/package.json", version):
            files_updated = True
        if update_constants_version(repo_path / "web/src/config/constants.ts", version):
            files_updated = True

        if pyproject_path.exists() and not is_nodetool:
            if generate_uv_lock(repo_path):
                files_updated = True

    if files_updated:
        print_info("  Staging version updates...")
        if pyproject_path.exists():
            run_command(["git", "add", "pyproject.toml"], cwd=repo_path)

        lock_path = repo_path / "uv.lock"
        if lock_path.exists():
            run_command(["git", "add", "uv.lock"], cwd=repo_path)

        metadata_dirs = find_metadata_dirs(repo_path)

        for metadata_dir in metadata_dirs:
            if metadata_dir.exists():
                for f in metadata_dir.glob("*.json"):
                    try:
                        rel_path = f.relative_to(repo_path)
                        run_command(["git", "add", str(rel_path)], cwd=repo_path)
                    except ValueError:
                        print_warning(f"  Skipping {f} (not relative to repo root)")

        if is_nodetool:
            for f in [
                "web/package.json",
                "electron/package.json",
                "mobile/package.json",
                "web/src/config/constants.ts",
            ]:
                if (repo_path / f).exists():
                    run_command(["git", "add", f], cwd=repo_path)
        if copilot_workflow.exists():
            run_command(
                ["git", "add", str(copilot_workflow.relative_to(repo_path))],
                cwd=repo_path,
            )
        for dockerfile in dockerfiles:
            if dockerfile.exists():
                try:
                    rel_path = dockerfile.relative_to(repo_path)
                    run_command(["git", "add", str(rel_path)], cwd=repo_path)
                except ValueError:
                    print_warning(
                        f"  Skipping {dockerfile} (not relative to repo root)"
                    )

        print_info("  Committing version updates...")
        proc = run_command(
            ["git", "commit", "-m", f"Bump version to {version}"],
            cwd=repo_path,
            check=False,
        )
        if proc.returncode == 0:
            print_info("  Committed version changes")
            print_info("  Pushing commit to remote (main)...")
            push_result = run_command(
                ["git", "push", "-v", "origin", "main"], 
                cwd=repo_path, 
                check=False
            )
            if push_result.returncode == 0:
                print_info("  Pushed commit")
            else:
                print_error(f"  Failed to push commit for {repo}")
                print_error(f"  stdout: {push_result.stdout if push_result.stdout else '(empty)'}")
                print_error(f"  stderr: {push_result.stderr if push_result.stderr else '(empty)'}")
                # Print diagnostics again after failure
                print_git_diagnostics(repo_path)
                return
        else:
            print_warning(
                f"  No changes to commit (files may already be at version {version})"
            )
    else:
        print_info("  No version files found to update")

    print_info(f"  Creating tag {version_tag} in {repo}...")
    run_command(
        ["git", "tag", "-f", "-a", version_tag, "-m", f"Release {version_tag}"],
        cwd=repo_path,
    )

    print_info(f"  Pushing tag {version_tag} to remote...")
    push_result = run_command(
        ["git", "push", "-v", "-f", "origin", version_tag], 
        cwd=repo_path, 
        check=False
    )
    if push_result.returncode == 0:
        print_info(f"  Successfully tagged and pushed {repo}")
    else:
        print_error(f"  Failed to push tag for {repo}")
        print_error(f"  stdout: {push_result.stdout if push_result.stdout else '(empty)'}")
        print_error(f"  stderr: {push_result.stderr if push_result.stderr else '(empty)'}")
        # Print diagnostics again after failure
        print_git_diagnostics(repo_path)


def wait_for_repos(repos_to_wait: List[str], version_tag: str, cwd: Path):
    elapsed = 0
    logged_failures = set()

    while elapsed < MAX_WAIT:
        all_completed = True
        any_failed = False

        for repo in repos_to_wait:
            repo_path = cwd / repo
            if not repo_path.is_dir():
                continue

            result = check_workflow_completed(repo_path, version_tag)

            if result == 0:
                print_info(f"  Release workflow completed for {repo}")
            elif result == 2:
                print_error(f"  Release workflow failed or cancelled for {repo}")
                if repo not in logged_failures:
                    print_workflow_logs(repo_path, version_tag)
                    logged_failures.add(repo)
                any_failed = True
                all_completed = False
            else:
                print_warning(f"  Waiting for release workflow in {repo}...")
                all_completed = False

        if all_completed:
            if any_failed:
                print_error("Some release workflows failed or were cancelled")
                sys.exit(1)
            return

        if elapsed < MAX_WAIT:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL
            print_info(f"Elapsed time: {elapsed}s / {MAX_WAIT}s")

    print_error("Timeout waiting for release workflows to complete")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Release script for nodetool repositories"
    )
    parser.add_argument("version_tag", help="Version tag (e.g., v1.2.3)")
    parser.add_argument(
        "-u", "--update-versions", action="store_true", help="Update version files"
    )
    parser.add_argument(
        "--no-wait-core",
        action="store_true",
        help="Don't wait for nodetool-core to complete",
    )
    parser.add_argument("--repo", help="Only process this specific repository")

    args = parser.parse_args()
    version_tag = args.version_tag

    print_info("=== Initial Environment Diagnostics ===")
    print_info(f"Working directory: {os.getcwd()}")
    print_info(f"Script location: {Path(__file__).resolve()}")
    
    # Check for required environment variables
    for var in ["GH_PAT", "GITHUB_TOKEN", "GH_TOKEN"]:
        val = os.environ.get(var)
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
            print_info(f"{var}: {masked}")
        else:
            print_warning(f"{var}: not set")
    
    print_info("=== End Initial Diagnostics ===\n")

    if not version_tag.startswith("v"):
        print_warning(
            "Version tag should follow format: v<major>.<minor>.<patch> (e.g., v1.2.3)"
        )
        response = input("Continue anyway? (y/n) ")
        if response.lower() not in ["y", "yes"]:
            sys.exit(1)

    version = version_tag[1:]

    repos_to_process = REPOS
    if args.repo:
        if args.repo not in REPOS:
            print_error(
                f"Repository '{args.repo}' not in known repos: {', '.join(REPOS)}"
            )
            sys.exit(1)
        repos_to_process = [args.repo]
        print_info(f"Processing only repository: {args.repo}")

    print_info(f"Starting release process for version: {version_tag}")
    if args.update_versions:
        print_info("Version updates: ENABLED")
    else:
        print_info("Version updates: DISABLED (use --update-versions to enable)")
    print_info(f"Repositories to tag: {', '.join(repos_to_process)}")

    cwd = Path(__file__).resolve().parent.parent
    print_info(f"Working directory: {cwd}")
    print_info(f"Contents: {list(cwd.iterdir())}")
    nodetool_core_path = cwd / "nodetool-core"
    print_info(f"nodetool-core exists: {nodetool_core_path.exists()}, is_dir: {nodetool_core_path.is_dir()}, is_symlink: {nodetool_core_path.is_symlink()}")
    if nodetool_core_path.is_dir():
        git_path = nodetool_core_path / ".git"
        print_info(f"nodetool-core/.git exists: {git_path.exists()}, is_dir: {git_path.is_dir()}")

    print_info("Step 1a: Processing nodetool-core...")
    if not args.repo:
        process_repo("nodetool-core", repos_to_process, version, version_tag, args, cwd)
        if not args.no_wait_core:
            print_info("Waiting for nodetool-core workflow to complete...")
            wait_for_repos(["nodetool-core"], version_tag, cwd)
            print_info("nodetool-core has been published!")

    print_info("Step 1b: Creating and pushing tags...")
    for repo in repos_to_process:
        process_repo(repo, repos_to_process, version, version_tag, args, cwd)

    print_info("Step 2: Waiting for release workflows to complete...")
    wait_for_repos(repos_to_process, version_tag, cwd)
    print_info("All release workflows have completed!")

    print_info("Step 3: Triggering registry workflow to build index...")
    registry_path = cwd

    cmd = ["gh", "workflow", "run", REGISTRY_WORKFLOW_ID]
    if run_command(cmd, cwd=registry_path, check=False).returncode == 0:
        print_info(
            f"Successfully triggered registry workflow (ID: {REGISTRY_WORKFLOW_ID})"
        )

        proc = run_command(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            cwd=registry_path,
            check=False,
        )
        if proc.returncode == 0:
            repo_full_name = proc.stdout.strip()
            print_info(
                f"Monitor the workflow at: https://github.com/{repo_full_name}/actions/workflows/{REGISTRY_WORKFLOW_ID}"
            )
    else:
        print_error("Failed to trigger registry workflow")
        sys.exit(1)

    print_info("=" * 50)
    print_info("Release process completed successfully!")
    print_info(f"Version: {version_tag}")
    print_info(f"Tagged repositories: {len(repos_to_process)}")
    print_info("Registry workflow triggered")
    print_info("=" * 50)


if __name__ == "__main__":
    main()
