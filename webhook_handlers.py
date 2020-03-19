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
            'body': "Zac test yes!!"
        }
    )


def zac_test_check(webhook):
    log.info('Zac test check!!')

    # Gather the requried information from the payload to send a successful request to GitHub REST API.
    repo_full_name = str(webhook.repository.full_name)
    description = str(webhook.pull_request.body)

    testing_done = description.lower().split('testing done')

    check_name = 'Testing Done'
    check_status = 'completed'
    head_sha = str(webhook.pull_request.head.sha)
    output_title = 'Status of completion of Testing Done Section'

    if len(testing_done) > 1 and len(testing_done[1]) > 5:  # Naively assume there is something there.
        log.info("This PR already has a testing done section. Do nothing.")
        check_conclusion = 'success'
        output_summary = 'Testing Done section present. Thank you!'
    else:
        log.info("No Testing done section found.")
        check_conclusion = 'failure'
        output_summary = 'Please complete the Testing Done section of the description for compliance.'

    set_check_on_pr(repo_full_name, check_name, check_status, check_conclusion, head_sha, output_title, output_summary)


def check_trunk_status(webhook):
    """
    Steps -
    1. Check for event - PR Update and comments
    2. Set in_progress
    3. Set status
    """
    log.info('Processing Trunk Status Check')
    repo_full_name = str(webhook.repository.full_name)
    pr_number = None
    author = None

    check_name = 'Multiproduct Trunk Status'
    check_status = 'completed'
    check_conclusion = None
    head_sha = None
    output_title = None
    output_summary = None

    if webhook.pull_request:
        log.info("Pull Request Event")

        # Nothing to do if the PR was edited or synced.
        if str(webhook.action).lower() != 'opened':
            return

        head_sha = str(webhook.pull_request.head.sha)
        pr_number = str(webhook.pull_request.number)
        author = str(webhook.pull_request.user.login)

    elif webhook.issue and webhook.issue.pull_request and webhook.comment:
        log.info("Issue Comment Event")

        # Automated comment, no need to refresh
        issue_author = str(webhook.issue.user.login)
        if 'linkedin' in issue_author:
            return

        # Get PR info to get Head SHA and author
        pr_number = str(webhook.issue.number)
        pr_info = ObjectifyJSON(make_github_api_call(str(webhook.issue.pull_request.url), 'GET', None))
        head_sha = str(pr_info.head.sha)
        author = str(pr_info.user.login)

        # If the author added an override, set it and skip further validation
        if str(webhook.action) == 'created' and issue_author == author and 'TRUNKBLOCKERFIX' in str(webhook.issue.body):
            check_conclusion = 'success'
            output_title = 'Trunk lock overridden.'
            output_summary = '''Forced status check to success via TRUNKBLOCKERFIX override.
            More information about this override can be found at https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/Multiproduct+Trunk+Development#MultiproductTrunkDevelopment-TRUNKBLOCKERFIX
            '''

    if not pr_number or not head_sha:
        return

    # If not decided yet, check the comments
    if not check_conclusion:
        log.info(f"Setting Trunk check In Progress for PR: {repo_full_name}/{pr_number} at {head_sha}")

        # Set in_progress state
        set_check_on_pr(repo_full_name, check_name, 'in_progress', None, head_sha, output_title, output_summary)

        log.info(f"Getting comments for PR: {repo_full_name}/{pr_number} at {head_sha}")

        # Get comments
        comments_url = f'{API_BASE_URL}/repos/{repo_full_name}/issues/{pr_number}/comments'
        comments = make_github_api_call(comments_url, 'GET', None)
        num_comments = len(comments)

        log.info(f'Found {num_comments} comments.')

        # Look for override
        for comment in comments:
            comment = ObjectifyJSON(comment)
            comment_author = str(comment.user.login)
            if 'TRUNKBLOCKERFIX' in str(comment.body) and author == comment_author:
                check_conclusion = 'success'
                output_title = 'Trunk lock overridden.'
                output_summary = '''Forced status check to success via TRUNKBLOCKERFIX override.
                More information about this override can be found at https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/Multiproduct+Trunk+Development#MultiproductTrunkDevelopment-TRUNKBLOCKERFIX
                '''

    # If still not decided, fail the check
    if not check_conclusion:
        check_conclusion = 'failure'
        output_title = 'Trunk locked, merge not allowed'
        output_summary = '''Trunk status locked by owners of this Multiproduct.
        No new merges are allowed at this time.
        You may override this check by adding a comment `TRUNKBLOCKERFIX` to this PR. Doing so will notify the owners of this merge.
        Read more about this policy at https://iwww.corp.linkedin.com/wiki/cf/display/TOOLS/questions/184796939/what-is-the-recommended-way-to-lock-checkins-to-multiproduct
        '''

    # Finally, set the check
    if check_conclusion and head_sha and output_title and output_summary:
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

