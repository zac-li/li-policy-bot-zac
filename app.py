from bot_config import validate_env_variables
from gh_oauth_token import get_token, store_token
from webhook_handlers import check_comment_resolution, check_trunk_status, zac_test, pr_description_check

import logging
import sys
import datetime
import traceback
import markdown2

from flask import Flask, request, redirect, render_template
from objectify_json import ObjectifyJSON

log = logging.getLogger(__name__)

# Create the Flask App.
app = Flask(__name__)


"""
STATIC PAGES
==============
These pages basically just show static HTML

"""
@app.route('/')
def welcome():
    """Welcome page"""
    return render_template("index.html", readme_html=markdown2.markdown_path("./README.md"))


"""
AUTH ROUTES
============

Dynamic routes that are needed to facilitate the authentication flow

We will let you know when it's appropriate to un-comment this
"""

@app.route("/authenticate/<app_id>", methods=["GET"])
def authenticate(app_id):
    """Incoming Installation Request. Accept and get a new token."""
    try:
        app_id = str(app_id)
        installation_id = request.args.get('installation_id')
        store_token(get_token(app_id, installation_id))

    except Exception:
        log.error("Unable to get and store token.")
        traceback.print_exc(file=sys.stderr)

    return redirect("https://www.github.com", code=302)


@app.route('/webhook', methods=['POST'])
def process_message():
    """
    WEBHOOK RECEIVER
    ==================
    If you have set up your webhook forwarding tool (i.e., smee) properly, webhook
    payloads from github end up being sent to your python app as POST requests
    to
        http://localhost:5000/webhook

    If you don't see expected payloads arrive here, please check the following

    - Is your github repo configured to deliver webhooks to a https://smee.io URL?
    - Is your github repo configured to deliver webhook payloads for the right EVENTS?
    - Is your webhook forwarding tool (i.e., pysmee or smee-client) running?
    - Is github SENDING webhooks to the same https://smee.io URL you're RECEIVING from?

    """
    webhook = ObjectifyJSON(request.json)

    if request.headers['X-Github-Event'] == 'pull_request' and str(webhook.action).lower() == 'opened':
        zac_test(webhook)
    if request.headers['X-Github-Event'] == 'pull_request' and str(webhook.action).lower() == 'edited':
        pr_description_check(webhook)
        check_comment_resolution(webhook)
    if request.headers['X-Github-Event'] == 'issue_comment' and str(webhook.action).lower() == 'created':
        check_trunk_status(webhook)

    return 'GOOD'


if __name__ == 'app' or __name__ == '__main__':
    print(
        f'\n\033[96m\033[1m--- STARTING THE APP: [{datetime.datetime.now().strftime("%m/%d, %H:%M:%S")}] ---\033[0m \n')
    validate_env_variables()
    app.run(port=8080)
