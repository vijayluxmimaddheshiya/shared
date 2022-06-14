from shared.typings.oauth_token_types import OauthConsumerToken


def encode_token(token: OauthConsumerToken) -> str:
    # Different git providers encode different information on the oauth_token column.
    # Check https://github.com/codecov/shared/blob/a1e7ad5a5beea9a697c79e1d6eb41802523c26d8/shared/encryption/selector.py#L36
    string_to_save = token["access_token"]
    if token.get("secret"):
        string_to_save += f":{token['secret']}"
    if token.get("refresh_token"):
        string_to_save += (
            ": " if token.get("secret") is None else ""
        ) + f":{token['refresh_token']}"
    return string_to_save


def decode_token(_oauth: str) -> OauthConsumerToken:
    """
    This function decrypts a oauth_token into its different parts.
    At the moment it does different things depending on the provider.

    - github
        Only stores the "key" as the entire token
    - bitbucket
        Encodes the token as f"{key}:{secret}"
    - gitlab
        Encodes the token as f"{key}: :{refresh_token}"
        (notice the space where {secret} should go to avoid having '::', used by decode function)
    """
    token = {}
    colon_count = _oauth.count(":")
    if colon_count > 1:
        # Gitlab (after refresh tokens)
        token["key"], token["secret"], token["refresh_token"] = _oauth.split(":", 2)
        if token["secret"] == " ":
            # We remove the secret if it's our placeholder value
            token["secret"] = None
    elif colon_count == 1:
        # Bitbucket
        token["key"], token["secret"] = _oauth.split(":", 1)
    else:
        # Github (and Gitlab pre refresh tokens)
        token["key"] = _oauth
        token["secret"] = None
    return token