#!/usr/bin/env python3
"""
Generate metadata and additional files for the package registry
"""

import json
import time
from pathlib import Path
from typing import Dict, Any

def generate_registry_info(output_dir: Path):
    """Generate registry information file"""
    registry_info = {
        "name": "NodeTool Package Registry",
        "description": "Official package registry for NodeTool AI workflow packages",
        "version": "1.0",
        "api_version": "2",
        "repository_version": "1.0",
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "index_url": "https://nodetool-ai.github.io/nodetool-registry/simple/",
        "packages_url": "https://nodetool-ai.github.io/nodetool-registry/packages.json",
        "source": "https://github.com/nodetool-ai/nodetool-registry",
        "maintainer": "NodeTool AI Team",
        "license": "MIT"
    }
    
    with open(output_dir / 'registry.json', 'w') as f:
        json.dump(registry_info, f, indent=2)

def generate_packages_manifest(output_dir: Path):
    """Generate packages manifest"""
    simple_dir = output_dir / 'simple'
    packages = []
    
    if simple_dir.exists():
        for package_dir in simple_dir.iterdir():
            if package_dir.is_dir() and (package_dir / 'index.html').exists():
                # Count wheels
                with open(package_dir / 'index.html', 'r') as f:
                    content = f.read()
                    wheel_count = content.count('.whl')
                
                packages.append({
                    "name": package_dir.name,
                    "url": f"https://nodetool-ai.github.io/nodetool-registry/simple/{package_dir.name}/",
                    "wheel_count": wheel_count,
                    "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                })
    
    packages_manifest = {
        "packages": sorted(packages, key=lambda x: x['name']),
        "count": len(packages),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(output_dir / 'packages.json', 'w') as f:
        json.dump(packages_manifest, f, indent=2)

def generate_usage_docs(output_dir: Path):
    """Generate usage documentation"""
    usage_md = """# NodeTool Package Registry Usage

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
"""
    
    with open(output_dir / 'usage.md', 'w') as f:
        f.write(usage_md)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate registry metadata')
    parser.add_argument('--output-dir', default='docs', help='Output directory')
    
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📋 Generating registry metadata...")
    
    generate_registry_info(output_dir)
    print("✅ Generated registry.json")
    
    generate_packages_manifest(output_dir)
    print("✅ Generated packages.json")
    
    generate_usage_docs(output_dir)
    print("✅ Generated usage.md")
    
    print("🎉 Metadata generation complete!")

if __name__ == '__main__':
    main()