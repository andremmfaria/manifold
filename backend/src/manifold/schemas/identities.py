from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from manifold.schemas.common import SchemaModel


class MergeRequest(SchemaModel):
    """Request body for POST /identities/merge."""

    account_ids: list[str]

    @field_validator("account_ids")
    @classmethod
    def at_least_two(cls, v: list[str]) -> list[str]:
        if len(v) < 2:
            raise ValueError("account_ids must contain at least 2 entries")
        return v


class MergeResponse(SchemaModel):
    """Response for POST /identities/merge."""

    identity_id: str
    account_ids: list[str]


class UnmergeRequest(SchemaModel):
    """Request body for POST /identities/unmerge."""

    account_id: str


class UnmergeResponse(SchemaModel):
    """Response for POST /identities/unmerge."""

    caveat: str


class SuggestionItem(SchemaModel):
    """One merge suggestion pair."""

    account_a_id: str
    account_b_id: str
    score: float
    reasons: list[str]


class SuggestionsResponse(SchemaModel):
    """Response for GET /identities/suggestions."""

    suggestions: list[SuggestionItem]
    aggregated: bool = False


class DismissSuggestionRequest(SchemaModel):
    """Request body for POST /identities/suggestions/dismiss."""

    account_a_id: str
    account_b_id: str
    write_do_not_merge: bool = True


class DismissSuggestionResponse(SchemaModel):
    """Response for POST /identities/suggestions/dismiss."""

    dismissed: bool


class IdentityMemberResponse(SchemaModel):
    """One account member of an identity."""

    id: str
    user_id: str
    provider_account_id: str
    account_type: str
    currency: str
    display_name: str | None
    identity_id: str | None
    created_at: datetime


class IdentityResponse(SchemaModel):
    """Response for GET /identities/{id}."""

    id: str
    user_id: str
    origin: str
    master_account_id: str | None
    merged_into: str | None
    merged_at: datetime | None
    created_at: datetime
    updated_at: datetime
    members: list[IdentityMemberResponse]
    aggregated: bool = False


__all__ = [
    "DismissSuggestionRequest",
    "DismissSuggestionResponse",
    "IdentityMemberResponse",
    "IdentityResponse",
    "MergeRequest",
    "MergeResponse",
    "SuggestionItem",
    "SuggestionsResponse",
    "UnmergeRequest",
    "UnmergeResponse",
]
