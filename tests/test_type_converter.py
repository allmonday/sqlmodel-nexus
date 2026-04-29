"""Tests for TypeConverter."""

from enum import Enum

from sqlmodel import SQLModel

from sqlmodel_nexus.type_converter import TypeConverter


class Status(Enum):
    """Test enum."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class UserForConverterTest(SQLModel):
    """Test User entity."""

    id: int | None
    name: str


class PostForConverterTest(SQLModel):
    """Test Post entity."""

    id: int
    title: str


class TestTypeConverterIsOptional:
    """Test cases for TypeConverter.is_optional()."""

    def test_is_optional_with_optional_type(self) -> None:
        """Test that Optional[T] is detected as optional."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_optional(int | None) is True
        assert converter.is_optional(str | None) is True

    def test_is_optional_with_union_syntax(self) -> None:
        """Test that Union[T, None] is detected as optional."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_optional(int | None) is True

    def test_is_optional_with_pipe_syntax(self) -> None:
        """Test that T | None is detected as optional (Python 3.10+)."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_optional(int | None) is True
        assert converter.is_optional(str | None) is True

    def test_is_optional_with_non_optional_type(self) -> None:
        """Test that non-optional types return False."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_optional(int) is False
        assert converter.is_optional(str) is False
        assert converter.is_optional(list[int]) is False

    def test_is_optional_with_none_type(self) -> None:
        """Test that None type is not detected as optional."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_optional(type(None)) is False


class TestTypeConverterUnwrapOptional:
    """Test cases for TypeConverter.unwrap_optional()."""

    def test_unwrap_optional_int(self) -> None:
        """Test unwrapping Optional[int]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_optional(int | None)
        assert result is int

    def test_unwrap_optional_str(self) -> None:
        """Test unwrapping Optional[str]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_optional(str | None)
        assert result is str

    def test_unwrap_optional_with_union(self) -> None:
        """Test unwrapping Union[T, None]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_optional(int | None)
        assert result is int

    def test_unwrap_non_optional_type(self) -> None:
        """Test unwrapping non-optional type returns the type itself."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_optional(int)
        assert result is int


class TestTypeConverterIsListType:
    """Test cases for TypeConverter.is_list_type()."""

    def test_is_list_type_with_list(self) -> None:
        """Test that list[T] is detected as list type."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_list_type(list[int]) is True
        assert converter.is_list_type(list[str]) is True
        assert converter.is_list_type(list[UserForConverterTest]) is True

    def test_is_list_type_with_non_list(self) -> None:
        """Test that non-list types return False."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_list_type(int) is False
        assert converter.is_list_type(str) is False
        assert converter.is_list_type(int | None) is False


class TestTypeConverterGetListInnerType:
    """Test cases for TypeConverter.get_list_inner_type()."""

    def test_get_list_inner_type_simple(self) -> None:
        """Test getting inner type from list[int]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.get_list_inner_type(list[int])
        assert result is int

    def test_get_list_inner_type_entity(self) -> None:
        """Test getting inner type from list[Entity]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.get_list_inner_type(list[UserForConverterTest])
        assert result == UserForConverterTest

    def test_get_list_inner_type_optional(self) -> None:
        """Test getting inner type from list[Optional[int]]."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.get_list_inner_type(list[int | None])
        assert result is int

    def test_get_list_inner_type_empty(self) -> None:
        """Test getting inner type from untyped list."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.get_list_inner_type(list)
        assert result is list


