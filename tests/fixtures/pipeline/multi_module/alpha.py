import beta

ALPHA_VALUE = 1


def alpha(flag: bool = True) -> int:
    if flag:
        return beta.beta()
    return 0
