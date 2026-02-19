"""Mock Jira tools - get issue by key, list by project/service."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MOCK_DATA_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "jira_issues.json"


def _load_issues() -> List[Dict[str, Any]]:
    with open(_MOCK_DATA_PATH, "r") as f:
        return json.load(f)


class JiraTools:
    """Mock Jira issue tools. Uses sample data for payment, rating, policy services."""

    def get_issue(self, issue_key: str) -> Dict[str, Any]:
        """
        Get a single Jira issue by key (e.g. PAY-101, RAT-201).

        Args:
            issue_key: Issue key (e.g. PAY-101, POL-301).

        Returns:
            Issue record or error dict if not found.
        """
        issues = _load_issues()
        key = (issue_key or "").strip().upper()
        for i in issues:
            if i.get("key") == key:
                logger.info(f"Jira get_issue: found {key}")
                return {"found": True, "issue": i}
        logger.info(f"Jira get_issue: not found {key}")
        return {"found": False, "issue_key": key, "message": f"No issue found for {key}"}

    def list_issues(
        self,
        project: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        List Jira issues, optionally filtered by project or service.

        Args:
            project: Filter by project (e.g. PAY, RAT, POL).
            service: Filter by service (e.g. payment-service, rating-service, policy-service).
            limit: Max number of issues to return.

        Returns:
            Dict with 'issues' list and 'count'.
        """
        issues = _load_issues()
        if project:
            issues = [i for i in issues if i.get("project") == project.upper()]
        if service:
            issues = [i for i in issues if i.get("service") == service]
        issues = issues[:limit]
        logger.info(f"Jira list_issues: returning {len(issues)} issues")
        return {"issues": issues, "count": len(issues)}
