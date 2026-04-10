"""Test manual implementation of standard queries to verify approach."""

from __future__ import annotations

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

from sqlmodel_graphql import GraphQLHandler, query


class TestBase(SQLModel):
    pass


class TestUser(TestBase, table=False):
    __test__ = False

    id: int = Field(primary_key=True)
    name: str
    email: str
    age: int | None = None


# Create filter input type manually
class TestUserFilterInput(BaseModel):
    name: str | None = None
    email: str | None = None
    age: int | None = None


class TestUserWithQueries(TestBase, table=False):
    __test__ = False

    id: int = Field(primary_key=True)
    name: str
    email: str
    age: int | None = None

    @query
    async def by_id(cls, id: int, query_meta=None) -> TestUserWithQueries | None:
        """Get user by ID."""
        return TestUserWithQueries(id=id, name=f"User {id}", email=f"user{id}@test.com")

    @query
    async def by_filter(
        cls, filter: TestUserFilterInput, limit: int = 10, query_meta=None
    ) -> list[TestUserWithQueries]:
        """Get users by filter."""
        users = []
        for i in range(1, limit + 1):
            user = TestUserWithQueries(
                id=i,
                name=f"User {i}",
                email=f"user{i}@test.com",
                age=20 + i,
            )
            # Apply filter logic
            if filter.name and filter.name not in user.name:
                continue
            if filter.email and filter.email not in user.email:
                continue
            if filter.age is not None and user.age != filter.age:
                continue
            users.append(user)
        return users


# Test if this works
def test_manual_standard_queries():
    handler = GraphQLHandler(base=TestBase)
    sdl = handler.get_sdl()
    print("\nGenerated SDL:")
    print(sdl)

    assert "input TestUserFilterInput" in sdl
    assert "type Query" in sdl
    assert "testUserWithQueriesById" in sdl
    assert "testUserWithQueriesByFilter" in sdl


async def test_query_execution():
    handler = GraphQLHandler(base=TestBase)

    # Test by_id
    result = await handler.execute("""
        query {
            testUserWithQueriesById(id: 1) {
                id
                name
                email
            }
        }
    """)
    print("\nBy ID query result:")
    print(result)
    assert "data" in result
    assert "testUserWithQueriesById" in result["data"]
    assert result["data"]["testUserWithQueriesById"]["id"] == 1

    # Test by_filter
    result = await handler.execute("""
        query {
            testUserWithQueriesByFilter(filter: {age: 25}, limit: 3) {
                id
                name
                age
            }
        }
    """)
    print("\nBy Filter query result:")
    print(result)
    assert "data" in result
    assert "testUserWithQueriesByFilter" in result["data"]
    assert len(result["data"]["testUserWithQueriesByFilter"]) > 0


if __name__ == "__main__":
    import asyncio

    test_manual_standard_queries()
    print("✅ Manual test passed!")

    asyncio.run(test_query_execution())
    print("✅ Execution tests passed!")
