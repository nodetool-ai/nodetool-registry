# NodeTool Registry Deployment Guide 🚀

## Overview

This guide covers setting up the centralized NodeTool package registry with GitHub-hosted wheels.

## Architecture

```
Individual Repos (nodetool-base, etc.)
├── Tag push (v1.0.0)
├── GitHub Action builds wheel
├── Creates GitHub Release with wheel
└── Notifies nodetool-registry

nodetool-registry
├── Receives notification
├── Updates package index
├── Deploys to GitHub Pages
└── Serves at packages.nodetool.ai
```

## Setup Steps

### 1. Set up nodetool-registry Repository

```bash
# Create repository structure
nodetool-registry/
├── .github/workflows/
│   ├── build-index.yml           # Main index builder
│   ├── monitor-releases.yml      # Release monitoring  
│   └── coordinated-release.yml   # Coordinated releases
├── scripts/
│   ├── build_index.py           # Index generation script
│   └── generate_metadata.py     # Metadata generator
├── docs/                        # GitHub Pages content
│   ├── simple/                  # PEP 503 index
│   ├── packages.json           # Package manifest
│   └── registry.json           # Registry info
└── README.md
```

### 2. Configure GitHub Secrets

#### nodetool-registry secrets:
```bash
# GitHub token with repo access to all NodeTool repos
RELEASE_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Standard GitHub token (automatically available)
GITHUB_TOKEN
```

#### Individual repo secrets:
```bash
# Token to notify registry (same as RELEASE_TOKEN)
REGISTRY_UPDATE_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"

# Standard GitHub token
GITHUB_TOKEN
```

### 3. Deploy Individual Repository Workflows

Copy `publish-wheel.yml` to each package repository:

```bash
# For each repo (nodetool-base, nodetool-huggingface, etc.)
mkdir -p .github/workflows/
cp publish-wheel.yml .github/workflows/

# Commit and push
git add .github/workflows/publish-wheel.yml
git commit -m "Add wheel publishing workflow"
git push
```

### 4. Enable GitHub Pages

In `nodetool-registry` repository settings:
1. Go to **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: **gh-pages** (created by workflow)
4. Custom domain: **packages.nodetool.ai** (optional)

## Testing the Workflow

### Test 1: Individual Package Release

```bash
# Test with nodetool-base
cd nodetool-base

# Create test tag
git tag v0.6.0
git push origin v0.6.0

# This should trigger:
# 1. build-and-publish workflow in nodetool-base
# 2. Creates GitHub release with wheel
# 3. Notifies nodetool-registry  
# 4. Registry updates index
# 5. Deploys to GitHub Pages
```

### Test 2: Manual Registry Update

```bash
# Trigger registry update manually
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nodetool-ai/nodetool-registry/actions/workflows/build-index.yml/dispatches \
  -d '{"ref":"main","inputs":{"force_rebuild":"true"}}'
```

### Test 3: Coordinated Release

```bash
# Trigger coordinated release (dry run first)
# Go to nodetool-registry → Actions → Coordinated Release
# Run workflow with:
# - version: 0.6.0
# - dry_run: true

# Then run for real:
# - version: 0.6.0  
# - dry_run: false
```

### Test 4: Package Installation

```bash
# Test installation from registry
pip install --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base

# Test with extra index (fallback to PyPI)
pip install --extra-index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base

# Test specific version
pip install --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base==0.6.0
```

## Verification Steps

### Check Registry Index
```bash
# View root index
curl https://nodetool-ai.github.io/nodetool-registry/simple/

# View package index  
curl https://nodetool-ai.github.io/nodetool-registry/simple/nodetool-base/

# View metadata
curl https://nodetool-ai.github.io/nodetool-registry/packages.json
```

### Check Package Availability
```bash
# Check if package resolves
pip index versions nodetool-base \
  --index-url https://nodetool-ai.github.io/nodetool-registry/simple/

# Dry run install
pip install --dry-run --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base
```

## Monitoring and Maintenance

### GitHub Actions Monitoring
- Monitor workflow runs in each repository
- Check for failed releases or index updates
- Review logs for rate limiting or API issues

### Registry Health Check
```bash
# Daily health check script
#!/bin/bash
INDEX_URL="https://nodetool-ai.github.io/nodetool-registry"

echo "🔍 Checking registry health..."

# Check if index is accessible
if curl -s "$INDEX_URL/simple/" | grep -q "NodeTool Package Index"; then
    echo "✅ Index accessible"
else
    echo "❌ Index not accessible"
    exit 1
fi

# Check package count
PACKAGE_COUNT=$(curl -s "$INDEX_URL/packages.json" | jq -r '.count')
echo "📦 Packages: $PACKAGE_COUNT"

# Check recent updates
LAST_UPDATE=$(curl -s "$INDEX_URL/packages.json" | jq -r '.generated')
echo "⏰ Last update: $LAST_UPDATE"

echo "✅ Registry health check complete"
```

## Troubleshooting

### Common Issues

**1. Wheel not appearing in index**
```bash
# Check if release exists
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nodetool-ai/nodetool-base/releases/tags/v0.6.0

# Manually trigger index update
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nodetool-ai/nodetool-registry/dispatches \
  -d '{"event_type":"package-released","client_payload":{"package":"nodetool-base","version":"0.6.0"}}'
```

**2. GitHub API rate limiting**
```bash
# Check rate limit status
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/rate_limit
```

**3. Package dependencies not resolving**
```bash
# Verbose pip install to see resolution
pip install -v --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base

# Check dependency tree
pip show nodetool-base
```

### Recovery Procedures

**Full index rebuild:**
```bash
# Trigger complete rebuild
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/nodetool-ai/nodetool-registry/actions/workflows/build-index.yml/dispatches \
  -d '{"ref":"main","inputs":{"force_rebuild":"true"}}'
```

**Emergency fallback:**
```bash
# Users can install directly from releases
pip install https://github.com/nodetool-ai/nodetool-base/releases/download/v0.6.0/nodetool_base-0.6.0-py3-none-any.whl
```

## Benefits of This Architecture

✅ **Centralized Management**: Single registry for all packages  
✅ **Automatic Updates**: Index updates when packages release  
✅ **Fast Installation**: No git cloning, direct wheel downloads  
✅ **Standard Tools**: Works with pip, poetry, uv, etc.  
✅ **Scalable**: Can handle many packages and versions  
✅ **Reliable**: GitHub's infrastructure and CDN  
✅ **Cost-effective**: Free for public repositories  

## Next Steps

1. **Deploy registry**: Set up nodetool-registry repository
2. **Configure workflows**: Add workflows to all package repos  
3. **Test releases**: Create initial v0.6.0 releases
4. **Update dependencies**: Change packages to use version ranges
5. **Monitor and optimize**: Track usage and performance