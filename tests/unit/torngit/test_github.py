import pickle
from urllib.parse import parse_qsl, urlparse

import httpx
import pytest
import respx

from shared.torngit.base import TokenType
from shared.torngit.exceptions import (
    TorngitClientError,
    TorngitClientGeneralError,
    TorngitMisconfiguredCredentials,
    TorngitObjectNotFoundError,
    TorngitRateLimitError,
    TorngitServer5xxCodeError,
    TorngitServerUnreachableError,
    TorngitUnauthorizedError,
)
from shared.torngit.github import Github
from shared.torngit.github import log as gh_log


@pytest.fixture
def respx_vcr():
    with respx.mock as v:
        yield v


@pytest.fixture
def valid_handler():
    return Github(
        repo=dict(name="example-python"),
        owner=dict(username="ThiagoCodecov"),
        token=dict(key="some_key"),
    )


@pytest.fixture
def ghapp_handler():
    return Github(
        repo=dict(name="example-python", using_integration=True),
        owner=dict(username="codecov-e2e", integration_id=10000),
        token=dict(key="integration_token"),
        oauth_consumer_token=dict(
            key="client_id",
            secret="client_secret",
        ),
    )


class TestUnitGithub(object):
    @pytest.mark.asyncio
    async def test_api_client_error_unreachable(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(return_value=mocker.MagicMock(status_code=599))
        )
        method = "GET"
        url = "random_url"
        with pytest.raises(TorngitServerUnreachableError):
            await valid_handler.api(client, method, url)

    @pytest.mark.asyncio
    async def test_api_client_error_unauthorized(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(return_value=mocker.MagicMock(status_code=401))
        )
        method = "GET"
        url = "random_url"
        with pytest.raises(TorngitUnauthorizedError):
            await valid_handler.api(client, method, url)

    @pytest.mark.asyncio
    async def test_api_client_error_ratelimit_reached(self):
        with respx.mock:
            my_route = respx.get("https://api.github.com/endpoint").mock(
                return_value=httpx.Response(
                    status_code=403,
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1350085394",
                    },
                )
            )
            handler = Github(
                repo=dict(name="aaaaa"),
                owner=dict(username="aaaaa"),
                token=dict(key="aaaaa"),
            )
            with pytest.raises(TorngitRateLimitError) as excinfo:
                async with handler.get_client() as client:
                    res = await handler.api(client, "get", "/endpoint")
            assert excinfo.value.code == 403
            assert excinfo.value.message == "Github API rate limit error: Forbidden"
            assert excinfo.value.reset == "1350085394"

    @pytest.mark.asyncio
    async def test_api_client_error_ratelimit_missing_header(self):
        with respx.mock:
            my_route = respx.get("https://api.github.com/endpoint").mock(
                return_value=httpx.Response(
                    status_code=403, headers={"X-RateLimit-Reset": "1350085394"}
                )
            )
            handler = Github(
                repo=dict(name="aaaaa"),
                owner=dict(username="aaaaa"),
                token=dict(key="aaaaa"),
            )
            with pytest.raises(TorngitClientError) as excinfo:
                async with handler.get_client() as client:
                    res = await handler.api(client, "get", "/endpoint")
            assert excinfo.value.code == 403

    @pytest.mark.asyncio
    async def test_api_client_error_server_error(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(return_value=mocker.MagicMock(status_code=503))
        )
        method = "GET"
        url = "random_url"
        with pytest.raises(TorngitServer5xxCodeError):
            await valid_handler.api(client, method, url)

    @pytest.mark.asyncio
    async def test_api_client_error_client_error(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(return_value=mocker.MagicMock(status_code=404))
        )
        method = "GET"
        url = "random_url"
        with pytest.raises(TorngitClientError):
            await valid_handler.api(client, method, url)

    @pytest.mark.asyncio
    async def test_socker_gaierror(self, mocker, valid_handler):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(
                side_effect=httpx.TimeoutException("message", request="request")
            )
        )
        with pytest.raises(TorngitServerUnreachableError):
            await valid_handler.api(
                client, "get", "/repos/%s/branches" % valid_handler.slug, per_page=100
            )

    @pytest.mark.asyncio
    async def test_api_client_query_params(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(
                return_value=mocker.MagicMock(text="kowabunga", status_code=200)
            )
        )
        method = "GET"
        url = "/random_url"
        query_params = {"qparam1": "a param", "qparam2": "another param"}
        res = await valid_handler.api(client, method, url, **query_params)
        assert res == "kowabunga"
        assert client.request.call_count == 1
        args, kwargs = client.request.call_args
        print(args)
        assert len(args) == 2
        built_url = args[1]
        parsed_url = urlparse(built_url)
        print(parsed_url)
        assert parsed_url.scheme == "https"
        assert parsed_url.netloc == "api.github.com"
        assert parsed_url.path == url
        assert parsed_url.params == ""
        assert parsed_url.fragment == ""
        query = dict(parse_qsl(parsed_url.query, keep_blank_values=True))
        assert query["qparam1"] == query_params["qparam1"]
        assert query["qparam2"] == query_params["qparam2"]

    def test_loggable_token(self, mocker, valid_handler):
        no_username_handler = Github(
            repo=dict(name="example-python"),
            owner=dict(username="ThiagoCodecov"),
            token=dict(key="some_key"),
        )
        assert no_username_handler.loggable_token(no_username_handler.token) == "f7CMr"
        with_username_handler = Github(
            repo=dict(name="example-python"),
            owner=dict(username="ThiagoCodecov"),
            token=dict(key="some_key", username="Thiago"),
        )
        assert (
            with_username_handler.loggable_token(with_username_handler.token)
            == "Thiago's token"
        )
        no_token_handler = Github(
            repo=dict(name="example-python"),
            owner=dict(username="ThiagoCodecov"),
            token=dict(key=None),
        )
        assert no_token_handler.loggable_token(no_token_handler.token) == "notoken"
        no_repo_handler = Github(
            repo=dict(),
            owner=dict(username="ThiagoCodecov"),
            token=dict(key="some_key"),
        )
        assert no_repo_handler.loggable_token(no_repo_handler.token) == "2vwGK"

    @pytest.mark.asyncio
    async def test_api_retries(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="FOUND", status_code=200),
                ]
            )
        )
        method = "GET"
        url = "random_url"
        res = await valid_handler.api(client, method, url, statuses_to_retry=[401])
        assert res == "FOUND"

    @pytest.mark.asyncio
    async def test_api_almost_too_many_retries(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="FOUND", status_code=200),
                ]
            )
        )
        method = "GET"
        url = "random_url"
        res = await valid_handler.api(client, method, url, statuses_to_retry=[401])
        assert res == "FOUND"

    @pytest.mark.asyncio
    async def test_api_too_many_retries(self, valid_handler, mocker):
        client = mocker.MagicMock(
            request=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="NOTHERE", status_code=401),
                    mocker.MagicMock(text="FOUND", status_code=200),
                ]
            )
        )
        method = "GET"
        url = "random_url"
        with pytest.raises(TorngitClientError):
            await valid_handler.api(client, method, url, statuses_to_retry=[401])

    def test_get_token_by_type_if_none(self):
        instance = Github(
            token="token",
            token_type_mapping={
                TokenType.read: "read",
                TokenType.admin: "admin",
                TokenType.comment: "comment",
                TokenType.status: "status",
            },
        )
        assert instance.get_token_by_type_if_none(None, TokenType.read) == "read"
        assert instance.get_token_by_type_if_none(None, TokenType.admin) == "admin"
        assert instance.get_token_by_type_if_none(None, TokenType.comment) == "comment"
        assert instance.get_token_by_type_if_none(None, TokenType.status) == "status"
        assert instance.get_token_by_type_if_none(
            {"key": "token_set_user"}, TokenType.read
        ) == {"key": "token_set_user"}
        assert instance.get_token_by_type_if_none(
            {"key": "token_set_user"}, TokenType.admin
        ) == {"key": "token_set_user"}
        assert instance.get_token_by_type_if_none(
            {"key": "token_set_user"}, TokenType.comment
        ) == {"key": "token_set_user"}
        assert instance.get_token_by_type_if_none(
            {"key": "token_set_user"}, TokenType.status
        ) == {"key": "token_set_user"}

    @pytest.mark.asyncio
    async def test_get_commit_diff_bad_encoding(self):
        with respx.mock:
            my_route = respx.get("https://api.github.com/endpoint").mock(
                return_value=httpx.Response(
                    status_code=200,
                    content="\xC4pple".encode("latin-1"),
                    headers={
                        "Content-Type": "application/vnd.github.v3.diff; charset=utf-8"
                    },
                )
            )
            handler = Github(
                repo=dict(name="aaaaa"),
                owner=dict(username="aaaaa"),
                token=dict(key="aaaaa"),
            )
            async with handler.get_client() as client:
                res = await handler.api(client, "get", "/endpoint")
            assert res == "\xC4pple".encode("latin-1").decode("utf-8", errors="replace")

    @pytest.mark.asyncio
    async def test_find_pull_request_success(self, mocker):
        handler = Github(
            repo=dict(name="repo_name"),
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        commit_sha = "some_commit_sha"
        mock_log = mocker.patch.object(
            gh_log, "warning"
        )  # Used to check if the log message is fired because there are 2 PRs with the commit
        with respx.mock:
            respx.get(
                url=f"https://api.github.com/repos/{handler.slug}/commits/{commit_sha}/pulls"
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    # Response for pulls endpoint returns a list directly
                    json=[
                        {
                            "id": 575148805,
                            "node_id": "MDExOlB1bFkSZXF1ZXN0MzgzMzQ4Nzc1",
                            "number": 13,
                            "title": "feat/other-pr",
                            "labels": [],
                            "state": "closed",
                            "locked": True,
                        },
                        {
                            "id": 575148804,
                            "node_id": "MDExOlB1bGxSZXF1ZXN0MzgzMzQ4Nzc1",
                            "number": 18,
                            "title": "Thiago/base no base",
                            "labels": [],
                            "state": "open",
                            "locked": False,
                        },
                        {
                            "id": 575148804,
                            "node_id": "MDExOlB1bGxSZXF1ZXN0MzgzMzQ4Nzc1",
                            "number": 19,
                            "title": "Thiago/base no base",
                            "labels": [],
                            "state": "open",
                            "locked": False,
                        },
                        {
                            "id": 575148805,
                            "node_id": "MDExOlB1bFkSZXF1ZXN0MzgzMzQ4Nzc1",
                            "number": 22,
                            "title": "feat/other-pr",
                            "labels": [],
                            "state": "closed",
                            "locked": True,
                        },
                    ],
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )

            res = await handler.find_pull_request(commit=commit_sha)
            assert res == 18
            mock_log.assert_called_with(
                "Commit is referenced in multiple PRs.",
                extra=dict(
                    prs=[18, 19],
                    commit="some_commit_sha",
                    slug="username/repo_name",
                    state="open",
                ),
            )

    @pytest.mark.asyncio
    async def test_find_pr_by_pulls_failfast_if_no_commit(self, mocker):
        handler = Github(
            repo=dict(name="repo_name"),
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        res = await handler.find_pull_request(commit=None)
        assert res is None

    @pytest.mark.asyncio
    async def test_find_pr_by_pulls_failfast_if_no_slug(self, mocker):
        handler = Github(
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        commit_sha = "some_commit_sha"
        assert handler.slug is None
        res = await handler.find_pull_request(None, commit_sha, None)
        assert res is None

    @pytest.mark.asyncio
    async def test_find_pr_by_pulls_raise_exp_if_not_422(self, mocker):
        handler = Github(
            repo=dict(name="repo_name"),
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        commit_sha = "some_commit_sha"
        with respx.mock:
            respx.get(
                url=f"https://api.github.com/repos/{handler.slug}/commits/{commit_sha}/pulls"
            ).mock(
                return_value=httpx.Response(
                    status_code=425,
                    # Response for pulls endpoint returns a list directly
                    json={"reason_phrase": "Some message"},
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )
            client = handler.get_client()
            token = handler.get_token_by_type(TokenType.read)
            with pytest.raises(TorngitClientGeneralError):
                await handler.find_pull_request(commit=commit_sha, token=token)

    @pytest.mark.asyncio
    async def test_distance_in_commits(self, mocker):
        handler = Github(
            repo=dict(name="repo_name"),
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        base_commit_sha = "some_commit_sha"
        repos_default_branch = "branch"
        with respx.mock:
            respx.get(
                url=f"https://api.github.com/repos/{handler.slug}/compare/{repos_default_branch}...{base_commit_sha}"
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    json={
                        "status": "behind",
                        "ahead_by": 0,
                        "behind_by": 10,
                        "total_commits": 0,
                        "commits": [],
                        "files": [],
                        "base_commit": {
                            "sha": "c63a6b7c0dbc9e04a3bc8c109519615098325e41",
                        },
                    },
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )
            expected_result = {
                "behind_by": 10,
                "behind_by_commit": "c63a6b7c0dbc9e04a3bc8c109519615098325e41",
                "status": "behind",
                "ahead_by": 0,
            }
            res = await handler.get_distance_in_commits(
                repos_default_branch, base_commit_sha
            )
            assert res == expected_result

    @pytest.mark.asyncio
    async def test_null_distance_in_commits(self, mocker):
        handler = Github(
            repo=dict(name="repo_name"),
            owner=dict(username="username"),
            token=dict(key="aaaaa"),
        )
        base_commit_sha = "some_commit_sha"
        repos_default_branch = "branch"
        with respx.mock:
            respx.get(
                url=f"https://api.github.com/repos/{handler.slug}/compare/{repos_default_branch}...{base_commit_sha}"
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    json={
                        "status": "behind",
                        "ahead_by": 0,
                        "behind_by": 0,
                        "total_commits": 0,
                        "commits": [],
                        "files": [],
                    },
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )
            expected_result = {
                "behind_by": None,
                "behind_by_commit": None,
                "status": "behind",
                "ahead_by": 0,
            }
            res = await handler.get_distance_in_commits(
                repos_default_branch, base_commit_sha
            )
            assert res == expected_result

    @pytest.mark.asyncio
    async def test_post_comment(self, respx_vcr, valid_handler):
        mocked_response = respx_vcr.post(
            url="https://api.github.com/repos/ThiagoCodecov/example-python/issues/1/comments",
            json={"body": "Hello world"},
        ).mock(
            return_value=httpx.Response(
                status_code=201,
                json={
                    "url": "https://api.github.com/repos/ThiagoCodecov/example-python/issues/comments/708550750",
                    "html_url": "https://github.com/ThiagoCodecov/example-python/pull/1#issuecomment-708550750",
                    "issue_url": "https://api.github.com/repos/ThiagoCodecov/example-python/issues/1",
                    "id": 708550750,
                    "node_id": "MDEyOklzc3VlQ29tbWVudDcwODU1MDc1MA==",
                    "user": {
                        "login": "ThiagoCodecov",
                        "id": 44379999,
                        "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
                        "avatar_url": "https://avatars1.githubusercontent.com/u/44379999?u=d50e43da66b2dbe47099d854ebd3b489f1162d48&v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ThiagoCodecov",
                        "html_url": "https://github.com/ThiagoCodecov",
                        "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
                        "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
                        "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
                        "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
                        "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "created_at": "2020-10-14T17:32:01Z",
                    "updated_at": "2020-10-14T17:32:01Z",
                    "author_association": "OWNER",
                    "body": "Hello world",
                    "performed_via_github_app": None,
                },
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        )
        expected_result = {
            "url": "https://api.github.com/repos/ThiagoCodecov/example-python/issues/comments/708550750",
            "html_url": "https://github.com/ThiagoCodecov/example-python/pull/1#issuecomment-708550750",
            "issue_url": "https://api.github.com/repos/ThiagoCodecov/example-python/issues/1",
            "id": 708550750,
            "node_id": "MDEyOklzc3VlQ29tbWVudDcwODU1MDc1MA==",
            "user": {
                "login": "ThiagoCodecov",
                "id": 44379999,
                "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
                "avatar_url": "https://avatars1.githubusercontent.com/u/44379999?u=d50e43da66b2dbe47099d854ebd3b489f1162d48&v=4",
                "gravatar_id": "",
                "url": "https://api.github.com/users/ThiagoCodecov",
                "html_url": "https://github.com/ThiagoCodecov",
                "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
                "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
                "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
                "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
                "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
                "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
                "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
                "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
                "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
                "type": "User",
                "site_admin": False,
            },
            "created_at": "2020-10-14T17:32:01Z",
            "updated_at": "2020-10-14T17:32:01Z",
            "author_association": "OWNER",
            "body": "Hello world",
            "performed_via_github_app": None,
        }
        res = await valid_handler.post_comment("1", "Hello world")
        assert res == expected_result
        assert mocked_response.called is True

    @pytest.mark.asyncio
    async def test_list_teams(self, valid_handler, respx_vcr):
        mocked_response = respx_vcr.get(
            url="https://api.github.com/user/memberships/orgs?state=active&page=1"
        ).respond(
            status_code=200,
            json=[
                {
                    "url": "https://api.github.com/orgs/codecov/memberships/ThiagoCodecov",
                    "state": "active",
                    "role": "member",
                    "organization_url": "https://api.github.com/orgs/codecov",
                    "user": {
                        "login": "ThiagoCodecov",
                        "id": 44379999,
                        "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
                        "avatar_url": "https://avatars3.githubusercontent.com/u/44379999?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ThiagoCodecov",
                        "html_url": "https://github.com/ThiagoCodecov",
                        "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
                        "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
                        "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
                        "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
                        "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "organization": {
                        "login": "codecov",
                        "id": 8226999,
                        "node_id": "MDEyOk9yZ2FuaXphdGlvbjgyMjYyMDU=",
                        "url": "https://api.github.com/orgs/codecov",
                        "repos_url": "https://api.github.com/orgs/codecov/repos",
                        "events_url": "https://api.github.com/orgs/codecov/events",
                        "hooks_url": "https://api.github.com/orgs/codecov/hooks",
                        "issues_url": "https://api.github.com/orgs/codecov/issues",
                        "members_url": "https://api.github.com/orgs/codecov/members{/member}",
                        "public_members_url": "https://api.github.com/orgs/codecov/public_members{/member}",
                        "avatar_url": "https://avatars3.githubusercontent.com/u/8226999?v=4",
                        "description": "Empower developers with tools to improve code quality and testing.",
                    },
                },
                {
                    "url": "https://api.github.com/orgs/ThiagoCodecovTeam/memberships/ThiagoCodecov",
                    "state": "active",
                    "role": "admin",
                    "organization_url": "https://api.github.com/orgs/ThiagoCodecovTeam",
                    "user": {
                        "login": "ThiagoCodecov",
                        "id": 44379999,
                        "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
                        "avatar_url": "https://avatars3.githubusercontent.com/u/44379999?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ThiagoCodecov",
                        "html_url": "https://github.com/ThiagoCodecov",
                        "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
                        "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
                        "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
                        "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
                        "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "organization": {
                        "login": "ThiagoCodecovTeam",
                        "id": 57222756,
                        "node_id": "MDEyOk9yZ2FuaXphdGlvbjU3MjIyNzU2",
                        "url": "https://api.github.com/orgs/ThiagoCodecovTeam",
                        "repos_url": "https://api.github.com/orgs/ThiagoCodecovTeam/repos",
                        "events_url": "https://api.github.com/orgs/ThiagoCodecovTeam/events",
                        "hooks_url": "https://api.github.com/orgs/ThiagoCodecovTeam/hooks",
                        "issues_url": "https://api.github.com/orgs/ThiagoCodecovTeam/issues",
                        "members_url": "https://api.github.com/orgs/ThiagoCodecovTeam/members{/member}",
                        "public_members_url": "https://api.github.com/orgs/ThiagoCodecovTeam/public_members{/member}",
                        "avatar_url": "https://avatars0.githubusercontent.com/u/57222756?v=4",
                        "description": False,
                    },
                },
            ],
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        team_dicts = [
            (
                "https://api.github.com/users/codecov",
                {
                    "login": "codecov",
                    "id": 8226999,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjgyMjYyMDU=",
                    "avatar_url": "https://avatars3.githubusercontent.com/u/8226999?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/codecov",
                    "html_url": "https://github.com/codecov",
                    "followers_url": "https://api.github.com/users/codecov/followers",
                    "following_url": "https://api.github.com/users/codecov/following{/other_user}",
                    "gists_url": "https://api.github.com/users/codecov/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/codecov/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/codecov/subscriptions",
                    "organizations_url": "https://api.github.com/users/codecov/orgs",
                    "repos_url": "https://api.github.com/users/codecov/repos",
                    "events_url": "https://api.github.com/users/codecov/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/codecov/received_events",
                    "type": "Organization",
                    "site_admin": False,
                    "name": "Codecov",
                    "company": None,
                    "blog": "https://codecov.io/",
                    "location": None,
                    "email": "hello@codecov.io",
                    "hireable": None,
                    "bio": "Empower developers with tools to improve code quality and testing.",
                    "twitter_username": None,
                    "public_repos": 97,
                    "public_gists": 0,
                    "followers": 0,
                    "following": 0,
                    "created_at": "2014-07-21T16:22:31Z",
                    "updated_at": "2020-10-28T19:29:26Z",
                },
            ),
            (
                "https://api.github.com/users/ThiagoCodecovTeam",
                {
                    "login": "ThiagoCodecovTeam",
                    "id": 57222756,
                    "node_id": "MDEyOk9yZ2FuaXphdGlvbjU3MjIyNzU2",
                    "avatar_url": "https://avatars0.githubusercontent.com/u/57222756?v=4",
                    "gravatar_id": "",
                    "url": "https://api.github.com/users/ThiagoCodecovTeam",
                    "html_url": "https://github.com/ThiagoCodecovTeam",
                    "followers_url": "https://api.github.com/users/ThiagoCodecovTeam/followers",
                    "following_url": "https://api.github.com/users/ThiagoCodecovTeam/following{/other_user}",
                    "gists_url": "https://api.github.com/users/ThiagoCodecovTeam/gists{/gist_id}",
                    "starred_url": "https://api.github.com/users/ThiagoCodecovTeam/starred{/owner}{/repo}",
                    "subscriptions_url": "https://api.github.com/users/ThiagoCodecovTeam/subscriptions",
                    "organizations_url": "https://api.github.com/users/ThiagoCodecovTeam/orgs",
                    "repos_url": "https://api.github.com/users/ThiagoCodecovTeam/repos",
                    "events_url": "https://api.github.com/users/ThiagoCodecovTeam/events{/privacy}",
                    "received_events_url": "https://api.github.com/users/ThiagoCodecovTeam/received_events",
                    "type": "Organization",
                    "site_admin": False,
                    "name": None,
                    "company": None,
                    "blog": "",
                    "location": None,
                    "email": None,
                    "hireable": None,
                    "bio": None,
                    "twitter_username": None,
                    "public_repos": 0,
                    "public_gists": 0,
                    "followers": 0,
                    "following": 0,
                    "created_at": "2019-10-31T13:07:24Z",
                    "updated_at": "2019-10-31T13:07:24Z",
                },
            ),
        ]
        for url, data in team_dicts:
            respx_vcr.get(url=url).respond(
                status_code=200,
                json=data,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
        expected_result = [
            {"email": None, "id": "8226999", "name": "codecov", "username": "codecov"},
            {
                "email": None,
                "id": "57222756",
                "name": "ThiagoCodecovTeam",
                "username": "ThiagoCodecovTeam",
            },
        ]
        res = await valid_handler.list_teams()
        assert res == expected_result
        assert mocked_response.called is True

    @pytest.mark.asyncio
    async def test_list_team_with_org_response_404(self, valid_handler, respx_vcr):
        mocked_response = respx_vcr.get(
            url="https://api.github.com/user/memberships/orgs?state=active&page=1"
        ).respond(
            status_code=200,
            json=[
                {
                    "url": "https://api.github.com/orgs/codecov/memberships/ThiagoCodecov",
                    "state": "active",
                    "role": "member",
                    "organization_url": "https://api.github.com/orgs/codecov",
                    "user": {
                        "login": "ThiagoCodecov",
                        "id": 44379999,
                        "node_id": "MDQ6VXNlcjQ0Mzc2OTkx",
                        "avatar_url": "https://avatars3.githubusercontent.com/u/44379999?v=4",
                        "gravatar_id": "",
                        "url": "https://api.github.com/users/ThiagoCodecov",
                        "html_url": "https://github.com/ThiagoCodecov",
                        "followers_url": "https://api.github.com/users/ThiagoCodecov/followers",
                        "following_url": "https://api.github.com/users/ThiagoCodecov/following{/other_user}",
                        "gists_url": "https://api.github.com/users/ThiagoCodecov/gists{/gist_id}",
                        "starred_url": "https://api.github.com/users/ThiagoCodecov/starred{/owner}{/repo}",
                        "subscriptions_url": "https://api.github.com/users/ThiagoCodecov/subscriptions",
                        "organizations_url": "https://api.github.com/users/ThiagoCodecov/orgs",
                        "repos_url": "https://api.github.com/users/ThiagoCodecov/repos",
                        "events_url": "https://api.github.com/users/ThiagoCodecov/events{/privacy}",
                        "received_events_url": "https://api.github.com/users/ThiagoCodecov/received_events",
                        "type": "User",
                        "site_admin": False,
                    },
                    "organization": {
                        "login": "codecov",
                        "id": 8226999,
                        "node_id": "MDEyOk9yZ2FuaXphdGlvbjgyMjYyMDU=",
                        "url": "https://api.github.com/orgs/codecov",
                        "repos_url": "https://api.github.com/orgs/codecov/repos",
                        "events_url": "https://api.github.com/orgs/codecov/events",
                        "hooks_url": "https://api.github.com/orgs/codecov/hooks",
                        "issues_url": "https://api.github.com/orgs/codecov/issues",
                        "members_url": "https://api.github.com/orgs/codecov/members{/member}",
                        "public_members_url": "https://api.github.com/orgs/codecov/public_members{/member}",
                        "avatar_url": "https://avatars3.githubusercontent.com/u/8226999?v=4",
                        "description": "Empower developers with tools to improve code quality and testing.",
                    },
                }
            ],
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

        respx_vcr.get(url="https://api.github.com/users/codecov").respond(
            status_code=404,
            json={},
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        res = await valid_handler.list_teams()
        assert res == []
        assert mocked_response.called is True

    @pytest.mark.asyncio
    async def test_update_check_run_no_url(self, valid_handler):
        with respx.mock:
            mocked_response = respx.patch(
                url="https://api.github.com/repos/ThiagoCodecov/example-python/check-runs/1256232357",
                json={"conclusion": "success", "status": "completed", "output": None},
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    # response doesn't matter here
                    json={},
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )

            res = await valid_handler.update_check_run(1256232357, "success")

        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_update_check_run_url(self, valid_handler):
        url = "https://app.codecov.io/gh/codecov/example-python/compare/1?src=pr"
        with respx.mock:
            mocked_response = respx.patch(
                url="https://api.github.com/repos/ThiagoCodecov/example-python/check-runs/1256232357",
                json={
                    "conclusion": "success",
                    "status": "completed",
                    "output": None,
                    "details_url": "https://app.codecov.io/gh/codecov/example-python/compare/1?src=pr",
                },
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    # response doesn't matter here
                    json={},
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )
            res = await valid_handler.update_check_run(1256232357, "success", url=url)
        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_get_general_exception_pickle(self, valid_handler):
        with respx.mock:
            mocked_response = respx.get(
                url="https://api.github.com/repos/ThiagoCodecov/example-python/pulls?page=1&per_page=25&state=open"
            ).mock(
                return_value=httpx.Response(
                    status_code=404,
                    # response doesn't matter here
                    json={},
                    headers={"Content-Type": "application/json; charset=utf-8"},
                )
            )
            with pytest.raises(TorngitClientGeneralError) as ex:
                await valid_handler.get_pull_requests()
            error = ex.value
            text = pickle.dumps(error)
            renegerated_error = pickle.loads(text)
            assert isinstance(renegerated_error, TorngitClientGeneralError)
            assert renegerated_error.code == error.code

        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_api_no_token(self):
        c = Github()
        with pytest.raises(TorngitMisconfiguredCredentials):
            await c.api()

    @pytest.mark.asyncio
    async def test_paginated_api_no_token(self, mocker):
        c = Github()
        with pytest.raises(TorngitMisconfiguredCredentials):
            async for page in c.paginated_api_generator(
                mocker.MagicMock(), mocker.MagicMock(), mocker.MagicMock()
            ):
                pass

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries(self, ghapp_handler):
        def side_effect(request):
            assert request.headers.get("Accept") == "application/vnd.github+json"
            assert (
                request.headers.get("Authorization")
                == f"Bearer {ghapp_handler.token['key']}"
            )

            return httpx.Response(
                status_code=200,
                json=[
                    {
                        "id": 17324040107,
                        "guid": "53c93580-7a6e-11ed-96c9-5e1ce3e5574e",  # this value is the same accross redeliveries
                        "delivered_at": "2022-12-12T22:42:59Z",
                        "redelivery": False,
                        "duration": 0.37,
                        "status": "OK",
                        "status_code": 200,
                        "event": "installation_repositories",  # when you add / remove repos from installation
                        "action": "added",
                        "installation_id": None,
                        "repository_id": None,
                        "url": "",
                    },
                    {
                        "id": 17324018336,
                        "guid": "40d7f830-7a6e-11ed-8b90-0777e88b1858",
                        "delivered_at": "2022-12-12T22:42:30Z",
                        "redelivery": False,
                        "duration": 2.31,
                        "status": "OK",
                        "status_code": 200,
                        "event": "installation_repositories",
                        "action": "removed",
                        "installation_id": None,
                        "repository_id": None,
                        "url": "",
                    },
                    {
                        "id": 17323292984,
                        "guid": "0498e8e0-7a6c-11ed-8834-c5eb5a4b102a",
                        "delivered_at": "2022-12-12T22:26:28Z",
                        "redelivery": False,
                        "duration": 0.69,
                        "status": "Invalid HTTP Response: 400",
                        "status_code": 400,
                        "event": "installation",  # A new installation
                        "action": "created",
                        "installation_id": None,
                        "repository_id": None,
                        "url": "",
                    },
                    {
                        "id": 17323228732,
                        "guid": "d41fa780-7a6b-11ed-8890-0619085a3f97",
                        "delivered_at": "2022-12-12T22:25:07Z",
                        "redelivery": False,
                        "duration": 0.74,
                        "status": "Invalid HTTP Response: 400",
                        "status_code": 400,
                        "event": "installation",
                        "action": "deleted",
                        "installation_id": None,
                        "repository_id": None,
                        "url": "",
                    },
                ],
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        with respx.mock:
            mocked_response = respx.get(
                url="https://api.github.com/app/hook/deliveries?per_page=50",
            ).mock(side_effect=side_effect)
            async for res in ghapp_handler.list_webhook_deliveries():
                assert len(res) == 4
        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_list_webhook_deliveries_multiple_pages(self, ghapp_handler):
        with respx.mock:
            mocked_response_1 = respx.get(
                url="https://api.github.com/app/hook/deliveries?per_page=50"
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    headers=dict(
                        link='<https://api.github.com/app/hook/deliveries?per_page=50&cursor=v1_17323292984>; rel="next"'
                    ),
                    json=[
                        {
                            "id": 17324040107,
                            "guid": "53c93580-7a6e-11ed-96c9-5e1ce3e5574e",  # this value is the same accross redeliveries
                            "delivered_at": "2022-12-12T22:42:59Z",
                            "redelivery": False,
                            "duration": 0.37,
                            "status": "OK",
                            "status_code": 200,
                            "event": "installation_repositories",  # when you add / remove repos from installation
                            "action": "added",
                            "installation_id": None,
                            "repository_id": None,
                            "url": "",
                        },
                        {
                            "id": 17324018336,
                            "guid": "40d7f830-7a6e-11ed-8b90-0777e88b1858",
                            "delivered_at": "2022-12-12T22:42:30Z",
                            "redelivery": False,
                            "duration": 2.31,
                            "status": "OK",
                            "status_code": 200,
                            "event": "installation_repositories",
                            "action": "removed",
                            "installation_id": None,
                            "repository_id": None,
                            "url": "",
                        },
                    ],
                )
            )
            mocked_response_2 = respx.get(
                url="https://api.github.com/app/hook/deliveries?per_page=50&cursor=v1_17323292984"
            ).mock(
                return_value=httpx.Response(
                    status_code=200,
                    json=[
                        {
                            "id": 17323292984,
                            "guid": "0498e8e0-7a6c-11ed-8834-c5eb5a4b102a",
                            "delivered_at": "2022-12-12T22:26:28Z",
                            "redelivery": False,
                            "duration": 0.69,
                            "status": "Invalid HTTP Response: 400",
                            "status_code": 400,
                            "event": "installation",  # A new installation
                            "action": "created",
                            "installation_id": None,
                            "repository_id": None,
                            "url": "",
                        },
                        {
                            "id": 17323228732,
                            "guid": "d41fa780-7a6b-11ed-8890-0619085a3f97",
                            "delivered_at": "2022-12-12T22:25:07Z",
                            "redelivery": False,
                            "duration": 0.74,
                            "status": "Invalid HTTP Response: 400",
                            "status_code": 400,
                            "event": "installation",
                            "action": "deleted",
                            "installation_id": None,
                            "repository_id": None,
                            "url": "",
                        },
                    ],
                )
            )
            aggregate_res = []
            async for res in ghapp_handler.list_webhook_deliveries():
                assert len(res) == 2
                aggregate_res += res
        assert len(aggregate_res) == 4
        assert mocked_response_1.call_count == 1
        assert mocked_response_2.call_count == 1

    @pytest.mark.asyncio
    async def test_webhook_redelivery_success(self, ghapp_handler):
        delivery_id = 17323228732

        def side_effect(request):
            assert request.headers.get("Accept") == "application/vnd.github+json"
            assert (
                request.headers.get("Authorization")
                == f"Bearer {ghapp_handler.token['key']}"
            )
            assert request.method == "POST"
            return httpx.Response(
                status_code=202, headers={"Content-Type": "applicaiton/json"}
            )

        with respx.mock:
            mocked_response = respx.post(
                url=f"https://api.github.com/app/hook/deliveries/{delivery_id}/attempts"
            ).mock(side_effect=side_effect)
            ans = await ghapp_handler.request_webhook_redelivery(delivery_id)
            assert ans is True
        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_webhook_redelivery_fail(self, ghapp_handler):
        delivery_id = 17323228732
        with respx.mock:
            mocked_response = respx.post(
                url=f"https://api.github.com/app/hook/deliveries/{delivery_id}/attempts"
            ).mock(
                return_value=httpx.Response(
                    status_code=422, headers={"Content-Type": "applicaiton/json"}
                ),
            )
            ans = await ghapp_handler.request_webhook_redelivery(delivery_id)
            assert ans is False
        assert mocked_response.call_count == 1

    @pytest.mark.asyncio
    async def test_get_pull_request_files_404(self):
        with respx.mock:
            my_route = respx.get(
                "https://api.github.com/repos/codecove2e/example-python/pulls/4/files"
            ).mock(
                return_value=httpx.Response(
                    status_code=404,
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1350085394",
                    },
                )
            )
            handler = Github(
                repo=dict(name="example-python"),
                owner=dict(username="codecove2e"),
                token=dict(key=10 * "a280"),
            )
            with pytest.raises(TorngitObjectNotFoundError) as excinfo:
                res = await handler.get_pull_request_files(4)
            assert excinfo.value.code == 404
            assert excinfo.value.message == "PR with id 4 does not exist"

    @pytest.mark.asyncio
    async def test_get_pull_request_files_403(self):
        with respx.mock:
            my_route = respx.get(
                "https://api.github.com/repos/codecove2e/example-python/pulls/4/files"
            ).mock(
                return_value=httpx.Response(
                    status_code=403,
                    headers={
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": "1350085394",
                    },
                )
            )
            handler = Github(
                repo=dict(name="example-python"),
                owner=dict(username="codecove2e"),
                token=dict(key=10 * "a280"),
            )
            with pytest.raises(TorngitClientError) as excinfo:
                res = await handler.get_pull_request_files(4)
            assert excinfo.value.code == 403
            assert excinfo.value.message == "Github API rate limit error: Forbidden"

    @pytest.mark.asyncio
    async def test_get_pull_request_files_403_secondary_limit(self):
        with respx.mock:
            my_route = respx.get(
                "https://api.github.com/repos/codecove2e/example-python/pulls/4/files"
            ).mock(
                return_value=httpx.Response(
                    status_code=403,
                    headers={
                        "Retry-After": "60",
                    },
                )
            )
            handler = Github(
                repo=dict(name="example-python"),
                owner=dict(username="codecove2e"),
                token=dict(key=10 * "a280"),
            )
            with pytest.raises(TorngitRateLimitError) as excinfo:
                res = await handler.get_pull_request_files(4)
            assert excinfo.value.code == 403
            assert (
                excinfo.value.message
                == "Github API rate limit error: secondary rate limit"
            )
            assert excinfo.value.retry_after == 60
