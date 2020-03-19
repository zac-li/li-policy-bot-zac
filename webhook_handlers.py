import logging
from gh_utils import make_github_api_call, make_github_gql_api_call, set_check_on_pr, API_BASE_URL, format_query


from objectify_json import ObjectifyJSON


"""
SPECIALIZED WEBHOOK HANDLERS 
=======================

Becaue we may receive many webhooks for many different reasons, it's a good idea
to "hand off" control from `process_message()` to a dedicated function ASAP.

This is a good place for these specialized handlers

"""
log = logging.getLogger(__name__)


def zac_test(webhook):
    log.info('Zac test! ok')

    # Gather the required information from the payload to send a successful request to GitHub REST API.
    repo_full_name = str(webhook.repository.full_name)
    pr_number = str(webhook.pull_request.number)

    comments_url = f'repos/{repo_full_name}/issues/{pr_number}/comments'

    # Make the API call.
    make_github_api_call(
        comments_url,
        'POST', {
            'body': "Zac test RB!!"
        }
    )


def pr_description_check(webhook):
    # Gather the required information from the payload to send a successful request to GitHub REST API.
    repo_full_name = str(webhook.repository.full_name)
    description = str(webhook.pull_request.body)

    testing_done = description.lower().split('testing done')

    check_name = 'PR Basic Information Check'
    check_status = 'completed'
    head_sha = str(webhook.pull_request.head.sha)
    output_title = 'Status of Completion of PR Description Section'

    if len(testing_done) > 1 and len(testing_done[1]) > 5:  # Naively assume there is something there.
        check_conclusion = 'success'
        output_summary = 'Basic information of the PR has been filled.'
    else:
        check_conclusion = 'failure'
        output_summary = 'Please fill out the Description and Testing Done section for compliance.'

    set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)


def check_trunk_status(webhook):
    """
    Steps -
    1. Check for event - PR comments
    2. Set in_progress
    3. Set status
    """
    log.info('Processing Trunk Status Check')
    repo_full_name = str(webhook.repository.full_name)

    check_name = 'Multiproduct Trunk Status'
    check_status = 'completed'

    if webhook.issue and webhook.issue.pull_request and webhook.comment:
        log.info("Issue Comment Event")

        # Automated comment, no need to refresh
        issue_author = str(webhook.issue.user.login)
        if 'linkedin' in issue_author:
            return

        # Get PR info to get Head SHA and author
        pr_number = str(webhook.issue.number)
        pr_url = f'repos/{repo_full_name}/pulls/{pr_number}'
        pr_info = ObjectifyJSON(make_github_api_call(pr_url, 'GET', None))  # ??????
        head_sha = str(pr_info.head.sha)
        author = str(pr_info.user.login)

        log.info(f"Getting comments for PR: {repo_full_name}/{pr_number} at {head_sha}")

        check_conclusion = 'failure'
        output_title = 'MP locked, merge not allowed'
        output_summary = '''MP locked by owners of this Multiproduct. No new merges are allowed at this time.
        You may override this check by adding a comment `TRUNKBLOCKERFIX` to this PR. Doing so will notify the owners of this merge.
        Read more about this policy at https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/questions/184796939/what-is-the-recommended-way-to-lock-checkins-to-multiproduct
        '''

        found_override = False

        if 'TRUNKBLOCKERFIX' in str(webhook.comment.body):
            found_override = True
        else:
            # Get comments
            comments_url = f'repos/{repo_full_name}/issues/{pr_number}/comments'
            comments = make_github_api_call(comments_url, 'GET', None)

            for comment in comments:
                comment = ObjectifyJSON(comment)
                comment_author = str(comment.user.login)
                if 'TRUNKBLOCKERFIX' in str(comment.body) and author == comment_author:
                    found_override = True
                    break

        if found_override:
            check_conclusion = 'success'
            output_title = 'MP lock overridden.'
            output_summary = '''Forced status check to success via TRUNKBLOCKERFIX override.
            More information about this override can be found at https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/Multiproduct+Trunk+Development#MultiproductTrunkDevelopment-TRUNKBLOCKERFIX
            '''

        set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)


def check_comment_resolution(webhook):
    log.info('Processing Comment Resolution Check')
    repo_full_name = str(webhook.repository.full_name)
    owner = repo_full_name.split('/')[0]
    repo = repo_full_name.split('/')[1]
    pr_number = None

    check_name = 'Comment Resolution'
    check_status = 'completed'
    check_conclusion = None
    head_sha = None
    output_title = None
    output_summary = None

    if webhook.pull_request.head.sha:
        log.info("Pull Request Event")
        pr_number = str(webhook.pull_request.number)
        head_sha = str(webhook.pull_request.head.sha)

        # Just created a new PR, will not have any review comments.
        if str(webhook.action) == 'opened':
            check_conclusion = 'success'
            output_title = 'All conversations are resolved'
            output_summary = 'Check passed as there are no unresolved comments on this Pull Request.'

            set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)

            return

    elif webhook.issue and webhook.issue.pull_request and webhook.comment:
        log.info("Issue Comment Event")
        pr_number = str(webhook.issue.number)
        pr_info = ObjectifyJSON(make_github_api_call(str(webhook.issue.pull_request.url), 'GET', None))
        head_sha = str(pr_info.head.sha)

    # Incomplete info, give up
    if not pr_number or not head_sha:
        return

    # Set in_progress state
    set_check_on_pr(repo_full_name, check_name, 'in_progress', None, head_sha, output_title, output_summary)

    log.info(f"Getting comments for PR: {repo_full_name}/{pr_number} at {head_sha}")

    # Get review comments from GraphQL API
    query = format_query("""
    {
        repository(owner:"$owner", name:"$repo") {
            issueOrPullRequest(number:$pr_number) {
            ... on PullRequest {
                id
                reviewThreads(last:50) {
                nodes {
                    id,
                    isResolved
                }
                }
                commits(last: 1) {
                nodes {
                    commit {
                    oid
                    }
                }
                }
            }
            }
        }
    }
    """, dict(owner=owner, repo=repo, pr_number=pr_number))

    response = ObjectifyJSON(make_github_gql_api_call(query))

    # Count the resolved and unresolved conversations.
    resolved = total = 0
    for node in response.data.repository.issueOrPullRequest.reviewThreads.nodes._data:
        total += 1
        resolved += (1 if node['isResolved'] else 0)

    # 2019-09-13(bwarsaw): Is it true that we can only create statuses using the v3 API?
    if resolved == total:
        check_conclusion = 'success'
        output_title = 'All conversations are resolved'
        output_summary = 'Check passed as there are no unresolved comments on this Pull Request.'
    else:
        check_conclusion = 'failure'
        output_title = f'{resolved}/{total} conversations resolved'
        output_summary = f'Check failed because only {resolved}/{total} comments resolved.'

    set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)

