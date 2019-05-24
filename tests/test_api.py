import asynctest

from tests.MockClient import MockClient
from mandate import Cognito


class testApi(asynctest.TestCase):
    async def test_api(self):
        mock_register = asynctest.CoroutineMock(
            side_effect=lambda *args, **kwargs: {
                'ResponseMetadata': {'HTTPStatusCode': 200}
            }
        )

        mock_client = MockClient(mock_register=mock_register)

        cog = Cognito(
            'user_pool_id',  # user pool id
            'client_id',
            user_pool_region='eu-west-2',
            username='test@test.com',
            client_callback=lambda: mock_client
        )

        await cog.register(
            username='test@test.com',
            password='password',
            email='test@test.com'
        )

        mock_register.assert_awaited()
        mock_register.assert_called_with(
            ClientId='client_id',
            Username='test@test.com',
            Password='password',
            UserAttributes=[
                {
                    'Name': 'email',
                    'Value': 'test@test.com',
                }
            ]
        )
