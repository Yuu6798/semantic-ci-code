def fixture_func():
    return 1


class FixtureClass:
    def method(self, enabled):
        if enabled:
            return 1
        return 0
