"""Tests for type_utils module."""


from sqlmodel import Field, SQLModel

from sqlmodel_graphql.utils.type_utils import (
    get_field_type,
    get_return_entity_type,
)


class EntityForUtilsTest(SQLModel):
    """Test entity for type_utils tests."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    optional_field: str | None = None


class AnotherEntityForUtilsTest(SQLModel):
    """Another test entity."""

    id: int | None
    value: int


class TestGetFieldType:
    """Test cases for get_field_type()."""

    def test_get_field_type_from_model_fields(self) -> None:
        """Test getting field type from model_fields."""
        result = get_field_type(EntityForUtilsTest, "name")
        assert result is str

    def test_get_field_type_optional(self) -> None:
        """Test getting optional field type."""
        result = get_field_type(EntityForUtilsTest, "optional_field")
        # Should return the annotation
        assert result is not None

    def test_get_field_type_non_existent(self) -> None:
        """Test getting type of non-existent field."""
        from typing import Any

        result = get_field_type(EntityForUtilsTest, "non_existent")
        assert result == Any

    def test_get_field_type_primary_key(self) -> None:
        """Test getting type of primary key field."""
        result = get_field_type(EntityForUtilsTest, "id")
        # id is Optional[int] or int | None
        assert result is not None


class TestGetReturnEntityType:
    """Test cases for get_return_entity_type()."""

    def test_get_return_entity_type_single_entity(self) -> None:
        """Test getting return type from method returning single entity."""
        # Use direct type reference (not forward reference string)
        # because get_type_hints can't resolve forward refs in local classes

        class TestEntity(SQLModel):
            id: int | None

        # Define method outside the class to avoid forward reference issues
        def get_by_id(cls, id: int) -> TestEntity:  # type: ignore
            return TestEntity(id=id)

        # Attach to class as classmethod
        TestEntity.get_by_id = classmethod(get_by_id)  # type: ignore

        result = get_return_entity_type(TestEntity.get_by_id, [TestEntity])
        assert result == TestEntity

    def test_get_return_entity_type_list_entity(self) -> None:
        """Test getting return type from method returning list of entities."""

        class TestEntityList(SQLModel):
            id: int | None

        def get_all(cls) -> list[TestEntityList]:  # type: ignore
            return []

        TestEntityList.get_all = classmethod(get_all)  # type: ignore

        result = get_return_entity_type(TestEntityList.get_all, [TestEntityList])
        assert result == TestEntityList

    def test_get_return_entity_type_optional_entity(self) -> None:
        """Test getting return type from method returning optional entity."""

        class TestEntityOptional(SQLModel):
            id: int | None

        def find(cls, id: int) -> TestEntityOptional | None:  # type: ignore
            return None

        TestEntityOptional.find = classmethod(find)  # type: ignore

        result = get_return_entity_type(
            TestEntityOptional.find, [TestEntityOptional]
        )
        assert result == TestEntityOptional

    def test_get_return_entity_type_non_entity(self) -> None:
        """Test getting return type from method returning non-entity."""

        class TestEntityNonEntity(SQLModel):
            id: int | None

            @classmethod
            def count(cls) -> int:
                return 0

        result = get_return_entity_type(
            TestEntityNonEntity.count, [TestEntityNonEntity]
        )
        assert result is None

    def test_get_return_entity_type_no_return_annotation(self) -> None:
        """Test getting return type from method without return annotation."""

        class TestEntityNoReturn(SQLModel):
            id: int | None

            @classmethod
            def no_return(cls):
                pass

        result = get_return_entity_type(
            TestEntityNoReturn.no_return, [TestEntityNoReturn]
        )
        assert result is None

    def test_get_return_entity_type_different_entity(self) -> None:
        """Test getting return type when returning different entity."""

        class EntityA(SQLModel):
            id: int | None

        class EntityB(SQLModel):
            id: int | None

        def get_b(cls) -> EntityB:  # type: ignore
            return EntityB(id=1)

        EntityA.get_b = classmethod(get_b)  # type: ignore

        result = get_return_entity_type(EntityA.get_b, [EntityA, EntityB])
        assert result == EntityB

    def test_get_return_entity_type_list_optional(self) -> None:
        """Test getting return type from list[Optional[Entity]]."""

        class TestEntityListOpt(SQLModel):
            id: int | None

        def search(cls) -> list[TestEntityListOpt | None]:  # type: ignore
            return []

        TestEntityListOpt.search = classmethod(search)  # type: ignore

        result = get_return_entity_type(
            TestEntityListOpt.search, [TestEntityListOpt]
        )
        assert result == TestEntityListOpt
