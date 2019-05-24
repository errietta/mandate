import asynctest

from mandate import Cognito
from tests.MockClient import MockClient


class testGroup(asynctest.TestCase):

    async def test_get_group(self):
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

        mock_client = MockClient(mock_get_group=_fake_get_group)

        cog = Cognito(
            'user_pool_id',  # user pool id
            'client_id',
            user_pool_region='eu-west-2',
            username='test@test.com',
            id_token='id token',
            access_token='access token',
            client_callback=lambda : mock_client
        )

        group = await cog.get_group('Test')

        self.assertEqual(group.group_name, 'Test')
        self.assertEqual(group.description, 'Desc')
        self.assertEqual(group.creation_date, '1970-01-01')
        self.assertEqual(group.last_modified_date, '1970-01-02')
        self.assertEqual(group.role_arn, 'Arn::eatcake')
        self.assertEqual(group.precedence, 'testing')
