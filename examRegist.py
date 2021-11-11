import bs4
import requests as rq
import urllib.parse as urlparse
import getpass
import pandas as pd
import smtplib, ssl
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

LOGIN_PROMPT_URL = creds.login_prompt_url
LOGIN_PAYLOAD_URL = creds.login_payload_url
FIRST_REDIRECT_PAYLOAD_URL = creds.first_redirect_payload_url
SECOND_REDIRECT_PAYLOAD_URL = creds.second_redirect_payload_url
OSIRIS_EXAM_SIGN_UP_URL = creds.osiris_exam_sign_up_url
OSIRIS_HOME_URL = creds.osiris_home_url

HOME_PAGE_WAIT_ELEMENT_CLASS = "osi-last-login"
SIGN_UP_PAGE_WAIT_CLASS = "searchbar-input"
COURSE_SEARCH_ELEMENT_XPATH = "/html/body/ion-app/ng-component/ion-split-pane/ion-nav/page-enroll-exam/enroll-base-component/osi-page-left/ion-content/div[2]/div/osi-enroll-exam-flow/div/div/osi-course-enroll-search/osi-elastic-search/ion-row/ion-col[2]/div/div/div[1]/div[2]/div/ion-searchbar/div/input"
SIGN_UP_ELEMENT_CSS_SELECTOR = ".osi-ion-item.ng-star-inserted"

SENDER = creds.sender_mail
RECEIVER = creds.receiver_mail

def get_password() -> str:
    password = getpass.getpass("Enter password: ")
    return password

def get_and_save_courses_to_csv(do_append = "y") -> list:
    course_data = []
    try:
        df = pd.read_csv("courses.csv", usecols=[1,2])
        course_data = df.values.tolist()
        print("Existing courses found!")
        print(f"Old DF: \n{df}")
        if (do_append != "n"): do_append = input("Do you want to enter more? (Y/N): ")
    except:
        print("No courses found!")
        do_append = "y"
    
    if (do_append.lower() == "y"):
        new_courses = get_course_codes_manually()
        new_course_data = rebuild_dataframe(new_courses, course_data)
        df = pd.DataFrame(new_course_data)
        print(f"New DF: \n{df}")
        df.to_csv("courses.csv")
    return course_data

def get_course_codes_manually():
    while (True):
        courses = input("Input the course codes seperated by a comma: ")
        print(f"\tInput: {courses}")
        continue_prompt = input("Is this input OK? (Y/N): ")
        if (continue_prompt.lower() == "y"):
            break
    course_list = format_courses(courses)
    return course_list

def format_courses(courses):
    courses = courses.replace(" ", "")
    course_list = courses.split(",")
    print(course_list)
    return course_list

def rebuild_dataframe(new_courses : list, old_course_data : list):
    all_courses = []
    for course in old_course_data:
        all_courses.append([course[0], course[1]])
    for course in new_courses:
        all_courses.append([course, False])
    return all_courses

def create_webdriver():
    print("Creating webdriver...")
    try:
        driver_options = webdriver.FirefoxOptions()
        driver_options.headless = False
        driver = webdriver.Firefox(executable_path="geckodriver.exe", options=driver_options)
    except Exception as e:
        print(f"\tAn exception occured:\n{e}")
        print("\nAborting (webdriver)...")
        return False
    return driver

def get_auth_state(login_url) -> str:
    parsed_url = urlparse.urlparse(login_url)
    query = urlparse.parse_qs(parsed_url.query)["AuthState"]
    auth_state = query[0].split(":")[0]
    return auth_state

def get_value_by_name(page_text, name) -> str:
    soup = bs4.BeautifulSoup(page_text, features="html.parser")
    value = soup.find("input", {"name" : name})["value"]
    return value

def wait_for_element_by_class(class_name, driver, timeout=30):
    try:
        element_present = EC.presence_of_element_located((By.CLASS_NAME, class_name))
        WebDriverWait(driver, timeout).until(element_present)
    except TimeoutException:
        print("\tTimed out...")
        quit(driver)

def script_search_in_page(driver, query) -> bool:
    return driver.execute_script(f'return document.body.innerHTML.includes("{query}")')

def quit(driver):
    print("Closing driver...")
    driver.quit()

def save_adjusted_courses(adjusted_course_list, course_data):
    print("Adjusting CSV signed up column...")
    for course in course_data:
        adjusted_course_list.append([course[0], course[1]])
    df = pd.DataFrame(adjusted_course_list)
    print(f"New DF: \n{df}")
    df.to_csv("courses.csv")

def send_email(available_sign_ups : str):
        port = 465
        smtp_server_domain = "smtp.gmail.com"
        sender_mail = SENDER
        sender_pass = creds.mail_pass

        print("Sending mail...")
        try:
            ssl_context = ssl.create_default_context()
            service = smtplib.SMTP_SSL(smtp_server_domain, port, context=ssl_context)
            service.login(sender_mail, sender_pass)
            mail_result = service.sendmail(sender_mail, creds.receiver_mail, f"Subject: open sign ups!\nThese exams are available for sign up: {available_sign_ups}")
            service.quit()
            print(f"\tSuccess!")
        except Exception as e:
            print(f"\tThere was an error sending the email:\n{e}")

