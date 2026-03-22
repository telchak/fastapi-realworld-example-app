import pytest
from pydantic import ValidationError

from app.models.schemas.articles import (
    DEFAULT_ARTICLES_LIMIT,
    DEFAULT_ARTICLES_OFFSET,
    FavoriteFeedFilters,
)


def test_favorite_feed_filters_has_correct_defaults() -> None:
    filters = FavoriteFeedFilters()
    assert filters.tag is None
    assert filters.limit == DEFAULT_ARTICLES_LIMIT
    assert filters.limit == 20
    assert filters.offset == DEFAULT_ARTICLES_OFFSET
    assert filters.offset == 0


def test_favorite_feed_filters_accepts_valid_tag() -> None:
    filters = FavoriteFeedFilters(tag="python")
    assert filters.tag == "python"


def test_favorite_feed_filters_accepts_custom_limit_and_offset() -> None:
    filters = FavoriteFeedFilters(limit=10, offset=5)
    assert filters.limit == 10
    assert filters.offset == 5


def test_favorite_feed_filters_rejects_negative_limit() -> None:
    with pytest.raises(ValidationError):
        FavoriteFeedFilters(limit=-1)


def test_favorite_feed_filters_rejects_zero_limit() -> None:
    # limit has ge=1, so 0 is also invalid
    with pytest.raises(ValidationError):
        FavoriteFeedFilters(limit=0)


def test_favorite_feed_filters_rejects_negative_offset() -> None:
    with pytest.raises(ValidationError):
        FavoriteFeedFilters(offset=-1)


def test_favorite_feed_filters_accepts_zero_offset() -> None:
    # offset has ge=0, so 0 is valid
    filters = FavoriteFeedFilters(offset=0)
    assert filters.offset == 0


def test_favorite_feed_filters_accepts_large_limit() -> None:
    filters = FavoriteFeedFilters(limit=100)
    assert filters.limit == 100


def test_favorite_feed_filters_all_fields_set() -> None:
    filters = FavoriteFeedFilters(tag="testing", limit=5, offset=10)
    assert filters.tag == "testing"
    assert filters.limit == 5
    assert filters.offset == 10
