import asynctest

from mandate import Cognito


class testUser(asynctest.TestCase):
    async def test_get_user(self):
        cog = Cognito(
            'user_pool_id',  # user pool id
            'client_id',
            user_pool_region='eu-west-2',
            username='test@test.com',
            id_token='id token',
            access_token='access token',
        )

        cog.add_base_attributes(email='test@test.com')

        async with cog.get_client() as client:
            with asynctest.patch.object(
                client, 'get_user',
                new=asynctest.CoroutineMock()
            ):
                user = await cog.get_user()
                self.assertEqual(user.username, 'test@test.com')
                self.assertEqual(user.id_token, 'id token')
                self.assertEqual(user.access_token, 'access token')