class TestTypeConverterScalarTypeName:
    """Test cases for TypeConverter.get_scalar_type_name()."""

    def test_get_scalar_type_name_int(self) -> None:
        """Test getting scalar name for int."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_scalar_type_name(int) == "Int"

    def test_get_scalar_type_name_str(self) -> None:
        """Test getting scalar name for str."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_scalar_type_name(str) == "String"

    def test_get_scalar_type_name_bool(self) -> None:
        """Test getting scalar name for bool."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_scalar_type_name(bool) == "Boolean"

    def test_get_scalar_type_name_float(self) -> None:
        """Test getting scalar name for float."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_scalar_type_name(float) == "Float"

    def test_get_scalar_type_name_non_scalar(self) -> None:
        """Test getting scalar name for non-scalar type returns None."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_scalar_type_name(UserForConverterTest) is None
        assert converter.get_scalar_type_name(Status) is None
        assert converter.get_scalar_type_name(dict) is None


class TestTypeConverterIsEnumType:
    """Test cases for TypeConverter.is_enum_type()."""

    def test_is_enum_type_with_enum(self) -> None:
        """Test that enum types are detected."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_enum_type(Status) is True

    def test_is_enum_type_with_non_enum(self) -> None:
        """Test that non-enum types return False."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_enum_type(int) is False
        assert converter.is_enum_type(str) is False
        assert converter.is_enum_type(UserForConverterTest) is False


class TestTypeConverterIsEntityType:
    """Test cases for TypeConverter.is_entity_type()."""

    def test_is_entity_type_with_entity(self) -> None:
        """Test that entity types are detected."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_entity_type(UserForConverterTest) is True

    def test_is_entity_type_with_string_forward_ref(self) -> None:
        """Test that string forward references are detected."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_entity_type("UserForConverterTest") is True

    def test_is_entity_type_with_non_entity(self) -> None:
        """Test that non-entity types return False."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_entity_type(int) is False
        assert converter.is_entity_type(str) is False
        assert converter.is_entity_type(PostForConverterTest) is False

    def test_is_entity_type_with_unknown_string(self) -> None:
        """Test that unknown string returns False."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_entity_type("UnknownEntity") is False


class TestTypeConverterGetEntityName:
    """Test cases for TypeConverter.get_entity_name()."""

    def test_get_entity_name_from_type(self) -> None:
        """Test getting entity name from type."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_entity_name(UserForConverterTest) == "UserForConverterTest"

    def test_get_entity_name_from_string(self) -> None:
        """Test getting entity name from string."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_entity_name("UserForConverterTest") == "UserForConverterTest"

    def test_get_entity_name_from_non_entity(self) -> None:
        """Test getting entity name from non-entity returns None."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.get_entity_name(int) is None
        assert converter.get_entity_name("UnknownEntity") is None


class TestTypeConverterIsRelationship:
    """Test cases for TypeConverter.is_relationship()."""

    def test_is_relationship_single_entity(self) -> None:
        """Test detecting single entity relationship."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_relationship(UserForConverterTest) is True

    def test_is_relationship_optional_entity(self) -> None:
        """Test detecting optional entity relationship."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_relationship(UserForConverterTest | None) is True

    def test_is_relationship_list_entity(self) -> None:
        """Test detecting list of entities relationship."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_relationship(list[UserForConverterTest]) is True

    def test_is_relationship_list_optional_entity(self) -> None:
        """Test detecting list of optional entities relationship."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_relationship(list[UserForConverterTest | None]) is True

    def test_is_relationship_non_entity(self) -> None:
        """Test non-entity type is not a relationship."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.is_relationship(int) is False
        assert converter.is_relationship(list[int]) is False
        assert converter.is_relationship(str | None) is False


class TestTypeConverterUnwrapToBaseType:
    """Test cases for TypeConverter.unwrap_to_base_type()."""

    def test_unwrap_to_base_type_optional(self) -> None:
        """Test unwrapping Optional[T] to T."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_to_base_type(int | None)
        assert result is int

    def test_unwrap_to_base_type_list(self) -> None:
        """Test unwrapping list[T] to T."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_to_base_type(list[int])
        assert result is int

    def test_unwrap_to_base_type_list_optional(self) -> None:
        """Test unwrapping list[Optional[T]] to T."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_to_base_type(list[int | None])
        assert result is int

    def test_unwrap_to_base_type_entity(self) -> None:
        """Test unwrapping entity type returns itself."""
        converter = TypeConverter({"UserForConverterTest"})
        result = converter.unwrap_to_base_type(UserForConverterTest)
        assert result == UserForConverterTest

    def test_unwrap_to_base_type_scalar(self) -> None:
        """Test unwrapping scalar type returns itself."""
        converter = TypeConverter({"UserForConverterTest"})
        assert converter.unwrap_to_base_type(int) is int
        assert converter.unwrap_to_base_type(str) is str
