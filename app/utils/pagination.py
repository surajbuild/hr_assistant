"""
app/utils/pagination.py
-----------------------
List pagination convention (D-035): list endpoints keep returning a plain JSON array and accept
`limit` / `offset` query parameters; the total number of matching rows is sent in the
`X-Total-Count` response header (exposed for browsers via Access-Control-Expose-Headers).
"""

from fastapi import Response

TOTAL_COUNT_HEADER = "X-Total-Count"


def set_total_count(response: Response, total: int) -> None:
    response.headers[TOTAL_COUNT_HEADER] = str(total)
    response.headers["Access-Control-Expose-Headers"] = TOTAL_COUNT_HEADER
