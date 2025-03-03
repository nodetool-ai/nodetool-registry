# Nodetool Package Management System

## Overview

The Nodetool Package Management System is designed to handle the installation, management, and distribution of node packages within the Nodetool ecosystem. While most package management operations are handled through the Nodetool UI, this CLI tool provides direct access for advanced users and node developers.

## For Users

### Package Management in Nodetool UI

The primary interface for managing packages is through the Nodetool UI, which provides a user-friendly way to:

- Browse available node packages
- Install/uninstall packages
- Update packages
- View package information and documentation

### CLI Usage (Advanced)

The CLI tool is available for advanced users who need direct access to package management operations. This can be useful for:

- Troubleshooting installation issues
- Manual package management
- System administration tasks

Basic commands:

```bash
# List installed packages
nodetool-package list

# List available packages in the registry
nodetool-package list --available

# Install a package
nodetool-package install owner/project

# Uninstall a package
nodetool-package uninstall owner/project

# Update a package
nodetool-package update owner/project

# Show detailed package information
nodetool-package info owner/project
```

## For Node Developers

### Creating a Node Package

To create a package that can be installed in Nodetool:

1. Create a new Python package with the following structure:

```
your-package/
├── pyproject.toml
├── src/
│ └── your_package/
│ ├── init.py
│ └── nodes/
│ └── your_nodes.py
└── README.md
```

2. Configure your `pyproject.toml`:

```toml
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[tool.poetry]
name = "nodetool-lib-data"
version = "0.6.0"
description = "Nodetool nodes for data processing."
readme = "README.md"
authors = ["Matthias Georgi <matti.georgi@gmail.com>"]
packages = [{ include = "nodetool", from = "src" }]
package-mode = true

[tool.poetry.dependencies]
python = "^3.10"
nodetool-core = { git = "https://github.com/nodetool-ai/nodetool-core.git", rev = "main" }

```

3. Create your node classes:

```python
class MyAgent(BaseNode):
    prompt: Field(default="Build me a website for my business.")

    async def process(self, context: ProcessingContext) -> str:
        llm = MyLLM()
        return llm.generate(self.prompt)
```

4. Register your package in the Nodetool registry:
   - Fork the [nodetool-registry](https://github.com/nodetool-ai/nodetool-registry) repository
   - Add your package information to `index.json`
   - Submit a pull request

### Package Requirements

Your package should:

- Follow Python packaging best practices
- Include clear documentation for each node
- Provide example usage
- Include appropriate tests
- Use semantic versioning

### Testing Your Package

Before submitting to the registry:

1. Install your package locally:

```bash
pip install -e .
```

2. Test installation in Nodetool:

```bash
nodetool-package install your-username/your-package --local /path/to/package
```

3. Verify your nodes appear in the Nodetool UI

## Package Registry

The Nodetool package registry is hosted at [nodetool-registry](https://github.com/nodetool-ai/nodetool-registry). It contains:

- Package metadata
- Installation instructions
- Version information
- Node documentation

## Troubleshooting

Common issues and solutions:

1. **Package Installation Fails**

   - Check your internet connection
   - Verify the package name is correct
   - Ensure you have the latest version of Nodetool

2. **Nodes Not Appearing**

   - Verify package installation was successful
   - Check package namespaces are correctly configured
   - Restart Nodetool

3. **Update Issues**
   - Clear package cache
   - Check for conflicting dependencies
   - Verify package compatibility

## Contributing

We welcome contributions to the Nodetool ecosystem! Please see our [Contributing Guidelines](CONTRIBUTING.md) for more information.

## License

This package management system is part of the Nodetool project. See the main [project repository](https://github.com/nodetool-ai/nodetool) for license information.
