"""Source parsers. Each turns raw text into normalized observations; no DB access, no guessing."""

from app.services.parsers.base import ParsedRecord, ParseIssue, ParseResult

__all__ = ["ParsedRecord", "ParseIssue", "ParseResult"]
