import json
import logging
import requests

from string import Template
from typing import Any, Mapping

from gh_oauth_token import retrieve_token
from bot_config import API_BASE_URL, GH_USER_TOKEN

log = logging.getLogger(__name__)


def make_github_api_call(api_path, method='GET', params=None):
    """Send API call to Github using a personal token.

Use this function to make API calls to the GitHub REST api

For example:

`GET` the current user
---
```py
me = make_github_rest_api_call('login')
```

`POST` to create a comment on a PR
---
```py
new_comment = make_github_rest_api_call(
    'repos/my_org/my_repo/issues/31/comments',
    'POST', {
        'body': "Hello there, thanks for creating a new Pull Request!"
    }
)
```
    """

    token = retrieve_token()

    # Required headers.
    headers = {'Accept': 'application/vnd.github.antiope-preview+json',
               'Content-Type': 'application/json',
               'Authorization': f'Bearer {token}'
               }

    try:
        if method.upper() == 'POST':
            response = requests.post(f'{API_BASE_URL}/{api_path}', headers=headers, data=json.dumps(
                params))
        elif method.upper() == 'GET':
            response = requests.get(f'{API_BASE_URL}/{api_path}', headers=headers)
        else:
            raise Exception('Invalid Request Method.')

        return json.loads(response.text)
    except Exception as e:
        log.exception("Could not make a successful API call to GitHub.")


def make_github_gql_api_call(query):
    """Send API call to Github GraphQL API with required Auth."""
    token = GH_USER_TOKEN

    headers = {'Accept': 'application/vnd.github.ocelot-preview;application/vnd.github.cateye-preview+json', 'Content-Type': 'application/json', 'Authorization': f'token {token}'}

    url = f'https://ghetest.trafficmanager.net/graphql?access_token={token}'

    response = requests.post(url, headers=headers, json={'query': query})
    return json.loads(response.text)


def set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title=None, output_summary=None):
    payload = {
        'name': check_name,
        'status': check_status,
        'head_sha': head_sha,
    }

    if check_conclusion:
        payload['conclusion'] = check_conclusion

    if output_title and output_summary:
        payload['output'] = dict(title=output_title, summary=output_summary)

    api_path = f'repos/{repo_full_name}/check-runs'
    make_github_api_call(api_path, 'POST', params=payload)


def format_query(template: str, variables: Mapping[str, Any]) -> str:
    """Format the GraphQL query template substituting the given mapping."""
    return Template(template).safe_substitute(variables)
