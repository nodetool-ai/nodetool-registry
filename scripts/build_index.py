#!/usr/bin/env python3
"""
NodeTool Registry Package Index Builder
Builds a PEP 503 compatible package index from GitHub releases
"""

import os
import json
import requests
import hashlib
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from registry_utils import (
    GitHubAPIClient,
    RegistryManager,
    has_wheel_assets,
    parse_version,
    setup_logging,
)


class NodeToolRegistryBuilder:
    """Build package index for NodeTool packages"""

    def __init__(self, github_token: Optional[str] = None):
        self.github_client = GitHubAPIClient(github_token)
        self.registry_manager = RegistryManager()

        # Load packages from registry instead of hardcoding
        self._load_packages()

    def _load_packages(self):
        """Load packages from registry index.json"""
        try:
            packages = self.registry_manager.get_all_packages()
            self.packages = {}
            self.package_filters = {}

            for package in packages:
                repo_id = package.get("repo_id", "")
                if repo_id:
                    # Extract package name from repo_id
                    package_name = repo_id.split("/")[1]
                    self.packages[package_name] = repo_id
                    # Store wheel filter if present
                    wheel_filter = package.get("wheel_filter")
                    if wheel_filter:
                        self.package_filters[package_name] = wheel_filter

            print(f"📋 Loaded {len(self.packages)} packages from registry")

        except Exception as e:
            print(f"❌ Failed to load packages from registry: {e}")
            # Fallback to empty dict
            self.packages = {}
            self.package_filters = {}

    def get_wheel_metadata(self, asset_url: str, asset_name: str) -> Dict:
        """Get wheel metadata and discover PEP 658 metadata availability.

        Returns a dict containing:
          - url, filename, size, upload_time
          - metadata_available: bool
          - metadata_sha256: Optional[str] (hex digest without "sha256=")
        """
        try:
            # Get wheel content length without downloading
            response = requests.head(asset_url, headers=self.github_client.headers)
            size = int(response.headers.get("content-length", 0))

            metadata_available = False
            metadata_sha256 = None

            # Check for PEP 658 sidecar metadata at <wheel_url>.metadata
            try:
                metadata_url = f"{asset_url}.metadata"
                meta_head = requests.head(
                    metadata_url, headers=self.github_client.headers
                )
                if meta_head.status_code == 200:
                    meta_get = requests.get(
                        metadata_url, headers=self.github_client.headers
                    )
                    if meta_get.ok and meta_get.content:
                        metadata_sha256 = hashlib.sha256(meta_get.content).hexdigest()
                        metadata_available = True
            except Exception:
                # If we can't retrieve sidecar metadata, simply don't advertise it
                metadata_available = False

            return {
                "url": asset_url,
                "filename": asset_name,
                "size": size,
                "upload_time": response.headers.get("last-modified", ""),
                "metadata_available": metadata_available,
                "metadata_sha256": metadata_sha256,
            }
        except Exception as e:
            print(f"⚠️  Warning: Could not get metadata for {asset_name}: {e}")
            return {
                "url": asset_url,
                "filename": asset_name,
                "size": 0,
                "upload_time": "",
                "metadata_available": False,
                "metadata_sha256": None,
            }

    def generate_package_page(
        self, package_name: str, repo: str, output_dir: Path, wheel_filter: Optional[str] = None
    ):
        """Generate PEP 503 package page"""
        releases = self.github_client.get_releases(repo)

        # Filter and sort releases
        valid_releases = []
        for release in releases:
            if release.get("draft") or release.get("prerelease"):
                continue

            v = parse_version(release["tag_name"])
            if v:
                valid_releases.append((v, release))

        # Sort by version (newest first)
        valid_releases.sort(key=lambda x: x[0], reverse=True)

        # Collect wheel assets
        wheels = []
        for v, release in valid_releases:
            for asset in release.get("assets", []):
                if asset["name"].endswith(".whl"):
                    # Apply wheel filter if specified
                    if wheel_filter and wheel_filter not in asset["name"]:
                        continue
                    metadata = self.get_wheel_metadata(
                        asset["browser_download_url"], asset["name"]
                    )
                    metadata["version"] = str(v)
                    metadata["release_date"] = release["published_at"]
                    wheels.append(metadata)

        # Generate HTML
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"  <title>Links for {package_name}</title>",
            '  <meta name="pypi:repository-version" content="1.0">',
            '  <meta name="api-version" content="2">',
            "</head>",
            "<body>",
            f"  <h1>Links for {package_name}</h1>",
        ]

        # Add wheel links
        for wheel in wheels:
            attrs = [f'href="{wheel["url"]}"']

            if wheel.get("size"):
                attrs.append(f'data-size="{wheel["size"]}"')

            # Add Python version requirement
            if "py3" in wheel["filename"]:
                attrs.append('data-requires-python="&gt;=3.11"')

            # Include PEP 658 attribute only if we actually found sidecar metadata
            if wheel.get("metadata_available") and wheel.get("metadata_sha256"):
                attrs.append(
                    f'data-dist-info-metadata="sha256={wheel["metadata_sha256"]}"'
                )

            link_html = f'    <a {" ".join(attrs)}>{wheel["filename"]}</a><br>'
            html_lines.append(link_html)

        html_lines.extend(["</body>", "</html>"])

        # Write package page
        package_dir = output_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        with open(package_dir / "index.html", "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))

        print(f"✅ Generated {package_name} index ({len(wheels)} wheels)")
        return len(wheels)

    def generate_root_index(self, output_dir: Path, package_counts: Dict[str, int]):
        """Generate root index page"""
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "  <title>NodeTool Package Index</title>",
            '  <meta name="pypi:repository-version" content="1.0">',
            '  <meta name="api-version" content="2">',
            "</head>",
            "<body>",
            "  <h1>NodeTool Package Index</h1>",
            "  <p>Simple package index for NodeTool packages hosted on GitHub</p>",
            "  <hr>",
        ]

        # Add package links with counts
        total_wheels = 0
        for package_name in sorted(self.packages.keys()):
            count = package_counts.get(package_name, 0)
            total_wheels += count
            html_lines.append(
                f'  <a href="{package_name}/">{package_name}</a> ({count} wheels)<br>'
            )

        html_lines.extend(
            [
                "  <hr>",
                f"  <p><small>Total: {len(self.packages)} packages, {total_wheels} wheels</small></p>",
                f'  <p><small>Last updated: {time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}</small></p>',
                "</body>",
                "</html>",
            ]
        )

        with open(output_dir / "index.html", "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))

        print(
            f"✅ Generated root index ({len(self.packages)} packages, {total_wheels} wheels)"
        )

    def build_index(
        self, output_dir: str, force_rebuild: bool = False, package_filter: str = None
    ):
        """Build complete package index"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Filter packages if specified
        packages_to_build = self.packages
        if package_filter:
            packages_to_build = {
                k: v for k, v in self.packages.items() if k == package_filter
            }
            if not packages_to_build:
                print(f"❌ Package '{package_filter}' not found in registry")
                return

        print(f"🏗️  Building NodeTool package index in {output_path}")
        print(f"📊 Processing {len(packages_to_build)} packages")
        if package_filter:
            print(f"🔍 Filter: {package_filter}")

        package_counts = {}

        # Load existing counts for incremental builds
        if not force_rebuild and package_filter:
            try:
                with open(output_path.parent / "packages.json", "r") as f:
                    existing_data = json.load(f)
                    for pkg in existing_data.get("packages", []):
                        if pkg["name"] not in packages_to_build:
                            package_counts[pkg["name"]] = pkg.get("wheel_count", 0)
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        # Generate package pages
        for package_name, repo in packages_to_build.items():
            wheel_filter = self.package_filters.get(package_name)
            filter_info = f" [filter: {wheel_filter}]" if wheel_filter else ""
            print(f"\n📦 Processing {package_name} ({repo}){filter_info}")
            try:
                count = self.generate_package_page(package_name, repo, output_path, wheel_filter)
                package_counts[package_name] = count
            except Exception as e:
                print(f"❌ Failed to process {package_name}: {e}")
                package_counts[package_name] = 0

        # Generate root index (always, to include all packages)
        print(f"\n📋 Generating root index")
        # Fill in missing packages with existing data
        for package_name in self.packages:
            if package_name not in package_counts:
                package_counts[package_name] = 0

        self.generate_root_index(output_path, package_counts)

        print(f"\n🎉 Package index built successfully!")
        print(f"📍 Location: {output_path.absolute()}")
        print(
            f"🌐 Usage: pip install --index-url file://{output_path.absolute()}/ nodetool-base"
        )


def main():
    parser = argparse.ArgumentParser(description="Build NodeTool package index")
    parser.add_argument(
        "--output-dir", default="dist", help="Output directory for index"
    )
    parser.add_argument("--github-token", help="GitHub token for API access")
    parser.add_argument(
        "--force-rebuild", action="store_true", help="Force rebuild entire index"
    )
    parser.add_argument(
        "--package-filter", help="Only build index for specific package"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    import logging

    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(log_level)

    github_token = args.github_token or os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("⚠️  Warning: No GitHub token provided, API rate limits may apply")

    builder = NodeToolRegistryBuilder(github_token)
    builder.build_index(args.output_dir, args.force_rebuild, args.package_filter)


if __name__ == "__main__":
    main()
