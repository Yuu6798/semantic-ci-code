import pytest


@pytest.mark.parametrize("x", [1, 2, 3])
def test_param(x):
    assert x


@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20, 30])
def test_stacked(x, y):
    assert x + y
