# Nodetool Packs Registry

## Overview

The Nodetool Packs Registry manages the installation, management, and distribution of node packs within the Nodetool ecosystem. The registry operates using two complementary systems:

1. **Wheel-based Package Index** (PEP 503 compliant) - Hosted at https://nodetool-ai.github.io/nodetool-registry/simple/ for fast, reliable package installation via `uv pip install`
2. **Package Metadata Registry** (`index.json`) - Provides discovery, descriptions, and browsing functionality for the Nodetool UI

Pack installation is handled by uv/pip using pre-built wheel files, while the Nodetool UI and CLI tools provide interfaces for discovering and managing node packs.

## For Users

### Pack Management in Nodetool UI

The primary interface for managing packs is through the Nodetool UI, which provides a user-friendly way to:

- Browse available node packs from the registry metadata
- Install/uninstall packs (using uv pip with wheel index under the hood)
- Update packs to latest wheel versions
- View pack information and documentation

## For Node Developers

The CLI tool is available for developers to create and manage Nodetool packs.

Basic commands:

```bash
# List installed packs
nodetool package list

# Scan current directory for nodes and create metadata
nodetool package scan

# Initialize a new Nodetool pack
nodetool package init
```

### Creating a Node Pack

To create a pack that can be installed in Nodetool:

IMPORTANT: pack name MUST start with `nodetool-`

1. Create a new folder for your project

2. Run the `nodetool init` command:

```bash
$ nodetool init
Project name: nodetool-example
Description: My example Nodetool pack
Author (name <email>): John Smith <john@example.com>
✅ Successfully initialized Nodetool project
Created:
  - pyproject.toml
  - src/nodetool/nodes/nodetool-example
  - src/nodetool/pack_metadata/
```

3. Create your node classes:

```python
from pydantic import Field
from nodetool.workflows.base_node import BaseNode

class MyNode(BaseNode):
    """Example node implementation"""

    prompt: str = Field(
        default="Build me a website for my business.",
        description="Input prompt for the node"
    )

    async def process(self, context: ProcessingContext) -> str:
        # Your node implementation here
        return "Node output"
```

4. Generate pack metadata:

   - Run `nodetool package scan` in your pack repository
   - This will create `your_pack.json` file in `src/nodetool/pack_metadata`

5. Commit and publish your project to a Github repository

6. Register your pack in the Nodetool registry:
   - Fork this repository
   - Add your pack information to [index.json](index.json)
   - Submit a pull request

### Pack Requirements

Your pack should:

- Follow Python packaging best practices
- Include clear documentation for each node
- Provide example usage
- Include proper node metadata (generated via `nodetool scan`)

### Testing Your Pack

Before submitting to the registry:

1. Install your pack locally:

```bash
pip install -e .
```

2. Restart Nodetool UI

3. Verify your nodes appear in the Nodetool UI

## Pack Registry

The Nodetool packs registry is hosted at [nodetool-registry](https://github.com/nodetool-ai/nodetool-registry). The registry maintains:

- Pack metadata in `index.json`
- Installation instructions
- Version information
- Node documentation

Each pack in the registry includes:

- Name
- Description
- Repository ID (owner/project format)
- Namespaces provided
- Node metadata

## License

This pack management system is part of the Nodetool project. See the main [project repository](https://github.com/nodetool-ai/nodetool) for license information.
