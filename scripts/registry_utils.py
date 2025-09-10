#!/usr/bin/env python3
"""
Shared utilities for NodeTool registry operations.
Consolidates common functionality across build and polling scripts.
"""

import json
import time
import requests
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from packaging import version

logger = logging.getLogger(__name__)

class GitHubAPIClient:
    """Centralized GitHub API client with rate limiting"""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        } if token else {'Accept': 'application/vnd.github.v3+json'}
        
        self.api_calls = 0
        self.start_time = time.time()
    
    def rate_limit_check(self):
        """Check and handle GitHub API rate limits"""
        self.api_calls += 1
        if self.api_calls % 10 == 0:  # Check every 10 calls
            elapsed = time.time() - self.start_time
            if elapsed < 60 and self.api_calls > 50:  # Approaching rate limit
                sleep_time = 60 - elapsed + 1
                logger.info(f"Rate limiting: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self.start_time = time.time()
                self.api_calls = 0
    
    def get_releases(self, repo_id: str) -> List[Dict]:
        """Get releases for a repository with rate limiting"""
        self.rate_limit_check()
        url = f'https://api.github.com/repos/{repo_id}/releases'
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            
            # Check rate limit headers
            remaining = response.headers.get('X-RateLimit-Remaining')
            if remaining and int(remaining) < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                sleep_time = max(reset_time - time.time() + 1, 0)
                if sleep_time > 0:
                    logger.info(f"Rate limit protection: sleeping {sleep_time:.1f}s")
                    time.sleep(sleep_time)
            
            if response.status_code == 404:
                logger.info(f"No releases found for {repo_id}")
                return []
            elif response.status_code != 200:
                logger.warning(f"Failed to fetch releases for {repo_id}: {response.status_code}")
                return []
            
            releases = response.json()
            logger.info(f"Found {len(releases)} releases for {repo_id}")
            return releases
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching releases for {repo_id}: {e}")
            return []
    
    def get_latest_release(self, repo_id: str) -> Optional[Dict]:
        """Get the latest release for a repository"""
        try:
            url = f"https://api.github.com/repos/{repo_id}/releases/latest"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 404:
                logger.info(f"No releases found for {repo_id}")
                return None
            elif response.status_code != 200:
                logger.warning(f"Failed to fetch latest release for {repo_id}: {response.status_code}")
                return None
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching latest release for {repo_id}: {e}")
            return None
    
    def search_repositories(self, query: str, per_page: int = 50) -> List[Dict]:
        """Search repositories on GitHub"""
        try:
            search_url = "https://api.github.com/search/repositories"
            params = {
                "q": query,
                "sort": "updated",
                "per_page": per_page
            }
            
            response = requests.get(search_url, params=params, headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])
            else:
                logger.warning(f"Search failed with status {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during repository search: {e}")
            return []

class RegistryManager:
    """Manages the registry index.json file"""
    
    def __init__(self, registry_path: str = "index.json"):
        self.registry_path = Path(registry_path)
    
    def load_registry(self) -> Dict:
        """Load the registry index.json"""
        if not self.registry_path.exists():
            logger.error(f"Registry file not found: {self.registry_path}")
            raise FileNotFoundError(f"Registry file not found: {self.registry_path}")
        
        with open(self.registry_path, 'r') as f:
            return json.load(f)
    
    def save_registry(self, registry: Dict):
        """Save the registry index.json"""
        with open(self.registry_path, 'w') as f:
            json.dump(registry, f, indent=2, sort_keys=True)
            f.write('\n')  # Add trailing newline
    
    def get_all_packages(self) -> List[Dict]:
        """Get all packages from registry"""
        registry = self.load_registry()
        return registry.get("packages", [])
    
    def get_packages_by_filter(self, external_only: bool = False, nodetool_ai_only: bool = False) -> List[Dict]:
        """Get packages filtered by type"""
        packages = self.get_all_packages()
        
        if external_only:
            return [pkg for pkg in packages if not pkg.get("repo_id", "").startswith("nodetool-ai/")]
        elif nodetool_ai_only:
            return [pkg for pkg in packages if pkg.get("repo_id", "").startswith("nodetool-ai/")]
        else:
            return packages
    
    def get_external_repos(self) -> Set[str]:
        """Get set of external repository IDs"""
        external_repos = set()
        for package in self.get_all_packages():
            repo_id = package.get("repo_id", "")
            if repo_id and not repo_id.startswith("nodetool-ai/"):
                external_repos.add(repo_id)
        return external_repos

def has_wheel_assets(release: Dict) -> bool:
    """Check if a release has wheel (.whl) files"""
    assets = release.get("assets", [])
    return any(asset["name"].endswith(".whl") for asset in assets)

def parse_version(tag_name: str) -> Optional[version.Version]:
    """Parse version from git tag"""
    try:
        # Remove 'v' prefix and any suffixes
        version_str = tag_name.lstrip('v').split('-')[0]
        return version.parse(version_str)
    except Exception:
        return None

def extract_package_name_from_repo(repo_id: str) -> str:
    """Extract package name from repository ID"""
    return repo_id.split("/")[1]

def setup_logging(level: int = logging.INFO):
    """Set up logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(levelname)s:%(name)s:%(message)s'
    )