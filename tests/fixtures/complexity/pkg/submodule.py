async def fetch(flag):
    if flag:
        return 1
    return 0


class Client:
    async def close(self, force):
        if force:
            return 1
        return 0
