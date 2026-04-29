"""Tests for DataLoader factory functions — M2O, O2M, M2M batch loaders."""

from __future__ import annotations

import pytest

from sqlmodel_nexus.loader.factories import (
    _build_loader_identity,
    _normalize_identifier,
    create_many_to_one_loader,
    create_one_to_many_loader,
)
from tests.conftest import get_test_session_factory


class TestNormalizeIdentifier:
    def test_simple_name(self):
        assert _normalize_identifier("User") == "User"

    def test_special_characters(self):
        assert _normalize_identifier("my-table") == "my_table"

    def test_multiple_underscores(self):
        assert _normalize_identifier("a__b") == "a_b"

    def test_empty_string(self):
        assert _normalize_identifier("") == "anonymous"


class TestBuildLoaderIdentity:
    def test_identity_format(self):
        identity = _build_loader_identity(int, "posts", "O2M")
        assert "int" in identity
        assert "posts" in identity
        assert "O2M" in identity


class TestManyToOneLoader:
    @pytest.mark.usefixtures("test_db")
    async def test_batch_load_returns_correct_mapping(self):
        """M2O loader should return target entities keyed by remote column."""

        from tests.conftest import FixtureTask, FixtureUser

        session_factory = get_test_session_factory()

        # FixtureTask.owner_id -> FixtureUser.id (M2O)
        LoaderCls = create_many_to_one_loader(
            source_kls=FixtureTask,
            rel_name="owner",
            target_kls=FixtureUser,
            target_remote_col_name="id",
            session_factory=session_factory,
        )

        loader = LoaderCls()

        # Load users by their IDs
        result = await loader.load_many([1, 2])

        assert len(result) == 2
        assert result[0] is not None
        assert result[0].name in ("Alice", "Bob")

    @pytest.mark.usefixtures("test_db")
    async def test_missing_key_returns_none(self):
        """M2O loader should return None for non-existent keys."""

        from tests.conftest import FixtureTask, FixtureUser

        session_factory = get_test_session_factory()

        LoaderCls = create_many_to_one_loader(
            source_kls=FixtureTask,
            rel_name="owner",
            target_kls=FixtureUser,
            target_remote_col_name="id",
            session_factory=session_factory,
        )

        loader = LoaderCls()
        result = await loader.load_many([999])

        assert result == [None]


class TestOneToManyLoader:
    @pytest.mark.usefixtures("test_db")
    async def test_batch_load_returns_grouped_lists(self):
        """O2M loader should return lists of target entities grouped by FK."""

        from tests.conftest import FixtureSprint, FixtureTask

        session_factory = get_test_session_factory()

        # FixtureSprint.id -> list[FixtureTask] via sprint_id (O2M)
        LoaderCls = create_one_to_many_loader(
            source_kls=FixtureSprint,
            rel_name="tasks",
            target_kls=FixtureTask,
            target_fk_col_name="sprint_id",
            session_factory=session_factory,
        )

        loader = LoaderCls()

        # Load tasks for sprints 1 and 2
        result = await loader.load_many([1, 2])

        assert len(result) == 2
        # Each sprint has 2 tasks
        assert len(result[0]) == 2
        assert len(result[1]) == 2

    @pytest.mark.usefixtures("test_db")
    async def test_empty_group_returns_empty_list(self):
        """O2M loader should return empty list for FK with no matches."""

        from tests.conftest import FixtureSprint, FixtureTask

        session_factory = get_test_session_factory()

        LoaderCls = create_one_to_many_loader(
            source_kls=FixtureSprint,
            rel_name="tasks",
            target_kls=FixtureTask,
            target_fk_col_name="sprint_id",
            session_factory=session_factory,
        )

        loader = LoaderCls()
        result = await loader.load_many([999])

        assert result == [[]]


class TestLoaderClassNaming:
    def test_m2o_class_name(self):
        """M2O loader class should have a descriptive name."""

        from tests.conftest import FixtureTask, FixtureUser

        LoaderCls = create_many_to_one_loader(
            source_kls=FixtureTask,
            rel_name="owner",
            target_kls=FixtureUser,
            target_remote_col_name="id",
            session_factory=lambda: None,
        )

        assert "SG_" in LoaderCls.__name__
        assert "M2O" in LoaderCls.__name__

    def test_o2m_class_name(self):
        """O2M loader class should have a descriptive name."""

        from tests.conftest import FixtureSprint, FixtureTask

        LoaderCls = create_one_to_many_loader(
            source_kls=FixtureSprint,
            rel_name="tasks",
            target_kls=FixtureTask,
            target_fk_col_name="sprint_id",
            session_factory=lambda: None,
        )

        assert "SG_" in LoaderCls.__name__
        assert "O2M" in LoaderCls.__name__
