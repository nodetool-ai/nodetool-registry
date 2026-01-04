# NodeTool Release Automation

This directory contains tools for automating releases across the NodeTool ecosystem. It is part of the [nodetool-registry](https://github.com/nodetool-ai/nodetool-registry) repository.

## Contents

- `release.py` - Python script for releasing NodeTool packages

## Local Setup

```bash
# Clone nodetool-registry (contains release tools in release/)
git clone https://github.com/nodetool-ai/nodetool-registry.git
cd nodetool-registry

# Clone all nodetool repositories
for repo in nodetool-core nodetool-apple nodetool-base nodetool-comfy nodetool-elevenlabs \
            nodetool-fal nodetool-huggingface nodetool-lib-ml nodetool-mlx \
            nodetool-lib-audio nodetool-replicate nodetool-whispercpp \
            nodetool; do
  git clone "https://github.com/nodetool-ai/$repo.git"
done

# Install uv (for dependency management and lock file generation)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install nodetool-core (required for package scan)
cd nodetool-core
uv sync
cd ..

# Enter release directory and install
cd release
uv sync

# Authenticate with gh (for pushing tags)
gh auth login
```

## Usage

### Local Release (Single Repository)

```bash
cd release
python release.py v0.6.2-rc.20 --update-versions --repo nodetool-lib-audio
```

### Local Release (All Repositories)

```bash
cd release
python release.py v0.6.2-rc.20 --update-versions
```

### GitHub Actions Release

1. Go to [Release workflow](https://github.com/nodetool-ai/nodetool-registry/actions/workflows/release.yml)
2. Click "Run workflow"
3. Fill in:
   - **Version**: e.g., `v0.6.2-rc.20`
   - **Repository**: (optional, leave empty for all)
   - **Update version files**: `true` (recommended)

## Version Format

Version tags must follow semantic versioning with a `v` prefix:

```
v<major>.<minor>.<patch>[-<prerelease>]
```

Examples:
- `v1.0.0` - stable release
- `v0.6.2-rc.20` - release candidate

## Repositories

The release process handles these repositories:

| Repository | Type | Notes |
|------------|------|-------|
| nodetool-core | Python | Core library, released first |
| nodetool-apple | Python | Apple Silicon nodes |
| nodetool-base | Python | Base node collection |
| nodetool-comfy | Python | ComfyUI integration |
| nodetool-elevenlabs | Python | ElevenLabs API |
| nodetool-fal | Python | FAL AI integration |
| nodetool-huggingface | Python | HuggingFace models |
| nodetool-lib-ml | Python | ML utilities |
| nodetool-mlx | Python | MLX (Apple Silicon) |
| nodetool-lib-audio | Python | Audio processing |
| nodetool-replicate | Python | Replicate API |
| nodetool-whispercpp | Python | Whisper.cpp bindings |
| nodetool | TypeScript | Desktop app (web/electron) |

## What Gets Updated

When `--update-versions` is enabled:

1. **pyproject.toml** - version and nodetool-core dependency pinning
2. **.github/workflows/copilot-setup-steps.yml** - NODETOOL_CORE_REF
3. **Dockerfiles** - git package refs and PyPI versions
4. **package_metadata/*.json** - regenerated via `nodetool package scan`
5. **web/package.json**, **electron/package.json**, **mobile/package.json** - version
6. **web/src/config/constants.ts** - VERSION constant
7. **uv.lock** - generated for reproducible dependency resolution

## Prerequisites

- Python 3.11+
- `uv` CLI tool (install via `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- `gh` CLI tool authenticated with GitHub
- `GH_PAT` secret with `repo` scope

1. Create a Personal Access Token (classic):
   - Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `repo` scope

2. Add as repository secret:
   - Go to repository Settings → Secrets and variables → Actions
   - Add secret: `GH_PAT`

## Troubleshooting

### Package scan fails

Ensure nodetool-core is installed:
```bash
cd nodetool-core && pip install -e .
```

### Permission denied when pushing

Re-authenticate with gh:
```bash
gh auth login
```

### Version format error

Make sure your version tag starts with `v`:
```bash
# Correct
python release.py v1.2.3

# Incorrect
python release.py 1.2.3
```
