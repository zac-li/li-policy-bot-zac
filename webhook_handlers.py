import re
import logging
from constants import OVERRIDE_ALLOWED
from gh_utils import make_github_api_call, make_github_gql_api_call, set_check_on_pr, format_query


from objectify_json import ObjectifyJSON


log = logging.getLogger(__name__)


def testing_done_pass(description):
    testing_done = description.lower().split('testing done')
    return len(testing_done) > 1 and len(testing_done[1]) > 5


def description_pass(description):
    description = description.lower().split('description')
    return len(description) > 1 and len(description[1]) > 5


def check_not_pass(description):
    # if there are more than 4 spaces, it won't be check box
    return bool(re.findall('[-\*]\s{1,4}\[\s\]', description))


def pr_template_check(webhook):
    repo_full_name = str(webhook.repository.full_name)
    description = str(webhook.pull_request.body)

    check_name = 'PR Basic Information Check'
    check_status = 'completed'
    head_sha = str(webhook.pull_request.head.sha)

    if description_pass(description):
        check_conclusion = 'success'
        output_title = 'Required information has been filed'
        output_summary = 'Required information of the PR has been filled.'
    else:
        check_conclusion = 'failure'
        output_title = 'Required information is still missing'
        output_summary = 'Please make sure the PR Description section is filled.'

    set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)


def check_trunk_status(webhook):
    """
    Steps -
    1. Check for event - PR comments
    2. Set in_progress
    3. Set status
    """
    repo_full_name = str(webhook.repository.full_name)

    check_name = 'Multiproduct Trunk Status'
    check_status = 'completed'

    pr_number = str(webhook.pull_request.number)
    head_sha = str(webhook.pull_request.head.sha)

    commits_url = f'repos/{repo_full_name}/pulls/{pr_number}/commits'
    commits = ObjectifyJSON(make_github_api_call(commits_url, 'GET', None))

    commit_messages = [str(commit['commit']['message']) for commit in commits]
    found_override = any(['TRUNKBLOCKERFIX' in commit_message for commit_message in commit_messages])

    check_conclusion = 'failure'
    output_title = 'MP locked, merge not allowed'
    output_summary = '''MP locked by owners of this Multiproduct. No new merges are allowed at this time.
    You may override this check by adding string `TRUNKBLOCKERFIX` to the comment message and sync the commit to Github.
    Doing so will notify the owners of this merge. Read more about MP lock policy [here](https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/questions/184796939/what-is-the-recommended-way-to-lock-checkins-to-multiproduct).
    '''

    if found_override:
        check_conclusion = 'success'
        output_title = 'MP lock overridden'
        output_summary = '''Forced status check to success via `TRUNKBLOCKERFIX` override.
        More information about this override can be found [here](https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/Multiproduct+Trunk+Development#MultiproductTrunkDevelopment-TRUNKBLOCKERFIX).
        '''

    set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)


def check_conversation_resolution(webhook):
    repo_full_name = str(webhook.repository.full_name)
    owner = repo_full_name.split('/')[0]
    repo = repo_full_name.split('/')[1]
    pr_number = None

    check_name = 'Conversation Resolution'
    check_status = 'completed'
    head_sha = None
    output_title = None
    output_summary = None

    # PR edit
    if webhook.pull_request.head.sha:
        pr_number = str(webhook.pull_request.number)
        head_sha = str(webhook.pull_request.head.sha)

        # Just created a new PR, will not have any review comments.
        if str(webhook.action) == 'opened':
            check_conclusion = 'success'
            output_title = 'All conversations are resolved'
            output_summary = 'Check passed as there are no unresolved comments on this Pull Request.'

            set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)

            return

    # Comment
    elif webhook.issue and webhook.issue.pull_request and webhook.comment:
        pr_info = ObjectifyJSON(make_github_api_call(str(webhook.issue.pull_request.url), 'GET', None))
        pr_number = str(webhook.issue.number)
        head_sha = str(pr_info.head.sha)

    # Re-run
    elif webhook.check_run and webhook.check_run.pull_requests:
        pr_number = str(webhook.check_run.pull_requests[0].number)
        head_sha = str(webhook.check_run.head_sha)

    # Incomplete info, give up
    if not pr_number or not head_sha:
        return

    # Set in_progress state
    set_check_on_pr(repo_full_name, check_name, 'in_progress', None, head_sha, output_title, output_summary)

    resolved, total = _get_resolved_and_total_conversations(owner, repo, pr_number)

    set_conversation_result_check(resolved, total, repo_full_name, check_name, head_sha)


def set_conversation_result_check(resolved, total, repo_full_name, check_name, head_sha):
    if resolved == total:
        check_conclusion = 'success'
        output_title = 'All conversations are resolved'
        output_summary = 'Check passed as there are no unresolved comments on this Pull Request.'
    else:
        check_conclusion = 'failure'
        output_title = f'{resolved}/{total} conversations resolved'
        output_summary = f'Check failed because only {resolved}/{total} comments resolved.'

    set_check_on_pr(repo_full_name, check_name, 'completed', check_conclusion, head_sha, output_title, output_summary)


def _get_resolved_and_total_conversations(owner, repo, pr_number):
    # Get review comments from GraphQL API
    query = format_query("""
    {
        repository(owner:"$owner", name:"$repo") {
            pullRequest(number:$pr_number) {
                reviewThreads(last: 50) {
                    nodes {
                      isResolved
                    }
                }
            }
        }
    }
    """, dict(owner=owner, repo=repo, pr_number=pr_number))

    response = ObjectifyJSON(make_github_gql_api_call(query))

    # Count the resolved and unresolved conversations.
    resolved = total = 0
    for node in response.data.repository.pullRequest.reviewThreads.nodes._data:
        total += 1
        resolved += (1 if node['isResolved'] else 0)

    return resolved, total


def get_sha(owner, repo):
    pull_requests = ObjectifyJSON(make_github_api_call(f'repos/{owner}/{repo}/pulls'))
    return {str(pull_request['number']): str(pull_request['head']['sha']) for pull_request in pull_requests}


def run_conversation_check_scan_for_prs(owner, repo):
    pr_shas = get_sha(owner, repo)
    check_name = 'Conversation Resolution'
    for pr_number, sha in pr_shas.items():
        resolved, total = _get_resolved_and_total_conversations(owner, repo, pr_number)
        log.info(f'Setting conversation resolution status ({resolved}/{total}) '
                 f'for PR: {owner}/{repo}/{pr_number} at {sha}')
        set_conversation_result_check(resolved, total, f'{owner}/{repo}', check_name, sha)


def process_override(webhook):
    repo_full_name = str(webhook.repository.full_name)
    pr_number = str(webhook.pull_request.number)

    commits_url = f'repos/{repo_full_name}/pulls/{pr_number}/commits'
    commits = ObjectifyJSON(make_github_api_call(commits_url, 'GET', None))

    override_used = set()
    commit_messages = [str(commit['commit']['message']) for commit in commits]
    for commit_message in commit_messages:
        for allowed_override in OVERRIDE_ALLOWED:
            if allowed_override in commit_message:
                override_used.add(allowed_override)

    label_url = f'repos/{repo_full_name}/issues/{pr_number}/labels'
    make_github_api_call(
        label_url,
        'POST', {
            'labels': list(override_used)
        }
    )
    log.info(f'labels: {override_used} applied')