def login_and_get_courses(driver, password = None, check_resits = False):
    print("Creating session...")
    with rq.session() as s:
        print("Retrieving login page...")
        r = s.get(LOGIN_PROMPT_URL)
        print(f"\tReceived redirect URL: {r.url[0:5]}(...){r.url[-6:-1]} ({r.status_code})")
        auth_state = get_auth_state(r.url)
        print(f"\tRetrieved AuthState: {auth_state}")

        payload = {
            "username" : "jreaves",
            "password" : (get_password() if (password == None) else password),
            "AuthState" : str(auth_state)
        }

        print("Attempting login...")
        r = s.post(LOGIN_PAYLOAD_URL, data=payload)
        print(f"\tResponse: {r.url[0:5]}(...){r.url[-6:-1]} ({r.status_code})")
        login_succeeded = not r.text.__contains__("Incorrect username or password")
        print("Login succeeded: " + str(login_succeeded))
        if (not login_succeeded):
            print("Aborting (login credentials)...")
            return False

        SAML_response = get_value_by_name(r.text, "SAMLResponse")
        print(f"SAMLResponse retrieved... ({SAML_response[0:10]}...)")
        payload = {
            "SAMLResponse" : SAML_response
        }

        print("Attempting first redirect...")
        r = s.post(FIRST_REDIRECT_PAYLOAD_URL, data=payload)
        print(f"\tResponse: {r.url[0:5]}(...){r.url[-6:-1]} ({r.status_code})")
        
        SAML_response = get_value_by_name(r.text, "SAMLResponse")
        print(f"SAMLResponse retrieved... ({SAML_response[0:10]}...)")
        relay_state = get_value_by_name(r.text, "RelayState")
        print(f"RelayState retrieved... ({relay_state})")
        payload = {
            "SAMLResponse" : SAML_response,
            "RelayState" : relay_state
        }

        print("Attempting second redirect...")
        r = s.post(SECOND_REDIRECT_PAYLOAD_URL, data=payload)
        secure_osiris_url = r.url
        print(f"\tResponse: {secure_osiris_url[0:5]}(...){secure_osiris_url[-6:-1]} ({r.status_code})")
        if (r.status_code != 200):
            print(f"Status code: {r.status_code}")
            quit(driver)
        print("Success!")

        print("Loading home page in selenium webdriver...")
        driver.get(secure_osiris_url)
        wait_for_element_by_class(HOME_PAGE_WAIT_ELEMENT_CLASS, driver)

        print("Loading the sign up page...")
        driver.get(OSIRIS_EXAM_SIGN_UP_URL)
        wait_for_element_by_class(SIGN_UP_PAGE_WAIT_CLASS, driver)

        available_sign_ups = ""
        course_data = list(get_and_save_courses_to_csv("n"))
        adjusted_course_list = []
        for course in course_data[:]:
            time.sleep(1)
            if (course[1] == True and not check_resits):
                continue

            print(f"Looking for {course[0]}...")
            driver.find_element_by_xpath(COURSE_SEARCH_ELEMENT_XPATH).send_keys(str(course[0]))
            has_result = False
            i = 0
            while (has_result != True and i < 5):
                time.sleep(1)
                print(f"\tSeconds passed: {i+1}")
                has_result = script_search_in_page(driver, str(course[0]))
                if (script_search_in_page(driver, "Geen zoekresultaten")):
                    print(f"There was no course with code '{course[0]}' found...")
                    break
                i += 1

            if (not has_result):
                driver.find_element_by_xpath(COURSE_SEARCH_ELEMENT_XPATH).send_keys(Keys.CONTROL + "a")
                driver.find_element_by_xpath(COURSE_SEARCH_ELEMENT_XPATH).send_keys(Keys.BACK_SPACE)
                continue
            signed_in = course[1]
            print("Found course, verifying...")
            i = 0
            try:
                driver.find_element_by_css_selector(SIGN_UP_ELEMENT_CSS_SELECTOR).click()
            except:
                print("WARNING! There was an error while verifying the ability to sign up...")
                i = 5 #The page didn't load so there is no point for the while loop
            while (not signed_in and i < 5):
                time.sleep(1)
                print(f"\tSeconds passed: {i+1}")
                if (script_search_in_page(driver, "Selecteer een toetsgelegenheid")):
                    print(f"The course '{course[0]}' is available for sign up!")
                    available_sign_ups += f"{course[0]} "
                    break
                elif (script_search_in_page(driver, "Helaas")):
                    print(f"Congratulations! There are no open sign ups for course {course[0]}")
                    course[1] = True
                    break
                i += 1
            driver.get(OSIRIS_HOME_URL)
            wait_for_element_by_class(HOME_PAGE_WAIT_ELEMENT_CLASS, driver)

            print("Reloading the sign up page...")
            driver.get(OSIRIS_EXAM_SIGN_UP_URL)
            wait_for_element_by_class("searchbar-input", driver)
    quit(driver)

    print("Driver closed. All checkups completed!")
    if (available_sign_ups != ""):
        print(f"Found courses available for sign up:\n\t{available_sign_ups}")
        send_email(available_sign_ups)
    else:
        print("No open courses found!")
        send_email("LB_TEST")
    
    save_adjusted_courses(adjusted_course_list, course_data)

    return True

def run_script(add_courses, check_resits):
    print("Starting script...")
    print(f"Add courses: {add_courses}")
    if (add_courses):
        get_and_save_courses_to_csv()
    try:
        password = creds.cred_pass
    except:
        password = get_password()

    driver = create_webdriver()
    print(f"Driver created successfully: {driver if (driver == False) else True}")
    if (not driver): was_success = False
    else: 
        was_success = login_and_get_courses(driver, password, check_resits)
        if (not was_success): quit(driver)
        print(f"Login and search for courses completed successfully: {was_success}")
    print(f"Cycle completed successfully: {was_success}")
    print("Script ended without error...")

parser = argparse.ArgumentParser(description='Process some bools')
parser.add_argument("--add_courses", nargs="?", type=bool, default=False, const=True)
parser.add_argument("--check_resits", nargs="?", type=bool, default=False, const=True)
args = parser.parse_args()
run_script(args.add_courses, args.check_resits)