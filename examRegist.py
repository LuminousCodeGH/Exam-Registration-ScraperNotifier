import bs4
import requests as rq
import urllib.parse as urlparse
import html
import getpass

BUTTONS = ".button-container button"
INSCHRIJVEN_BUTTON = BUTTONS[-1]

PRE_LOGIN_URL = "https://auth-app-tu-delft-prd-tu-delft.xpaas.caci.nl/oauth2/authorize?response_type=token&client_id=osiris-student-mobile-prd&redirect_uri=https://my.tudelft.nl"
PAYLOAD_URL = "https://login.tudelft.nl/sso/module.php/core/loginuserpass.php"

def getPassword() -> str:
    password = getpass.getpass("Enter password: ")
    return password

def getAuthState(loginUrl) -> str:
    parsedUrl = urlparse.urlparse(loginUrl)
    query = urlparse.parse_qs(parsedUrl.query)["AuthState"]
    authState = query[0].split(":")[0]
    return authState

def main():
    print("Creating session...")
    with rq.session() as s:
        print("Retrieving login page...")
        r = s.get(PRE_LOGIN_URL)
        print(f"\tReceived redirect URL: {r.url}")
        authState = getAuthState(r.url)
        print(f"\tRetrieved AuthState: {authState}")

        print("Constructing payload...")
        payload = {
            "username" : "jreaves",
            "password" : getPassword(),
            "AuthState" : str(authState)
        }

        print("Attempting login...")
        r = s.post(PAYLOAD_URL, data=payload)
        print(f"\tResult: {r.url}")
        loginSucceeded = not r.text.__contains__("Incorrect username or password")
        print("Login succeeded: " + str(loginSucceeded))
        if (not loginSucceeded):
            print("Aborting (login credentials)...")
            return
        print(f"\n{r.text}")

        print("Attempting first redirect...")
        r = s.post("https://auth-app-tu-delft-prd-tu-delft.xpaas.caci.nl/oauth2/authorize")
        print(r.url)
        print(f"\n{r.text}")
