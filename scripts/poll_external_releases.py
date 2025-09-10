#!/usr/bin/env python3
"""
Poll external repositories for new releases and update the registry.

This script checks for new releases in external (third-party) repositories
and updates the package index accordingly.
"""
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

from registry_utils import GitHubAPIClient, RegistryManager, has_wheel_assets, setup_logging

setup_logging(logging.INFO)
logger = logging.getLogger(__name__)

def update_package_info(registry: Dict, repo_id: str, release: Dict) -> bool:
    """Update package information with latest release data"""
    updated = False
    
    for package in registry.get("packages", []):
        if package.get("repo_id") == repo_id:
            # Update version information if available
            tag_name = release.get("tag_name", "")
            current_version = package.get("version", "")
            
            if tag_name and tag_name != current_version:
                logger.info(f"Updating {repo_id} version from {current_version} to {tag_name}")
                package["version"] = tag_name
                updated = True
            
            # Update release date
            published_at = release.get("published_at", "")
            if published_at:
                package["updated_at"] = published_at
                updated = True
            
            break
    
    return updated

def create_package_entry(repo_id: str, release: Dict) -> Dict:
    """Create a new package entry for a discovered repository"""
    repo_name = repo_id.split("/")[1]
    
    # Try to extract meaningful name by removing nodetool- prefix if present
    display_name = repo_name
    if repo_name.startswith("nodetool-"):
        display_name = repo_name[9:].replace("-", " ").title()
    
    return {
        "name": display_name,
        "description": f"External package: {repo_name}",
        "repo_id": repo_id,
        "version": release.get("tag_name", ""),
        "updated_at": release.get("published_at", ""),
        "namespaces": [f"nodetool.nodes.{repo_name.replace('-', '_')}"],
        "external": True
    }

def discover_new_packages(github_client: GitHubAPIClient) -> List[str]:
    """
    Discover new nodetool packages by searching GitHub.
    This is a basic implementation - could be enhanced with more sophisticated discovery.
    """
    discovered = []
    
    try:
        # Search for repositories with "nodetool-" prefix that aren't from nodetool-ai
        repos = github_client.search_repositories("nodetool- in:name -user:nodetool-ai")
        
        for repo in repos:
            repo_name = repo["name"]
            repo_full_name = repo["full_name"]
            
            # Check if it looks like a nodetool package
            if repo_name.startswith("nodetool-") and not repo["private"]:
                # Check if it has releases with wheels
                latest_release = github_client.get_latest_release(repo_full_name)
                if latest_release and has_wheel_assets(latest_release):
                    logger.info(f"Discovered new nodetool package: {repo_full_name}")
                    discovered.append(repo_full_name)
        
    except Exception as e:
        logger.error(f"Error during package discovery: {e}")
    
    return discovered

def main():
    """Main polling function"""
    logger.info("Starting external package polling...")
    
    # Initialize managers and clients
    registry_manager = RegistryManager()
    github_client = GitHubAPIClient()
    
    # Load current registry
    registry = registry_manager.load_registry()
    original_registry = json.dumps(registry, sort_keys=True)
    
    # Get existing external repos
    external_repos = registry_manager.get_external_repos()
    logger.info(f"Found {len(external_repos)} external repositories in registry")
    
    # Check for updates to existing external repos
    for repo_id in external_repos:
        logger.info(f"Checking {repo_id} for updates...")
        latest_release = github_client.get_latest_release(repo_id)
        
        if latest_release and has_wheel_assets(latest_release):
            update_package_info(registry, repo_id, latest_release)
        elif latest_release:
            logger.warning(f"{repo_id} has releases but no wheel files")
    
    # Discover new packages (optional - can be disabled if too noisy)
    try_discovery = True  # Set to False to disable auto-discovery
    
    if try_discovery:
        logger.info("Discovering new nodetool packages...")
        discovered_repos = discover_new_packages(github_client)
        
        for repo_id in discovered_repos:
            if repo_id not in external_repos:
                latest_release = github_client.get_latest_release(repo_id)
                if latest_release and has_wheel_assets(latest_release):
                    new_package = create_package_entry(repo_id, latest_release)
                    registry["packages"].append(new_package)
                    logger.info(f"Added new external package: {repo_id}")
    
    # Check if anything changed
    updated_registry = json.dumps(registry, sort_keys=True)
    if original_registry != updated_registry:
        logger.info("Registry updated, saving changes...")
        registry_manager.save_registry(registry)
    else:
        logger.info("No changes detected")

if __name__ == "__main__":
    main()