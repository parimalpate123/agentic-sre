"""
GitHub Client for creating issues and managing PRs
"""

import os
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations"""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client

        Args:
            token: GitHub personal access token (or use GITHUB_TOKEN env var)
        """
        self.token = token or os.environ.get('GITHUB_TOKEN')
        if not self.token:
            logger.warning("No GitHub token provided. GitHub operations will fail.")
        
        self.base_url = 'https://api.github.com'
        self.headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        } if self.token else {
            'Accept': 'application/vnd.github.v3+json'
        }

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        labels: list = None
    ) -> str:
        """
        Create GitHub issue

        Args:
            repo: Repository path (org/repo)
            title: Issue title
            body: Issue body (markdown)
            labels: List of label names

        Returns:
            Issue URL (HTML)

        Raises:
            requests.RequestException: If API call fails
        """
        if not self.token:
            raise ValueError("GitHub token required for issue creation")

        url = f"{self.base_url}/repos/{repo}/issues"
        
        payload = {
            'title': title,
            'body': body,
            'labels': labels or []
        }
        
        logger.info(f"Creating GitHub issue in {repo}: {title}")
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            issue_data = response.json()
            issue_url = issue_data['html_url']
            issue_number = issue_data['number']
            
            logger.info(f"Created GitHub issue #{issue_number}: {issue_url}")
            return issue_url
            
        except requests.RequestException as e:
            logger.error(f"Failed to create GitHub issue: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise

    def _extract_issue_number(self, issue_url: str) -> Optional[int]:
        """
        Extract issue number from URL

        Args:
            issue_url: GitHub issue HTML URL

        Returns:
            Issue number or None
        """
        try:
            # URL format: https://github.com/org/repo/issues/123
            parts = issue_url.rstrip('/').split('/')
            return int(parts[-1])
        except (ValueError, IndexError):
            return None
