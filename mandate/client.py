import aioboto3
import datetime
import aiohttp
import attr

from envs import env
from jose import jwt, JWTError

from .aws_srp import AWSSRP
from .exceptions import TokenVerificationException
from .userobj import UserObj
from .groupobj import GroupObj
from .utils import dict_to_cognito


@attr.s
class Cognito(object):
    user_class = UserObj
    group_class = GroupObj

    user_pool_id = attr.ib()
    client_id = attr.ib()
    user_pool_region = attr.ib()

    username = attr.ib(default=None)
    id_token = attr.ib(default=None)
    access_token = attr.ib(default=None)
    refresh_token = attr.ib(default=None)
    client_secret = attr.ib(default=None)

    access_key = attr.ib(default=None)
    secret_key = attr.ib(default=None)
    client_callback = attr.ib(default=None)

    @user_pool_region.default
    def generate_region_from_pool(self):
        return self.user_pool_id.split('_')[0]

    def get_session(self):
        return aiohttp.ClientSession()

    def get_client(self):
        if self.client_callback:
            return self.client_callback()

        boto3_client_kwargs = {}
        if self.access_key and self.secret_key:
            boto3_client_kwargs['aws_access_key_id'] = self.access_key
            boto3_client_kwargs['aws_secret_access_key'] = self.secret_key
        if self.user_pool_region:
            boto3_client_kwargs['region_name'] = self.user_pool_region

        return aioboto3.client(
            'cognito-idp', **boto3_client_kwargs)

    async def get_keys(self):
        try:
            return self.pool_jwk
        except AttributeError:
            # Check for the dictionary in environment variables.
            pool_jwk_env = env('COGNITO_JWKS', {}, var_type='dict')
            if len(pool_jwk_env.keys()) > 0:
                self.pool_jwk = pool_jwk_env
                return self.pool_jwk

            # If it is not there use the aiohttp library to get it
            async with self.get_session() as session:
                resp = await session.get(
                    'https://cognito-idp.{}.amazonaws.com/{}/.well-known/jwks.json'.format( # noqa
                        self.user_pool_region, self.user_pool_id
                    ))
                self.pool_jwk = await resp.json()
                return self.pool_jwk

    async def get_key(self, kid):
        keys = (await self.get_keys()).get('keys')
        key = list(filter(lambda x: x.get('kid') == kid, keys))
        return key[0]

    async def verify_token(self, token, id_name, token_use):
        kid = jwt.get_unverified_header(token).get('kid')
        unverified_claims = jwt.get_unverified_claims(token)
        token_use_verified = unverified_claims.get('token_use') == token_use
        if not token_use_verified:
            raise TokenVerificationException(
                'Your {} token use could not be verified.')
        hmac_key = await self.get_key(kid)
        try:
            verified = jwt.decode(token, hmac_key, algorithms=['RS256'],
                                  audience=unverified_claims.get('aud'),
                                  issuer=unverified_claims.get('iss'))
        except JWTError:
            raise TokenVerificationException(
                'Your {} token could not be verified.')
        setattr(self, id_name, token)
        return verified

    def get_user_obj(self, username=None, attribute_list=None, metadata=None,
                     attr_map=None):
        """
        Returns the specified
        :param username: Username of the user
        :param attribute_list: List of tuples that represent the user's
            attributes as returned by the admin_get_user or get_user boto3
            methods
        :param metadata: Metadata about the user
        :param attr_map: Dictionary that maps the Cognito attribute names to
        what we'd like to display to the users
        :return:
        """
        return self.user_class(username=username,
                               attribute_list=attribute_list,
                               cognito_obj=self,
                               metadata=metadata, attr_map=attr_map)

    def get_group_obj(self, group_data):
        """
        Instantiates the self.group_class
        :param group_data: a dictionary with information about a group
        :return: an instance of the self.group_class
        """
        return self.group_class(group_data=group_data, cognito_obj=self)

    def switch_session(self, session):
        """
        Primarily used for unit testing so we can take advantage of the
        placebo library (https://githhub.com/garnaat/placebo)
        :param session: boto3 session
        :return:
        """
        self.client = session.client('cognito-idp')

    async def check_token(self, renew=True):
        """
        Checks the exp attribute of the access_token and either refreshes
        the tokens by calling the renew_access_tokens method or does nothing
        :param renew: bool indicating whether to refresh on expiration
        :return: bool indicating whether access_token has expired
        """
        if not self.access_token:
            raise AttributeError('Access Token Required to Check Token')
        now = datetime.datetime.now()
        dec_access_token = jwt.get_unverified_claims(self.access_token)

        if now > datetime.datetime.fromtimestamp(dec_access_token['exp']):
            expired = True
            if renew:
                await self.renew_access_token()
        else:
            expired = False
        return expired

    def add_base_attributes(self, **kwargs):
        self.base_attributes = kwargs

    async def register(self, *, username, password, email, attrs={}):
        """
        Register the user.

        :param username: User Pool username
        :param password: User Pool password
        :param email: User Email
        :param attrs: Other base attributes for AWS such as:
        address, birthdate, email, family_name (last name), gender,
        given_name (first name), locale, middle_name, name, nickname,
        phone_number, picture, preferred_username, profile, zoneinfo,
        updated at, website

        :return response: Response from Cognito

        Example response::
        {
            'UserConfirmed': True|False,
            'CodeDeliveryDetails': {
                'Destination': 'string', # This value will be obfuscated
                'DeliveryMedium': 'SMS'|'EMAIL',
                'AttributeName': 'string'
            }
        }
        """

        attributes = attrs
        attributes['email'] = email
        cognito_attributes = dict_to_cognito(attributes)

        params = {
            'ClientId': self.client_id,
            'Username': username,
            'Password': password,
            'UserAttributes': cognito_attributes
        }
        self._add_secret_hash(params, 'SecretHash')

        async with self.get_client() as client:
            response = await client.sign_up(**params)
            attributes.update(username=username, password=password)
            self._set_attributes(response, attributes)
            response.pop('ResponseMetadata')
            return response

    async def admin_confirm_sign_up(self, username=None):
        """
        Confirms user registration as an admin without using a confirmation
        code. Works on any user.
        :param username: User's username
        :return:
        """
        if not username:
            username = self.username
        async with self.get_client() as client:
            await client.admin_confirm_sign_up(
                UserPoolId=self.user_pool_id,
                Username=username,
            )

    async def confirm_sign_up(self, confirmation_code, username=None):
        """
        Using the confirmation code that is either sent via email or text
        message.
        :param confirmation_code: Confirmation code sent via text or email
        :param username: User's username
        :return:
        """
        if not username:
            username = self.username
        params = {'ClientId': self.client_id,
                  'Username': username,
                  'ConfirmationCode': confirmation_code}
        self._add_secret_hash(params, 'SecretHash')
        async with self.get_client() as client:
            await client.confirm_sign_up(**params)

    async def admin_authenticate(self, password):
        """
        Authenticate the user using admin super privileges
        :param password: User's password
        :return:
        """
        auth_params = {
            'USERNAME': self.username,
            'PASSWORD': password
        }
        self._add_secret_hash(auth_params, 'SECRET_HASH')

        async with self.get_client() as client:
            tokens = await client.admin_initiate_auth(
                UserPoolId=self.user_pool_id,
                ClientId=self.client_id,
                # AuthFlow='USER_SRP_AUTH'|'REFRESH_TOKEN_AUTH'|'REFRESH_TOKEN'|'CUSTOM_AUTH'|'ADMIN_NO_SRP_AUTH',
                AuthFlow='ADMIN_NO_SRP_AUTH',
                AuthParameters=auth_params,
            )

            await self.verify_token(
                tokens['AuthenticationResult']['IdToken'],
                'id_token',
                'id')
            self.refresh_token = tokens['AuthenticationResult']['RefreshToken']
            await self.verify_token(
                tokens['AuthenticationResult']['AccessToken'],
                'access_token',
                'access')
            self.token_type = tokens['AuthenticationResult']['TokenType']

    async def authenticate(self, password):
        """
        Authenticate the user using the SRP protocol
        :param password: The user's passsword
        :return:
        """

        aws = AWSSRP(username=self.username, password=password,
                     pool_id=self.user_pool_id,
                     client_id=self.client_id, client=self.get_client(),
                     client_secret=self.client_secret)
        tokens = await aws.authenticate_user()
        await self.verify_token(tokens['AuthenticationResult']['IdToken'],
                                'id_token', 'id')
        self.refresh_token = tokens['AuthenticationResult']['RefreshToken']
        await self.verify_token(tokens['AuthenticationResult']['AccessToken'],
                                'access_token', 'access')
        self.token_type = tokens['AuthenticationResult']['TokenType']

    async def new_password_challenge(self, password, new_password):
        """
        Respond to the new password challenge using the SRP protocol
        :param password: The user's current passsword
        :param password: The user's new passsword
        """
        aws = AWSSRP(username=self.username, password=password,
                     pool_id=self.user_pool_id,
                     client_id=self.client_id, client=self.get_client(),
                     client_secret=self.client_secret)
        tokens = await aws.set_new_password_challenge(new_password)
        self.id_token = tokens['AuthenticationResult']['IdToken']
        self.refresh_token = tokens['AuthenticationResult']['RefreshToken']
        self.access_token = tokens['AuthenticationResult']['AccessToken']
        self.token_type = tokens['AuthenticationResult']['TokenType']

    async def logout(self):
        """
        Logs the user out of all clients and removes the expires_in,
        expires_datetime, id_token, refresh_token, access_token, and token_type
        attributes
        :return:
        """
        async with self.get_client() as client:
            await client.global_sign_out(
                AccessToken=self.access_token
            )

            self.id_token = None
            self.refresh_token = None
            self.access_token = None
            self.token_type = None

    async def admin_update_profile(
            self,
            username=None,
            attrs={},
            attr_map=None
    ):
        if not username:
            username = self.username

        user_attrs = dict_to_cognito(attrs, attr_map)
        async with self.get_client() as client:
            await client.admin_update_user_attributes(
                UserPoolId=self.user_pool_id,
                Username=username,
                UserAttributes=user_attrs
            )

    async def update_profile(self, attrs, attr_map=None):
        """
        Updates User attributes
        :param attrs: Dictionary of attribute name, values
        :param attr_map: Dictionary map from Cognito attributes to attribute
        names we would like to show to our users
        """
        user_attrs = dict_to_cognito(attrs, attr_map)
        async with self.get_client() as client:
            await client.update_user_attributes(
                UserAttributes=user_attrs,
                AccessToken=self.access_token
            )

    async def get_user(self, attr_map=None):
        """
        Returns a UserObj (or whatever the self.user_class is) by using the
        user's access token.
        :param attr_map: Dictionary map from Cognito attributes to attribute
        names we would like to show to our users
        :return:
        """
        async with self.get_client() as client:
            user = await client.get_user(
                AccessToken=self.access_token
            )

            user_metadata = {
                'username': user.get('Username'),
                'id_token': self.id_token,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
            }
            return self.get_user_obj(username=self.username,
                                     attribute_list=user.get('UserAttributes'),
                                     metadata=user_metadata, attr_map=attr_map)

    async def get_users(self, attr_map=None):
        """
        Returns all users for a user pool. Returns instances of the
        self.user_class.
        :param attr_map:
        :return:
        """
        kwargs = {"UserPoolId": self.user_pool_id}

        async with self.get_client() as client:
            response = await client.list_users(**kwargs)
            return [self.get_user_obj(user.get('Username'),
                                      attribute_list=user.get('Attributes'),
                                      metadata={
                                          'username': user.get('Username')},
                                      attr_map=attr_map)
                    for user in response.get('Users')]

    async def admin_get_user(self, attr_map=None):
        """
        Get the user's details using admin super privileges.
        :param attr_map: Dictionary map from Cognito attributes to attribute
        names we would like to show to our users
        :return: UserObj object
        """
        async with self.get_client() as client:
            user = await client.admin_get_user(
                UserPoolId=self.user_pool_id,
                Username=self.username)
            user_metadata = {
                'enabled': user.get('Enabled'),
                'user_status': user.get('UserStatus'),
                'username': user.get('Username'),
                'id_token': self.id_token,
                'access_token': self.access_token,
                'refresh_token': self.refresh_token
            }
            return self.get_user_obj(username=self.username,
                                     attribute_list=user.get('UserAttributes'),
                                     metadata=user_metadata, attr_map=attr_map)

    async def admin_create_user(self, username, temporary_password=None,
                                attr_map=None, **kwargs):
        """
        Create a user using admin super privileges.
        :param username: User Pool username
        :param temporary_password: The temporary password to give the user.
        Leave blank to make Cognito generate a temporary password for the user.
        :param attr_map: Attribute map to Cognito's attributes
        :param kwargs: Additional User Pool attributes
        :return response: Response from Cognito
        """
        async with self.get_client() as client:
            if temporary_password:
                response = await client.admin_create_user(
                    UserPoolId=self.user_pool_id,
                    Username=username,
                    UserAttributes=dict_to_cognito(kwargs, attr_map),
                    TemporaryPassword=temporary_password,
                )
            else:
                # don't @ me, i'm not the one who designed that API
                response = await client.admin_create_user(
                    UserPoolId=self.user_pool_id,
                    Username=username,
                    UserAttributes=dict_to_cognito(kwargs, attr_map)
                )
            kwargs.update(username=username)
            self._set_attributes(response, kwargs)

            response.pop('ResponseMetadata')
            return response

    async def send_verification(self, attribute='email'):
        """
        Sends the user an attribute verification code for the specified
        attribute name.
        :param attribute: Attribute to confirm
        """
        await self.check_token()
        async with self.get_client() as client:
            await client.get_user_attribute_verification_code(
                AccessToken=self.access_token,
                AttributeName=attribute
            )

    async def validate_verification(self, confirmation_code,
                                    attribute='email'):
        """
        Verifies the specified user attributes in the user pool.
        :param confirmation_code: Code sent to user upon intiating verification
        :param attribute: Attribute to confirm
        """
        await self.check_token()
        async with self.get_client() as client:
            await client.verify_user_attribute(
                AccessToken=self.access_token,
                AttributeName=attribute,
                Code=confirmation_code
            )

    async def renew_access_token(self):
        """
        Sets a new access token on the User using the refresh token.
        """
        auth_params = {'REFRESH_TOKEN': self.refresh_token}
        self._add_secret_hash(auth_params, 'SECRET_HASH')

        async with self.get_client() as client:
            refresh_response = await client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN',
                AuthParameters=auth_params,
            )

            self._set_attributes(
                refresh_response,
                {
                    'access_token':
                    refresh_response['AuthenticationResult']['AccessToken'],
                    'id_token':
                    refresh_response['AuthenticationResult']['IdToken'],
                    'token_type':
                    refresh_response['AuthenticationResult']['TokenType']
                }
            )

    async def initiate_forgot_password(self):
        """
        Sends a verification code to the user to use to change their password.
        """
        params = {
            'ClientId': self.client_id,
            'Username': self.username
        }
        self._add_secret_hash(params, 'SecretHash')
        async with self.get_client() as client:
            await client.forgot_password(**params)

    async def delete_user(self):
        async with self.get_client() as client:
            await client.delete_user(
                AccessToken=self.access_token
            )

    async def admin_delete_user(self, username):
        async with self.get_client() as client:
            await client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=username
            )

    async def confirm_forgot_password(self, confirmation_code, password):
        """
        Allows a user to enter a code provided when they reset their password
        to update their password.
        :param confirmation_code: Confirmation code sent by a user's request
        to retrieve a forgotten password
        :param password: New password
        """
        params = {'ClientId': self.client_id,
                  'Username': self.username,
                  'ConfirmationCode': confirmation_code,
                  'Password': password
                  }
        self._add_secret_hash(params, 'SecretHash')
        async with self.get_client() as client:
            response = await client.confirm_forgot_password(**params)
            self._set_attributes(response, {'password': password})

    async def change_password(self, previous_password, proposed_password):
        """
        Change the User password
        """
        async with self.get_client() as client:
            await self.check_token()
            response = await client.change_password(
                PreviousPassword=previous_password,
                ProposedPassword=proposed_password,
                AccessToken=self.access_token
            )
        self._set_attributes(response, {'password': proposed_password})

    def _add_secret_hash(self, parameters, key):
        """
        Helper function that computes SecretHash and adds it
        to a parameters dictionary at a specified key
        """
        if self.client_secret is not None:
            secret_hash = AWSSRP.get_secret_hash(self.username, self.client_id,
                                                 self.client_secret)
            parameters[key] = secret_hash

    def _set_attributes(self, response, attribute_dict):
        """
        Set user attributes based on response code
        :param response: HTTP response from Cognito
        :attribute dict: Dictionary of attribute name and values
        """
        status_code = response.get(
            'HTTPStatusCode',
            response['ResponseMetadata']['HTTPStatusCode']
        )
        if status_code == 200:
            for k, v in attribute_dict.items():
                setattr(self, k, v)

    async def get_group(self, group_name):
        """
        Get a group by a name
        :param group_name: name of a group
        :return: instance of the self.group_class
        """
        async with self.get_client() as client:
            response = await client.get_group(GroupName=group_name,
                                              UserPoolId=self.user_pool_id)
            return self.get_group_obj(response.get('Group'))

    async def get_groups(self):
        """
        Returns all groups for a user pool. Returns instances of the
        self.group_class.
        :return: list of instances
        """
        async with self.get_client() as client:
            response = await client.list_groups(UserPoolId=self.user_pool_id)
            return [self.get_group_obj(group_data)
                    for group_data in response.get('Groups')]
