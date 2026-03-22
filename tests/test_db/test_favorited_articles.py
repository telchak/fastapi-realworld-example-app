import pytest
from asyncpg.pool import Pool
from fastapi import FastAPI
from httpx import AsyncClient
from starlette import status

from app.db.repositories.articles import ArticlesRepository
from app.db.repositories.users import UsersRepository
from app.models.domain.articles import Article
from app.models.domain.users import UserInDB
from app.models.schemas.articles import ListOfArticlesInResponse

pytestmark = pytest.mark.asyncio


async def test_get_favorited_articles_returns_empty_when_no_favorites(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    """User with no favorites should get an empty list."""
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)
        # Create some articles that are NOT favorited
        for i in range(3):
            await articles_repo.create_article(
                slug=f"slug-{i}",
                title=f"Title {i}",
                description="tmp",
                body="tmp",
                author=test_user,
            )

        result = await articles_repo.get_favorited_articles_for_user(user=test_user)

    assert result == []


async def test_get_favorited_articles_returns_favorited_articles(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    """User with favorites should receive exactly those articles."""
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)

        favorited_article = await articles_repo.create_article(
            slug="fav-slug",
            title="Fav Article",
            description="tmp",
            body="tmp",
            author=test_user,
        )
        unfavorited_article = await articles_repo.create_article(
            slug="not-fav-slug",
            title="Not Fav Article",
            description="tmp",
            body="tmp",
            author=test_user,
        )

        await articles_repo.add_article_into_favorites(
            article=favorited_article, user=test_user
        )

        result = await articles_repo.get_favorited_articles_for_user(user=test_user)

    assert len(result) == 1
    assert result[0].slug == favorited_article.slug
    assert all(a.slug != unfavorited_article.slug for a in result)


async def test_get_favorited_articles_pagination_limits_results(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    """Pagination: limit and offset control the result window."""
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)

        created = []
        for i in range(5):
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
            created.append(article)

        all_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user, limit=20, offset=0
        )
        limited_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user, limit=2, offset=0
        )
        offset_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user, limit=20, offset=3
        )

    assert len(all_results) == 5
    assert len(limited_results) == 2
    assert len(offset_results) == 2
    assert all_results[3:] == offset_results


async def test_get_favorited_articles_tag_filter_narrows_results(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    """Tag filter should only return favorited articles that have the given tag."""
    async with pool.acquire() as connection:
        articles_repo = ArticlesRepository(connection)

        article_with_tag = await articles_repo.create_article(
            slug="tagged-fav",
            title="Tagged Favorite",
            description="tmp",
            body="tmp",
            author=test_user,
            tags=["python"],
        )
        article_without_tag = await articles_repo.create_article(
            slug="untagged-fav",
            title="Untagged Favorite",
            description="tmp",
            body="tmp",
            author=test_user,
            tags=["javascript"],
        )

        await articles_repo.add_article_into_favorites(
            article=article_with_tag, user=test_user
        )
        await articles_repo.add_article_into_favorites(
            article=article_without_tag, user=test_user
        )

        tagged_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user, tag="python"
        )
        all_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user
        )
        no_match_results = await articles_repo.get_favorited_articles_for_user(
            user=test_user, tag="nonexistent-tag"
        )

    assert len(all_results) == 2
    assert len(tagged_results) == 1
    assert tagged_results[0].slug == article_with_tag.slug
    assert len(no_match_results) == 0


async def test_get_favorited_articles_only_returns_requesting_users_favorites(
    app: FastAPI,
    authorized_client: AsyncClient,
    test_user: UserInDB,
    pool: Pool,
) -> None:
    """Favorites from other users must not appear in the result."""
    async with pool.acquire() as connection:
        users_repo = UsersRepository(connection)
        articles_repo = ArticlesRepository(connection)

        other_user = await users_repo.create_user(
            username="other_user",
            email="other@email.com",
            password="password",
        )

        article = await articles_repo.create_article(
            slug="shared-article",
            title="Shared Article",
            description="tmp",
            body="tmp",
            author=test_user,
        )

        # Only other_user favorites the article
        await articles_repo.add_article_into_favorites(
            article=article, user=other_user
        )

        result = await articles_repo.get_favorited_articles_for_user(user=test_user)

    assert result == []
