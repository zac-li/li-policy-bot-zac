import os
import sys
import logging
from functools import reduce

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='[%(levelname)8s] %(process)s:%(name)s\t%(message)s')
log = logging.getLogger(__name__)


"""
SECRETS & CONFIG
=================
The following values come from your .env file, and either pertain to
your app's configuration (i.e., API_BASE_URL) or are secrets that may
have different values for each environment (staging, prod)

You'll get warnings if any of these are unset
"""


GH_USER = os.getenv("GH_USER", -1)
GH_USER_TOKEN = os.getenv("GH_USER_TOKEN", -1)
API_BASE_URL = os.getenv("API_BASE_URL", -1)
GH_APP_ID = os.getenv("GH_APP_ID", -1)
GH_APP_CLIENT_ID = os.getenv("GH_APP_CLIENT_ID", -1)
GH_APP_CLIENT_SECRET = os.getenv("GH_APP_CLIENT_SECRET", -1)
GH_APP_PRIVATE_KEY_PATH = os.getenv("GH_APP_PRIVATE_KEY_PATH", -1)


def validate_env_variables():
    env_vars = {
        "GH_USER": GH_USER,
        "GH_USER_TOKEN": GH_USER_TOKEN,
        "API_BASE_URL": API_BASE_URL,
        "GH_APP_ID": GH_APP_ID,
        "GH_APP_CLIENT_ID": GH_APP_CLIENT_ID,
        "GH_APP_CLIENT_SECRET": GH_APP_CLIENT_SECRET,
        "GH_APP_PRIVATE_KEY_PATH": GH_APP_PRIVATE_KEY_PATH
    }

    blanks_msg = reduce(lambda acc, item:
                        acc + "\n\t\t\t\t" + item[0] if (item[1] == -1 or item[1] == "") else acc, env_vars.items(), "")
    log.warn(
        "The following environment variables were found to be empty:\n"
        + blanks_msg
        + "\n\n\t\t\t\tThis may be fine, depending on which exercise you're currently working on")
