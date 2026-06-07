from billing import total


def test_total_smoke() -> None:
    assert total([4.0, 6.0]) == 10.0
