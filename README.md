# Python GitHub App

aThis app is meant to serve as an application to help you onboard to the GitHub ecosystem and start using GitHub Webhooks & Apps.

## Getting Started

### Initial Project Setup

- Clone/Fork this repo
- Generate your virutal environment

```sh
python3 -m venv venv
```

- Activate your environment

```sh
source venv/bin/activate
```

- Install dependencies

```sh
pip3 install -r requirements.txt
```

- Run the app

```
flask run
```

## How to use setup and install the app

- Create a new repository at https://github.com/li-playground/
- Visit https://smee.io/ and click on `Start a new Channel` and note the URL
- Create a new GitHub App - https://github.com/organizations/li-playground/settings/apps/new
- Give it a distinct name and description (prefix your LDAP)
- Set `Homepage URL` = `http://localhost:5000/`
- Set `User authorization callback URL` = `http://localhost:5000/authenticate/`
- Check the checkbox for `Request user authorization (OAuth) during installation`
- Set `Webhook URL` = `<SMEE_URL>`
- Select the Radio Button for `Enable SSL verification`
- Under permissions, give `Read & Write` permissions for `Pull Requests`
- Under `Subscribe to Events`, check `Pull Request`
- Generate and Download the `Private key`, move it to your app folder on local machine and name it `.private-key`
- Hit `Save Changes`

Now you should be redirected to the App Settings -

- Under the `General` tab on the left, find out your `App ID`
- Append this `App ID` to `User authorization callback URL`, for instance, `https://localhost:5000/authenticate/40221`
- Hit `Save Changes`

- Go to the `Install` tab and install the application on `only` your repository.
- If you were redirected to GitHub Home Page, your app installation was successful.

- Open a new terminal window and navigate to where you checked out this repo and activate virual environment as above - `source venv/bin/activate`
- Run `pysmee forward <SMEE_URL> http://127.0.0.1:5000/webhook` - this will forward all events to your app.

## See it in action

- Go ahead and create a new Pull Request in the repository you just added the webhook to
- Voila! A new comment should be added to it.

## Legal

&copy; 2019 LinkedIn
