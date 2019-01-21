import asynctest

from mandate import Cognito


class testGroup(asynctest.TestCase):
    async def test_get_group(self):
        cog = Cognito(
            'user_pool_id',  # user pool id
            'client_id',
            user_pool_region='eu-west-2',
            username='test@test.com',
            id_token='id token',
            access_token='access token',
        )

        async def _fake_get_group(GroupName=None, UserPoolId=None):
            return {
                'Group': {
                    'GroupName': GroupName,
                    'Description': 'Desc',
                    'CreationDate': '1970-01-01',
                    'LastModifiedDate': '1970-01-02',
                    'RoleArn': 'Arn::eatcake',
                    'Precedence': 'testing'
                }
            }

        async with cog.get_client() as client:
            with asynctest.patch.object(
                client, 'get_group',
                new=_fake_get_group
            ):
                group = await cog.get_group('Test')

                self.assertEqual(group.group_name, 'Test')
                self.assertEqual(group.description, 'Desc')
                self.assertEqual(group.creation_date, '1970-01-01')
                self.assertEqual(group.last_modified_date, '1970-01-02')
                self.assertEqual(group.role_arn, 'Arn::eatcake')
                self.assertEqual(group.precedence, 'testing')
