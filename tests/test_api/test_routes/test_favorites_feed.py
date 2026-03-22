import pytest
from asyncpg.pool import Pool
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from app.db.repositories.articles import ArticlesRepository
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB
from app.models.schemas.articles import ListOfArticlesInResponse

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def second_article(test_user: UserInDB, pool: Pool) -> Article:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        return await articles_repo.create_article(
            slug="second-article",
            title="Second Article",
            description="Another article for tests",
            body="Body " * 50,
            author=test_user,
            tags=["python", "async"],
        )


@pytest.fixture
async def third_article(test_user: UserInDB, pool: Pool) -> Article:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        return await articles_repo.create_article(
            slug="third-article",
            title="Third Article",
            description="Yet another article for tests",
            body="Content " * 50,
            author=test_user,
            tags=["django", "web"],
        )


@pytest.fixture
async def favorited_article(
    test_user: UserInDB,
    test_article: Article,
    pool: Pool,
) -> Article:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        await articles_repo.add_article_into_favorites(
            article=test_article, user=test_user
        )
    return test_article


@pytest.fixture
async def multiple_favorited_articles(
    test_user: UserInDB,
    test_article: Article,
    second_article: Article,
    third_article: Article,
    pool: Pool,
) -> list:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        for article in [test_article, second_article, third_article]:
            await articles_repo.add_article_into_favorites(
                article=article, user=test_user
            )
    return [test_article, second_article, third_article]


# ────────────────────────────────────────────────────────────────────────
# 1. Authentication tests
# ────────────────────────────────────────────────────────────────────────


async def test_unauthenticated_user_cannot_access_favorites_feed(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    response = await client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_authenticated_user_can_access_favorites_feed(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK


# ────────────────────────────────────────────────────────────────────────
# 2. Empty results
# ────────────────────────────────────────────────────────────────────────


async def test_favorites_feed_returns_empty_when_no_favorites(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    assert result.articles == []
    assert result.articles_count == 0


# ────────────────────────────────────────────────────────────────────────
# 3. Favorites retrieval
# ────────────────────────────────────────────────────────────────────────


async def test_favorites_feed_returns_favorited_articles(
    app: FastAPI,
    authorized_client: AsyncClient,
    favorited_article: Article,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    assert result.articles_count >= 1

    slugs = [article.slug for article in result.articles]
    assert favorited_article.slug in slugs


async def test_favorites_feed_response_matches_article_list_schema(
    app: FastAPI,
    authorized_client: AsyncClient,
    favorited_article: Article,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert "articles" in data
    assert "articles_count" in data
    assert isinstance(data["articles"], list)
    assert isinstance(data["articles_count"], int)

    # Validate full schema parsing
    result = ListOfArticlesInResponse(**data)
    assert result.articles_count == len(result.articles)


# ────────────────────────────────────────────────────────────────────────
# 4. Pagination
# ────────────────────────────────────────────────────────────────────────


async def test_favorites_feed_respects_limit_parameter(
    app: FastAPI,
    authorized_client: AsyncClient,
    multiple_favorited_articles: list,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"limit": 1},
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    assert len(result.articles) == 1
    assert result.articles_count == 1


async def test_favorites_feed_respects_offset_parameter(
    app: FastAPI,
    authorized_client: AsyncClient,
    multiple_favorited_articles: list,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"offset": 1},
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    # We favorited 3 articles; with offset=1, expect 2 remaining
    assert result.articles_count == len(multiple_favorited_articles) - 1


async def test_favorites_feed_uses_default_pagination(
    app: FastAPI,
    authorized_client: AsyncClient,
    multiple_favorited_articles: list,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    # Default limit=20, offset=0 — all 3 favorited articles should be returned
    assert result.articles_count == len(multiple_favorited_articles)


# ────────────────────────────────────────────────────────────────────────
# 5. Tag filtering
# ────────────────────────────────────────────────────────────────────────


async def test_favorites_feed_filters_by_tag(
    app: FastAPI,
    authorized_client: AsyncClient,
    multiple_favorited_articles: list,
) -> None:
    # test_article has tags ["tests", "testing", "pytest"]
    # second_article has tags ["python", "async"]
    # third_article has tags ["django", "web"]
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"tag": "python"},
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    assert result.articles_count >= 1

    # All returned articles should have the "python" tag
    for article in result.articles:
        assert "python" in article.tags


async def test_favorites_feed_tag_filter_returns_empty_for_nonexistent_tag(
    app: FastAPI,
    authorized_client: AsyncClient,
    multiple_favorited_articles: list,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"tag": "nonexistent-tag-xyz"},
    )
    assert response.status_code == status.HTTP_200_OK

    result = ListOfArticlesInResponse(**response.json())
    assert result.articles == []
    assert result.articles_count == 0
