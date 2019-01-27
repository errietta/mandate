import asynctest

from mandate import Cognito


class testApi(asynctest.TestCase):
    async def test_register(self):
        cog = Cognito(
            'user_pool_id',  # user pool id
            'client_id',
            user_pool_region='eu-west-2',
            username='test@test.com'
        )

        async with cog.get_client() as client:
            with asynctest.patch.object(client, 'sign_up',
                                        new=asynctest.CoroutineMock()):
                await cog.register(
                    username='test@test.com',
                    password='password',
                    email='test@test.com'
                )

                client.sign_up.assert_awaited()
                client.sign_up.assert_called_with(
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
