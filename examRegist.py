import bs4
import requests as rq
import urllib.parse as urlparse
import getpass
import pandas as pd
import notify_run as nr
import json
import time
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

DESKTOP = 0
MOBILE = 1

PRE_LOGIN_URL = "https://auth-app-tu-delft-prd-tu-delft.xpaas.caci.nl/oauth2/authorize?response_type=token&client_id=osiris-student-mobile-prd&redirect_uri=https://my.tudelft.nl"
PAYLOAD_URL = "https://login.tudelft.nl/sso/module.php/core/loginuserpass.php"
COURSE_SEARCH_XPATH = "/html/body/ion-app/ng-component/ion-split-pane/ion-nav/page-enroll-exam/enroll-base-component/osi-page-left/ion-content/div[2]/div/osi-enroll-exam-flow/div/div/osi-course-enroll-search/osi-elastic-search/ion-row/ion-col[2]/div/div/div[1]/div[2]/div/ion-searchbar/div/input"

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
        print("\nAborting...")
        return
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

        print("Loading home page in selenium webdriver...")
        driver.get(finalUrl)
        waitForElementByClass("osi-last-login", driver)

        print("Loading the sign up page...")
        driver.get("https://my.tudelft.nl/#/inschrijven/toets/:id")
        waitForElementByClass("searchbar-input", driver)

        courseData = list(getAndSaveCoursesToCSV())
        for course in courseData[:]:
            if (course[2] == True):
                continue

            print(f"Looking for {course[1]}...")
            driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(str(course[1]))
            hasResult = False
            i = 0
            while (hasResult != True and i < 5):
                time.sleep(1)
                hasResult = scriptSearchInPage(driver, str(course[1]))
                print(f"\tSeconds passed: {i}")
                i += 1

            driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(Keys.CONTROL + "a")
            driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(Keys.BACK_SPACE)
            if (not hasResult):
                continue
            msg = f"The course '{course[1]}' is available for sign up!"
            print(msg)
            notify = nr.Notify("https://notify.run/c/8gAdT6Ns7NIlsL07")
            notify.send(msg)

        #driver.get("https://my.tudelft.nl/student/osiris/student/cursussen_voor_toetsinschrijving/te_volgen_onderwijs/open_voor_inschrijving/?limit=9999")

    input("Press any key to quit...")
    quit(driver)

def getCourseCodesManually():
    specialChars = "@ _ ! # $ % ^ & * ( ) < > ? / \ | { } ~ : . ; [ ]"
    specialChars = specialChars.replace(" ", "")
    while (True):
        courses = input("Input the course codes seperated by a comma: ")
        for char in specialChars:
            if (char in courses):
                print(f"The string is not accepted due to the '{char}'")
                autoResolve = input("Do you want remove this and run the check again? (Y/N): ")
                if (autoResolve.lower() == "y"):
                    courses = courses.replace(char, "")
                else:
                    print("Please fill in the courses again...")
                    break
            else:
                print(f"Courses: {courses}")
                courseList = formatCourses(courses)
                return courseList

def formatCourses(courses):
    courses = courses.replace(" ", "")
    courseList = courses.split(",")
    print(courseList)
    return courseList

def getAndSaveCoursesToCSV() -> list:
    courseData = []
    try:
        df = pd.read_csv("courses.csv")
        print(df)
        courseData = df.values.tolist()
        print("Existing courses found!")
        print(courseData)
        doAppend = input("Do you want to enter more? (Y/N): ")
    except:
        print("No courses found!")
        doAppend = "y"
    
    if (doAppend.lower() == "y"):
        courseList = getCourseCodesManually()
        for course in courseList:
            courseData.append([course, False])
        print(courseData)
        df = pd.DataFrame(courseData)
        print(df.values)
        df.to_csv("courses.csv")
    return courseData

def getCoursePagePayload():
    payload = json.loads('{"items":[{"hidden":false,"filter":"mijn-programma","criterium":"examenonderdelen.id_examenonderdeel","titel":"Mijn programma","waarde":null,"weergave":"UIT","toon_maximaal":null,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N"},{"hidden":false,"filter":"trefwoord","criterium":"trefwoord","titel":"Cursuscode/naam","waarde":null,"weergave":null,"toon_maximaal":null,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N"},{"hidden":false,"filter":"alleen-open-toetsinschrijving","criterium":"inschrijfperiodes_toets.datum_vanaf","titel":"Alleen open voor toetsinschrijving","waarde":["J"],"weergave":null,"toon_maximaal":null,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N","checked":true},{"hidden":false,"filter":"alleen-vaste-programma","criterium":"programma","titel":"Alleen uit mijn vaste programma","waarde":null,"weergave":null,"toon_maximaal":null,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N","checked":false},{"hidden":false,"filter":"collegejaar","criterium":"collegejaar","titel":"Collegejaar","waarde":[2021],"weergave":"UIT","toon_maximaal":2,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N"},{"hidden":false,"filter":"faculteit","criterium":"faculteit_naam","titel":"Faculteit","waarde":null,"weergave":"IN","toon_maximaal":null,"mag_wijzigen":"J","sortering":"asc","uitsluiten":null,"genest":"N"}],"cursus_ids":[104597,104584]}')
    return payload

def getCourseSearchPayload(courseCode):
    payload = {"from":25,"size":25,"sort":[{"cursus_lange_naam.raw":{"order":"asc"}},{"cursus":{"order":"asc"}},{"collegejaar":{"order":"desc"}}],"aggs":{"agg_terms_inschrijfperiodes_toets.datum_vanaf":{"filter":{"bool":{"must":[{"terms":{"collegejaar":[2021]}},{"range":{"inschrijfperiodes_toets.datum_vanaf":{"lte":"now"}}},{"range":{"inschrijfperiodes_toets.datum_tm":{"gte":"now"}}}]}},"aggs":{"agg_inschrijfperiodes_toets.datum_vanaf_buckets":{"terms":{"field":"inschrijfperiodes_toets.datum_vanaf","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_programma":{"filter":{"bool":{"must":[{"terms":{"collegejaar":[2021]}},{"terms":{"id_cursus":[-1]}}]}},"aggs":{"agg_programma_buckets":{"terms":{"field":"programma","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_collegejaar":{"filter":{"bool":{"must":[]}},"aggs":{"agg_collegejaar_buckets":{"terms":{"field":"collegejaar","size":2500,"order":{"_term":"asc"}}}}},"agg_terms_faculteit_naam":{"filter":{"bool":{"must":[{"terms":{"collegejaar":[2021]}}]}},"aggs":{"agg_faculteit_naam_buckets":{"terms":{"field":"faculteit_naam","size":2500,"order":{"_term":"asc"}}}}}},"post_filter":{"bool":{"must":[{"terms":{"collegejaar":[2021]}}]}},"query":{"bool":{"must":[{"range":{"inschrijfperiodes_toets.datum_vanaf":{"lte":"now"}}},{"range":{"inschrijfperiodes_toets.datum_tm":{"gte":"now"}}},{"multi_match":{"query":str(courseCode),"type":"phrase_prefix","fields":["cursus","cursus_korte_naam","cursus_lange_naam"],"max_expansions":200}}]}}}
    return payload

def waitForElementByClass(className, driver, timeout=30):
    try:
        elementPresent = EC.presence_of_element_located((By.CLASS_NAME, className))
        WebDriverWait(driver, timeout).until(elementPresent)
    except TimeoutException:
        print("\tTimed out...")
        driver.close()

def scriptSearchInPage(driver, course) -> bool:
    return driver.execute_script('return document.body.innerHTML.includes("LB2630")')


#getAndSaveCoursesToCSV()
main()