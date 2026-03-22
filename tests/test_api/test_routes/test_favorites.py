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


async def test_authenticated_user_with_no_favorites_returns_empty_list(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
) -> None:
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    articles = ListOfArticlesInResponse(**response.json())
    assert articles.articles == []
    assert articles.articles_count == 0


async def test_authenticated_user_retrieves_favorited_articles(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_article: Article,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    # Favorite the test article via POST endpoint
    await authorized_client.post(
        app.url_path_for("articles:mark-article-favorite", slug=test_article.slug),
    )

    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    articles = ListOfArticlesInResponse(**response.json())
    assert articles.articles_count == 1
    assert articles.articles[0].slug == test_article.slug
    assert articles.articles[0].favorited is True
    assert articles.articles[0].favorites_count == 1


async def test_favorites_pagination_with_limit(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        for i in range(3):
            article = await articles_repo.create_article(
                slug=f"fav-slug-{i}",
                title=f"Fav Article {i}",
                description="tmp",
                body="tmp",
                author=test_user,
            )
            await articles_repo.add_article_into_favorites(
                article=article, user=test_user
            )

    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"limit": 1},
    )
    assert response.status_code == status.HTTP_200_OK

    articles = ListOfArticlesInResponse(**response.json())
    assert articles.articles_count == 1


async def test_favorites_pagination_with_offset(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        for i in range(3):
            article = await articles_repo.create_article(
                slug=f"fav-slug-{i}",
                title=f"Fav Article {i}",
                description="tmp",
                body="tmp",
                author=test_user,
            )
            await articles_repo.add_article_into_favorites(
                article=article, user=test_user
            )

    # Get all favorites first
    full_response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    full_articles = ListOfArticlesInResponse(**full_response.json())
    assert full_articles.articles_count == 3

    # Get with offset=1
    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"offset": 1},
    )
    offset_articles = ListOfArticlesInResponse(**response.json())
    assert offset_articles.articles_count == 2
    assert offset_articles.articles == full_articles.articles[1:]


async def test_favorites_tag_filtering(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)

        article_with_python = await articles_repo.create_article(
            slug="fav-python",
            title="Python Article",
            description="tmp",
            body="tmp",
            author=test_user,
            tags=["python", "coding"],
        )
        article_with_rust = await articles_repo.create_article(
            slug="fav-rust",
            title="Rust Article",
            description="tmp",
            body="tmp",
            author=test_user,
            tags=["rust", "coding"],
        )

        await articles_repo.add_article_into_favorites(
            article=article_with_python, user=test_user
        )
        await articles_repo.add_article_into_favorites(
            article=article_with_rust, user=test_user
        )

    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"tag": "python"},
    )
    assert response.status_code == status.HTTP_200_OK

    articles = ListOfArticlesInResponse(**response.json())
    assert articles.articles_count == 1
    assert articles.articles[0].slug == "fav-python"
    assert "python" in articles.articles[0].tags


async def test_favorites_tag_filter_no_matches_returns_empty(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_article: Article,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    # Favorite an article with known tags
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        await articles_repo.add_article_into_favorites(
            article=test_article, user=test_user
        )

    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
        params={"tag": "nonexistent-tag"},
    )
    assert response.status_code == status.HTTP_200_OK

    articles = ListOfArticlesInResponse(**response.json())
    assert articles.articles == []
    assert articles.articles_count == 0


async def test_unauthenticated_request_returns_403(
    app: FastAPI,
    client: AsyncClient,
    pool: Pool,
) -> None:
    # Use the base `client` fixture which has no auth header
    response = await client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_response_matches_list_of_articles_schema(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_article: Article,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    # Favorite an article and verify the full response schema
    await authorized_client.post(
        app.url_path_for("articles:mark-article-favorite", slug=test_article.slug),
    )

    response = await authorized_client.get(
        app.url_path_for("articles:get-user-favorites"),
    )
    assert response.status_code == status.HTTP_200_OK

    # Validate response can be parsed as ListOfArticlesInResponse without errors
    data = response.json()
    articles_response = ListOfArticlesInResponse(**data)

    assert "articles" in data
    assert "articles_count" in data
    assert isinstance(articles_response.articles, list)
    assert isinstance(articles_response.articles_count, int)
    assert articles_response.articles_count == len(articles_response.articles)

    # Verify article fields are present
    article = articles_response.articles[0]
    assert article.slug == test_article.slug
    assert article.title == test_article.title
    assert article.description == test_article.description
    assert article.body == test_article.body
    assert article.author is not None
    assert article.author.username == test_user.username
