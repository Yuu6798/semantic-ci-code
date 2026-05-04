from math import sqrt

VALUE = 1


def public_api(flag: bool) -> float:
    print("effect")
    if flag:
        return sqrt(4)
    return 0.0


def test_public_api():
    assert public_api(False) == 0.0
