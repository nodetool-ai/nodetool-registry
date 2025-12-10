# NodeTool Package Registry Usage

## Installation

Install packages from the NodeTool registry:

```bash
# Install single package
pip install --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base

# Install multiple packages
pip install --index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base nodetool-huggingface

# Use as extra index (combines with PyPI)
pip install --extra-index-url https://nodetool-ai.github.io/nodetool-registry/simple/ nodetool-base
```

## Configuration

### pip.conf
```ini
[global]
extra-index-url = https://nodetool-ai.github.io/nodetool-registry/simple/
```

### requirements.txt
```
--extra-index-url https://nodetool-ai.github.io/nodetool-registry/simple/
nodetool-base>=0.6.0
nodetool-huggingface>=0.6.0
```

### pyproject.toml
```toml
[tool.pip]
extra-index-url = "https://nodetool-ai.github.io/nodetool-registry/simple/"

[project]
dependencies = [
    "nodetool-core>=0.6.0,<0.7.0",
]
```

## Environment Variables
```bash
export PIP_EXTRA_INDEX_URL="https://nodetool-ai.github.io/nodetool-registry/simple/"
```

## Development

For local development, you can build and serve the index:

```bash
# Clone registry
git clone https://github.com/nodetool-ai/nodetool-registry.git
cd nodetool-registry

# Build index
python scripts/build_index.py --output-dir docs/simple

# Serve locally
python -m http.server 8000 --directory docs
# Then use: pip install --index-url http://localhost:8000/simple/ nodetool-base
```
