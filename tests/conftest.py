import copy

import pytest

from taxnetlab.datasets import Dataset
from taxnetlab.synthetic import build_0_1_fixture, generate
from taxnetlab.workspace import Workspace


@pytest.fixture
def fixture01() -> Dataset:
    return build_0_1_fixture()


@pytest.fixture
def world() -> Dataset:
    return generate(seed=17)


@pytest.fixture
def workspace(tmp_path) -> Workspace:
    return Workspace(tmp_path / "ws").ensure()


def tables_of(dataset: Dataset) -> dict:
    return copy.deepcopy(dataset.tables)


def rebuild(dataset: Dataset, mutate) -> tuple:
    tables = tables_of(dataset)
    mutate(tables)
    return Dataset.from_rows("mutated", tables)


def codes(report, level=None) -> set:
    return {i.code for i in report.issues if level is None or i.level == level}
