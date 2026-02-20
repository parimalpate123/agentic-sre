"""Mock ServiceNow tools - get ticket by number, list by service/category."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MOCK_DATA_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "servicenow_tickets.json"


def _load_tickets() -> List[Dict[str, Any]]:
    with open(_MOCK_DATA_PATH, "r") as f:
        return json.load(f)


class ServiceNowTools:
    """Mock ServiceNow incident/ticket tools. Uses sample data for payment, rating, policy services."""

    def get_ticket(self, ticket_number: str) -> Dict[str, Any]:
        """
        Get a single ServiceNow incident by number (e.g. INC001).

        Args:
            ticket_number: Incident number (e.g. INC001, INC002).

        Returns:
            Ticket record or error dict if not found.
        """
        tickets = _load_tickets()
        number = (ticket_number or "").strip().upper()
        for t in tickets:
            if t.get("number") == number:
                logger.info(f"ServiceNow get_ticket: found {number}")
                return {"found": True, "ticket": t}
        logger.info(f"ServiceNow get_ticket: not found {number}")
        return {"found": False, "ticket_number": number, "message": f"No ticket found for {number}"}

    def list_tickets(
        self,
        service: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        List ServiceNow incidents, optionally filtered by service or category.

        Args:
            service: Filter by service (e.g. payment-service, rating-service, policy-service).
            category: Filter by category (e.g. payment, rating, policy).
            limit: Max number of tickets to return.

        Returns:
            Dict with 'tickets' list and 'count'.
        """
        tickets = _load_tickets()
        if service:
            tickets = [t for t in tickets if t.get("service") == service]
        if category:
            tickets = [t for t in tickets if t.get("category") == category]
        tickets = tickets[:limit]
        logger.info(f"ServiceNow list_tickets: returning {len(tickets)} tickets")
        return {"tickets": tickets, "count": len(tickets)}
