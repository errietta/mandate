class MockClient:

    def __init__(self, *, mock_register=None, mock_get_group=None):
        self.mock_register = mock_register
        self.mock_get_group = mock_get_group

    async def sign_up(self, *args, **kwargs):
        return await self.mock_register(*args, **kwargs)

    async def get_group(self, *args, **kwargs):
        return await self.mock_get_group(*args, **kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
