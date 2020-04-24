# Mandate

Async fork of [warrant](https://github.com/capless/warrant).

Part of the code was provided by the [warrant](https://github.com/capless/warrant) contributors as part of that software. This code has been duplicated here as allowed by the Apache License 2.0. The warrant code is copyright of the warrant contributors. Any other code is copyright of mandate contributors.

## Import

```python
from mandate import Cognito
```

## Initialise

```python
    cog = Cognito(
        'pool_id',  # user pool id
        'client_id',  # client id
        user_pool_region='eu-west-2', # optional
        username='your-user@email.com',
        client_secret='secret', # optional
        loop=loop # optional
    )
```

## Register

```python
    await cog.register(
        email='your-user@email.com', username='myuser', password='password'
    )
```

`admin_create_user` is also available:
```python
    await cog.admin_create_user('user@email.com')
```

## Confirm Sign up

```python
    await cog.confirm_sign_up('SIGNUP_CODE', 'your-user@email.com')
```

`admin_confirm_sign_up` is also available:

```python
    await cog.admin_confirm_sign_up('user@email.com')
```

## Authenticate

All the below examples can be called with or without `admin_` variants.

Per [the documentation](https://docs.aws.amazon.com/en_us/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow.html#amazon-cognito-user-pools-server-side-authentication-flow), when running a backend server, you can use the `admin_` methods for authentication and user-related activities. For example:

```python
    await cog.admin_authenticate(password)
```

Technically, the non-admin workflow can also be used with, however I have not got this to work with app secrets! Help would be appreciated here.

```python
    await cog.authenticate(password)
```

```
botocore.errorfactory.NotAuthorizedException: An error occurred (NotAuthorizedException) when calling the RespondToAuthChallenge operation: Unable to verify secret hash for client <client id>
```

If you create an app without app secrets, you should also be able to use the non-admin versions without issues.

## Forgot password
```python
    await cog.initiate_forgot_password()
    # Get the code from the email
    await cog.confirm_forgot_password(code, new_password)
```


## Get user attributes
```python
    await cog.admin_authenticate('password')
    user = await cog.get_user()
```

## Change password
```python
    await cog.admin_authenticate(old_password)
    await cog.change_password(old_password, new_password)
```

## Update profile
```python
    await cog.admin_authenticate(password)
    await cog.update_profile(
        {
            'address': 'foo'
        }
    )
```

Or as admin
```python
    await cog.admin_update_profile(
        username='other-user',
        attrs={'gender':'potato'}
    )
```

## Delete user
```python
    await cog.admin_delete_user(username='user.email@example.com')
```

## Logout
```python
    await cog.logout()
```

## Development

Install [poetry](https://github.com/sdispater/poetry), then to install the
dependencies:

```
poetry install
```

## Unit tests
python -m unittest discover tests
