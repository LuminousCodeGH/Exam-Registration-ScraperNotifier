import bs4
import requests as rq
import urllib.parse as urlparse
import getpass
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

DESKTOP = 0
MOBILE = 1

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

def getValueByName(pageText, name) -> str:
    soup = bs4.BeautifulSoup(pageText, features="html.parser")
    value = soup.find("input", {"name" : name})["value"]
    return value

def quit(driver):
    print("Closing...")
    driver.quit()

def main():
    print("Creating webdriver...")
    try:
        driver = webdriver.Firefox(executable_path="geckodriver.exe")
    except Exception as e:
        print(f"\tAn exception occured:\n{e}")
    print("Creating session...")
    with rq.session() as s:
        print("Retrieving login page...")
        r = s.get(PRE_LOGIN_URL)
        print(f"\tReceived redirect URL: {r.url} ({r.status_code})")
        authState = getAuthState(r.url)
        print(f"\tRetrieved AuthState: {authState}")

        payload = {
            "username" : "jreaves",
            "password" : getPassword(),
            "AuthState" : str(authState)
        }

        print("Attempting login...")
        r = s.post(PAYLOAD_URL, data=payload)
        print(f"\tResponse: {r.url} ({r.status_code})")
        loginSucceeded = not r.text.__contains__("Incorrect username or password")
        print("Login succeeded: " + str(loginSucceeded))
        if (not loginSucceeded):
            print("Aborting (login credentials)...")
            return

        SAMLResponse = getValueByName(r.text, "SAMLResponse")
        print(f"SAMLResponse retrieved... ({SAMLResponse[0:10]}...)")
        payload = {
            "SAMLResponse" : SAMLResponse
        }

        print("Attempting first redirect...")
        r = s.post("https://engine.surfconext.nl/authentication/sp/consume-assertion", data=payload)
        print(f"\tResponse: {r.url} ({r.status_code})")
        
        SAMLResponse = getValueByName(r.text, "SAMLResponse")
        print(f"SAMLResponse retrieved... ({SAMLResponse[0:10]}...)")
        relayState = getValueByName(r.text, "RelayState")
        print(f"RelayState retrieved... ({relayState})")
        payload = {
            "SAMLResponse" : SAMLResponse,
            "RelayState" : relayState
        }

        print("Attempting second redirect...")
        r = s.post("https://auth-app-tu-delft-prd-tu-delft.xpaas.caci.nl/oauth2/authorize", data=payload)
        finalUrl = r.url
        print(f"\tResponse: {finalUrl} ({r.status_code})")
        if (r.status_code != 200):
            print(f"Status code: {r.status_code}")
            quit(driver)
        print("Success!")
        
        print("Loading webpage in selenium webdriver...")
        timeout = 3
        driver.get(finalUrl)
        try:
            elementPresent = EC.presence_of_element_located((By.CLASS_NAME, "osi-last-login"))
            WebDriverWait(driver, timeout).until(elementPresent)
        except TimeoutException:
            print("\tWaiting for page to load...")
        finally:
            print("\tPage loaded!")
        print("Loading the sign up page...")
        driver.get("https://my.tudelft.nl/#/inschrijven/mijn-inschrijvingen")
        print(driver.page_source)

    #quit(driver)

main()