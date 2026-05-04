from gamma import gamma


def beta() -> int:
    print("beta")
    return gamma()


def test_beta():
    assert beta() == 1
