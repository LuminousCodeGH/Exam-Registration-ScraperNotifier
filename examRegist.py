import bs4
import requests as rq
import urllib.parse as urlparse
import html
import getpass

BUTTONS = ".button-container button"
INSCHRIJVEN_BUTTON = BUTTONS[-1]

preLoginUrl = "https://auth-app-tu-delft-prd-tu-delft.xpaas.caci.nl/oauth2/authorize?response_type=token&client_id=osiris-student-mobile-prd&redirect_uri=https://my.tudelft.nl"

password = getpass.getpass("Enter password: ")

print("Creating session...")
with rq.session() as s:
    print("Retrieving login page...")
    r = s.get(preLoginUrl)
    loginUrl = r.url
    parsedUrl = urlparse.urlparse(loginUrl)
    print(f"\tReceived redirect URL: {loginUrl}")
    query = urlparse.parse_qs(parsedUrl.query)["AuthState"]
    authState = query[0].split(":")[0]
    print(f"\tRetrieved AuthState: {authState}")

    payloadUrl = "https://login.tudelft.nl/sso/module.php/core/loginuserpass.php"

    payload = {
        "username" : "jreaves",
        "password" : password,
        "AuthState" : str(authState)
    }

    print("Attempting login...")
    r = s.post(payloadUrl, data=payload)
    print(f"\tResult: {r.url}")
    print("Login succeeded: " + str(not r.text.__contains__("Incorrect username or password")))
