from typing import Optional, List
import httpx

from tornado.escape import url_escape
class Github(TorngitBaseAdapter):
    def get_client(self):
        timeout = httpx.Timeout(self._timeouts[1], connect=self._timeouts[0])
        return httpx.AsyncClient(
            verify=self.verify_ssl if not isinstance(self.verify_ssl, bool) else None,
            timeout=timeout,
        )

    async def api(
        self,
        client,
        method,
        url,
        body=None,
        headers=None,
        token=None,
        statuses_to_retry=None,
        **args,
    ):
            json=body if body else None, headers=_headers, allow_redirects=False,
        max_number_retries = 3
        for current_retry in range(1, max_number_retries + 1):
            try:
                with metrics.timer(f"{METRICS_PREFIX}.api.run") as timer:
                    res = await client.request(method, url, **kwargs)
                logged_body = None
                if res.status_code >= 300 and res.text is not None:
                    logged_body = res.text
                log.log(
                    logging.WARNING if res.status_code >= 300 else logging.INFO,
                    "Github HTTP %s",
                    res.status_code,
                    extra=dict(
                        current_retry=current_retry,
                        time_taken=timer.ms,
                        body=logged_body,
                        rlx=res.headers.get("X-RateLimit-Remaining"),
                        rly=res.headers.get("X-RateLimit-Limit"),
                        rlr=res.headers.get("X-RateLimit-Reset"),
                        **log_dict,
                    ),
                )
            except httpx.TimeoutException:
                    "GitHub was not able to be reached."
                )
            if (
                not statuses_to_retry
                or res.status_code not in statuses_to_retry
                or current_retry >= max_number_retries  # Last retry
            ):
                if res.status_code == 599:
                    metrics.incr(f"{METRICS_PREFIX}.api.unreachable")
                    raise TorngitServerUnreachableError(
                        "Github was not able to be reached, server timed out."
                    )
                elif res.status_code >= 500:
                    metrics.incr(f"{METRICS_PREFIX}.api.5xx")
                    raise TorngitServer5xxCodeError("Github is having 5xx issues")
                elif res.status_code >= 300:
                    message = f"Github API: {res.reason_phrase}"
                    metrics.incr(f"{METRICS_PREFIX}.api.clienterror")
                    raise TorngitClientError(res.status_code, res, message)
                if res.status_code == 204:
                    return None
                elif res.headers.get("Content-Type")[:16] == "application/json":
                    return res.json()
                else:
                    return res.text
                log.info(
                    "Retrying due to retriable status",
                    extra=dict(status=res.status_code, **log_dict),
                )
        async with self.get_client() as client:
            token = self.get_token_by_type_if_none(token, TokenType.read)
            # https://developer.github.com/v3/repos/#list-branches
            page = 0
            branches = []
            while True:
                page += 1
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/branches" % self.slug,
                    per_page=100,
                    page=page,
                    token=token,
                )
                if len(res) == 0:
                    break
                branches.extend([(b["name"], b["commit"]["sha"]) for b in res])
                if len(res) < 100:
                    break
            return branches

    async def get_authenticated_user(self, code):
        creds = self._oauth_consumer_token()
        async with self.get_client() as client:
            session = await self.api(
                client,
                self.service_url + "/login/oauth/access_token",
                code=code,
                client_id=creds["key"],
                client_secret=creds["secret"],
            if session.get("access_token"):
                # set current token
                self.set_token(dict(key=session["access_token"]))
                user = await self.api(client, "get", "/user")
                user.update(session or {})
                return user
            else:
                return None
        async with self.get_client() as client:
            # https://developer.github.com/v3/orgs/members/#get-organization-membership
            res = await self.api(
                client,
                "get",
                "/orgs/%s/memberships/%s"
                % (self.data["owner"]["username"], user["username"]),
                token=token,
            )
            return res["state"] == "active" and res["role"] == "admin"
        async with self.get_client() as client:
            r = await self.api(client, "get", "/repos/%s" % self.slug, token=token)
            ok = r["permissions"]["admin"] or r["permissions"]["push"]
            return (True, ok)
        async with self.get_client() as client:
            if self.data["repo"].get("service_id") is None:
                # https://developer.github.com/v3/repos/#get
                res = await self.api(
                    client, "get", "/repos/%s" % self.slug, token=token
                )
            else:
                res = await self.api(
                    client,
                    "get",
                    "/repositories/%s" % self.data["repo"]["service_id"],
                    token=token,
                )
        async with self.get_client() as client:
            while True:
                page += 1
                # https://developer.github.com/v3/repos/#list-your-repositories
                res = await self.api(
                    client,
                    "get",
                    "/installation/repositories?per_page=100&page=%d" % page,
                    headers={
                        "Accept": "application/vnd.github.machine-man-preview+json"
                    },
                )
                if len(res["repositories"]) == 0:
                    break
                repos.extend([repo["id"] for repo in res["repositories"]])
                if len(res["repositories"]) < 100:
                    break
            return repos
        async with self.get_client() as client:
            while True:
                page += 1
                # https://developer.github.com/v3/repos/#list-your-repositories
                if username is None:
                    repos = await self.api(
                        client,
                        "get",
                        "/user/repos?per_page=100&page=%d" % page,
                        token=token,
                    repos = await self.api(
                        client,
                        "get",
                        "/users/%s/repos?per_page=100&page=%d" % (username, page),
                        token=token,
                    )

                for repo in repos:
                    _o, _r, parent = repo["owner"]["login"], repo["name"], None
                    if repo["fork"]:
                        # need to get its source
                        # https://developer.github.com/v3/repos/#get
                        try:
                            parent = await self.api(
                                client, "get", "/repos/%s/%s" % (_o, _r), token=token
                            )
                            parent = parent["source"]
                        except Exception:
                            parent = None

                    if parent:
                        fork = dict(
                            owner=dict(
                                service_id=parent["owner"]["id"],
                                username=parent["owner"]["login"],
                            ),
                            repo=dict(
                                service_id=parent["id"],
                                name=parent["name"],
                                language=self._validate_language(parent["language"]),
                                private=parent["private"],
                                branch=parent["default_branch"],
                            ),
                        )
                    else:
                        fork = None

                    data.append(
                        dict(
                            owner=dict(service_id=repo["owner"]["id"], username=_o),
                            repo=dict(
                                service_id=repo["id"],
                                name=_r,
                                language=self._validate_language(repo["language"]),
                                private=repo["private"],
                                branch=repo["default_branch"],
                                fork=fork,
                            ),
                        )
                if len(repos) < 100:
                    break
            return data
        async with self.get_client() as client:
            while True:
                page += 1
                orgs = await self.api(
                    client,
                    "get",
                    "/user/memberships/orgs?state=active",
                    page=page,
                    token=token,
                if len(orgs) == 0:
                    break
                # organization names
                for org in orgs:
                    organization = org["organization"]
                    org = await self.api(
                        client, "get", "/users/%s" % organization["login"], token=token
                    )
                    data.append(
                        dict(
                            name=organization.get("name", org["login"]),
                            id=str(organization["id"]),
                            email=organization.get("email"),
                            username=organization["login"],
                        )
                    )
                if len(orgs) < 30:
                    break
            return data
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                "/repos/%s/pulls/%s/commits" % (self.slug, pullid),
                token=token,
            )
            return [c["sha"] for c in res]
        async with self.get_client() as client:
            res = await self.api(
                client,
                "post",
                "/repos/%s/hooks" % self.slug,
            return res

    async def edit_webhook(self, hookid, name, url, events, secret, token=None):
        token = self.get_token_by_type_if_none(token, TokenType.admin)
        # https://developer.github.com/v3/repos/hooks/#edit-a-hook
        try:
            async with self.get_client() as client:
                return await self.api(
                    client,
                    "patch",
                    "/repos/%s/hooks/%s" % (self.slug, hookid),
                    body=dict(
                        name="web",
                        active=True,
                        events=events,
                        config=dict(url=url, secret=secret, content_type="json"),
                    ),
                    token=token,
                )
                    ce.response.text, f"Cannot find webhook {hookid}"
            async with self.get_client() as client:
                await self.api(
                    client,
                    "delete",
                    "/repos/%s/hooks/%s" % (self.slug, hookid),
                    token=token,
                )
                    ce.response.text, f"Cannot find webhook {hookid}"
        async with self.get_client() as client:
            res = await self.api(
                client,
                "post",
                "/repos/%s/issues/%s/comments" % (self.slug, issueid),
                body=dict(body=body),
                token=token,
            )
            return res
            async with self.get_client() as client:
                return await self.api(
                    client,
                    "patch",
                    "/repos/%s/issues/comments/%s" % (self.slug, commentid),
                    body=dict(body=body),
                    token=token,
                )
                    ce.response.text,
            async with self.get_client() as client:
                await self.api(
                    client,
                    "delete",
                    "/repos/%s/issues/comments/%s" % (self.slug, commentid),
                    token=token,
                )
                    ce.response.text,
        async with self.get_client() as client:
            try:
                res = await self.api(
                    client,
                    "post",
                    "/repos/%s/statuses/%s" % (self.slug, commit),
                    body=dict(
                        state=status,
                        target_url=url,
                        context=context,
                        description=description,
                    ),
                    token=token,
                )
            except TorngitClientError as ce:
                raise
            if merge_commit:
                await self.api(
                    client,
                    "post",
                    "/repos/%s/statuses/%s" % (self.slug, merge_commit[0]),
                    body=dict(
                        state=status,
                        target_url=url,
                        context=merge_commit[1],
                        description=description,
                    ),
                    token=token,
                )
            return res
        async with self.get_client() as client:
            while True:
                page += 1
                # https://developer.github.com/v3/repos/statuses/#list-statuses-for-a-specific-ref
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/commits/%s/status" % (self.slug, commit),
                    page=page,
                    per_page=100,
                    token=token,
                )
                provided_statuses = res.get("statuses", [])
                statuses.extend(
                    [
                        {
                            "time": s["updated_at"],
                            "state": s["state"],
                            "description": s["description"],
                            "url": s["target_url"],
                            "context": s["context"],
                        }
                        for s in provided_statuses
                    ]
                )
                if len(provided_statuses) < 100:
                    break
            async with self.get_client() as client:
                content = await self.api(
                    client,
                    "get",
                    "/repos/{0}/contents/{1}".format(
                        self.slug, path.replace(" ", "%20")
                    ),
                    ref=ref,
                    token=token,
                )
                    ce.response.text, f"Path {path} not found at {ref}"
            async with self.get_client() as client:
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/commits/%s" % (self.slug, commit),
                    headers={"Accept": "application/vnd.github.v3.diff"},
                    token=token,
                )
                    ce.response.text, f"Commit with id {commit} does not exist"
        return self.diff_to_json(res)
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                "/repos/%s/compare/%s...%s" % (self.slug, base, head),
                token=token,
            )
            async with self.get_client() as client:
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/commits/%s" % (self.slug, commit),
                    statuses_to_retry=[401],
                    token=token,
                )
                    ce.response.text, f"Commit with id {commit} does not exist"
                    ce.response.text, f"Repo {self.slug} cannot be found by this user",
        async with self.get_client() as client:
            try:
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/pulls/%s" % (self.slug, pullid),
                    token=token,
            except TorngitClientError as ce:
                if ce.code == 404:
                    raise TorngitObjectNotFoundError(
                        ce.response.text, f"Pull Request {pullid} not found"
                    )
                raise
            commits = await self.api(
                client,
                "get",
                "/repos/%s/pulls/%s/commits" % (self.slug, pullid),
                token=token,
                per_page=250,
            commit_mapping = {
                val["sha"]: [k["sha"] for k in val["parents"]] for val in commits
            }
            all_commits_in_pr = set([val["sha"] for val in commits])
            current_level = [res["head"]["sha"]]
            while current_level and all(x in all_commits_in_pr for x in current_level):
                new_level = []
                for x in current_level:
                    new_level.extend(commit_mapping[x])
                current_level = new_level
            result = self._pull(res)
            if current_level == [res["head"]["sha"]]:
                log.warning(
                    "Head not found in PR. PR has probably too many commits to list all of them",
                    extra=dict(number_commits=len(commits), pullid=pullid),
            else:
                possible_bases = [
                    x for x in current_level if x not in all_commits_in_pr
                ]
                if possible_bases and result["base"]["commitid"] not in possible_bases:
                    log.info(
                        "Github base differs from original base",
                        extra=dict(
                            current_level=current_level,
                            github_base=result["base"]["commitid"],
                            possible_bases=possible_bases,
                            pullid=pullid,
                        ),
                    )
                    result["base"]["commitid"] = possible_bases[0]
            return result
        async with self.get_client() as client:
            while True:
                page += 1
                res = await self.api(
                    client,
                    "get",
                    "/repos/%s/pulls" % self.slug,
                    page=page,
                    per_page=25,
                    state=state,
                    token=token,
                )
                if len(res) == 0:
                    break
                pulls.extend([pull["number"] for pull in res])
                if len(pulls) < 25:
                    break
            return pulls
        async with self.get_client() as client:
            res = await self.api(
                client, "get", "/search/issues?q=%s" % query, token=token
            )
        async with self.get_client() as client:
            content = await self.api(client, "get", url, ref=ref, token=token)
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                "/repos/%s/commits" % self.slug,
                token=token,
                sha=commitid,
            )
        async with self.get_client() as client:
            res = await self.api(
                client,
                "post",
                "/repos/{}/check-runs".format(self.slug),
                body=dict(name=check_name, head_sha=head_sha, status=status),
                headers={"Accept": "application/vnd.github.antiope-preview+json"},
                token=token,
            )
            return res["id"]
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                url,
                headers={"Accept": "application/vnd.github.antiope-preview+json"},
                token=token,
            )
            return res
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                "/repos/{}/commits/{}/check-suites".format(self.slug, git_sha),
                headers={"Accept": "application/vnd.github.antiope-preview+json"},
                token=token,
            )
            return res
        async with self.get_client() as client:
            res = await self.api(
                client,
                "patch",
                "/repos/{}/check-runs/{}".format(self.slug, check_run_id),
                body=dict(conclusion=conclusion, status=status, output=output),
                headers={"Accept": "application/vnd.github.antiope-preview+json"},
                token=token,
            )
            return res
        """
        This method formats the API response from GitHub Actions
        for any particular build/workflow run. All fields are relevant to
        validating a tokenless response.
        """
        GitHub defines a workflow and a run as the following properties:
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                "/repos/%s/actions/runs/%s" % (self.slug, run_id),
                token=token,
            )

    async def get_best_effort_branches(self, commit_sha: str, token=None) -> List[str]:
        """
        Gets a 'best effort' list of branches this commit is in.
        If a branch is returned, this means this commit is in that branch. If not, it could still be
            possible that this commit is in that branch
        Args:
            commit_sha (str): The sha of the commit we want to look at
        Returns:
            List[str]: A list of branch names
        """
        token = self.get_token_by_type_if_none(token, TokenType.read)
        url = f"/repos/{self.slug}/commits/{commit_sha}/branches-where-head"
        async with self.get_client() as client:
            res = await self.api(
                client,
                "get",
                url,
                token=token,
                headers={"Accept": "application/vnd.github.groot-preview+json"},
            )
            return [r["name"] for r in res]

    async def is_student(self):
        async with self.get_client() as client:
            res = await self.api(client, "get", "https://education.github.com/api/user")
            return res["student"]