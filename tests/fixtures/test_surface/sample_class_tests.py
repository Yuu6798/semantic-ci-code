class TestFixture:
    def test_method(self):
        assert True

    def helper(self):
        assert 1 == 0


class HelperFixture:
    def test_not_collected(self):
        assert 1 == 0
