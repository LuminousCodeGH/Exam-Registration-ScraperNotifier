import bs4
import requests as rq
import urllib.parse as urlparse
import getpass
import pandas as pd
import notify_run as nr
import time
import creds
import argparse
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
NOTIFY_RUN_ENDPOINT = "https://notify.run/c/8gAdT6Ns7NIlsL07"

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
    print("Closing driver...")
    driver.quit()

def loginAndGetCourses(password = None):
    print("Creating webdriver...")
    try:
        driverOptions = webdriver.FirefoxOptions()
        driverOptions.headless = False
        driver = webdriver.Firefox(executable_path="geckodriver.exe", options=driverOptions)
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
            "password" : (getPassword() if (password == None) else password),
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

        availableSignUps = ""
        courseData = list(getAndSaveCoursesToCSV("n"))
        adjustedCourses = []
        for course in courseData[:]:
            time.sleep(1)
            if (course[1] == True):
                continue

            print(f"Looking for {course[0]}...")
            driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(str(course[0]))
            hasResult = False
            i = 0
            while (hasResult != True and i < 5):
                time.sleep(1)
                print(f"\tSeconds passed: {i+1}")
                hasResult = scriptSearchInPage(driver, str(course[0]))
                if (scriptSearchInPage(driver, "Geen zoekresultaten")):
                    print(f"There was no course with code '{course[0]}' found...")
                    break
                i += 1

            if (not hasResult):
                driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(Keys.CONTROL + "a")
                driver.find_element_by_xpath(COURSE_SEARCH_XPATH).send_keys(Keys.BACK_SPACE)
                continue
            signedIn = course[1]
            print("Found course, verifying...")
            i = 0
            try:
                driver.find_element_by_css_selector(".osi-ion-item.ng-star-inserted").click()
            except:
                print("WARNING! There was an error while verifying the ability to sign up...")
                i = 5 #The page didn't load so there is no point for the while loop
            while (not signedIn and i < 5):
                time.sleep(1)
                print(f"\tSeconds passed: {i+1}")
                if (scriptSearchInPage(driver, "Selecteer een toetsgelegenheid")):
                    print(f"The course '{course[0]}' is available for sign up!")
                    availableSignUps += f"{course[0]} "
                    break
                elif (scriptSearchInPage(driver, "Helaas")):
                    print(f"Congratulations! There are no open sign ups for course {course[0]}")
                    course[1] = True
                    break
                i += 1
            driver.get("https://my.tudelft.nl/#/home")
            waitForElementByClass("osi-last-login", driver)

            print("Reloading the sign up page...")
            driver.get("https://my.tudelft.nl/#/inschrijven/toets/:id")
            waitForElementByClass("searchbar-input", driver)

    print("All checkups completed!")
    if (availableSignUps != ""):
        print("Found courses available for sign up...")
        msg = f"Course(s) {availableSignUps} available for sign up!"
    else:
        print("No open courses found!")
        msg = f"No open sign ups found! Congrats!"
    print("Sending notification...")
    notify = nr.Notify(NOTIFY_RUN_ENDPOINT)
    notify.send(msg)
    print("Adjusting CSV signed up column...")
    for course in courseData:
        adjustedCourses.append([course[0], course[1]])
    df = pd.DataFrame(adjustedCourses)
    print(f"New DF: \n{df}")
    df.to_csv("courses.csv")
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

def getAndSaveCoursesToCSV(doAppend = "y") -> list:
    courseData = []
    try:
        df = pd.read_csv("courses.csv", usecols=[1,2])
        courseData = df.values.tolist()
        print("Existing courses found!")
        print(f"Old DF: \n{df}")
        if (doAppend != "n"): doAppend = input("Do you want to enter more? (Y/N): ")
    except:
        print("No courses found!")
        doAppend = "y"
    
    if (doAppend.lower() == "y"):
        newCourses = getCourseCodesManually()
        newCourseData = rebuildDataframe(newCourses, courseData)
        df = pd.DataFrame(newCourseData)
        print(f"New DF: \n{df}")
        df.to_csv("courses.csv")
    return courseData

def waitForElementByClass(className, driver, timeout=30):
    try:
        elementPresent = EC.presence_of_element_located((By.CLASS_NAME, className))
        WebDriverWait(driver, timeout).until(elementPresent)
    except TimeoutException:
        print("\tTimed out...")
        quit(driver)

def scriptSearchInPage(driver, query) -> bool:
    return driver.execute_script(f'return document.body.innerHTML.includes("{query}")')

def rebuildDataframe(newCourses : list, oldCourseData : list):
    allCourses = []
    for course in oldCourseData:
        allCourses.append([course[0], course[1]])
    for course in newCourses:
        allCourses.append([course, False])
    return allCourses

def runScript(addCourses):
    print("Starting script...")
    print(f"Add courses: {addCourses}")
    if (addCourses):
        getAndSaveCoursesToCSV()
    try:
        password = creds.credPass
    except:
        password = getPassword()
    loginAndGetCourses(password)
    print("Cycle completed!")
    print("Script ended successfully...")

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument("--addCourses", nargs="?", type=bool, default=False, const=True)
args = parser.parse_args()
runScript(args.addCourses)