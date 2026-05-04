import os

VALUE = 1


def public_api(flag: bool) -> int:
    if flag:
        print(os.getcwd())
        return VALUE
    return 0
