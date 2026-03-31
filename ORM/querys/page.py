"""Pagination result container."""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Page:
    """
    Result of a paginated query.

    Attributes:
        data:       The rows for the current page.
        page:       Current page number (1-based).
        page_size:  Maximum rows per page.
        total:      Total number of matching rows across all pages.

    Computed properties:
        total_pages: Total number of pages.
        has_next:    Whether a next page exists.
        has_prev:    Whether a previous page exists.

    Example::

        result = User.paginate(page=2, page_size=20, active=True)

        for row in result.data:
            print(row)

        print(f"Page {result.page} of {result.total_pages}")
        print(f"Total users: {result.total}")
    """

    data: List[Dict[str, Any]] = field(default_factory=list)
    page: int = 1
    page_size: int = 20
    total: int = 0

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return math.ceil(self.total / self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict — useful for JSON responses."""
        return {
            "data": self.data,
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }
