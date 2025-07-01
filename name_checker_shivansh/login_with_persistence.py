import os
import time
import base64
import json
import requests
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

from .config import (
    LOGIN_URL, APPLICATION_HISTORY_URL, MCA_HOME_URL, ELEMENTS,
    TRUECAPTCHA_USER, TRUECAPTCHA_KEY, DEFAULT_TIMEOUT, DEFAULT_RETRIES
)
from .selenium_utils import (
    _save_screenshot_on_error, _wait_for_element_clickable, _send_text,
    _click_element, _force_click_js, _solve_captcha_with_api,
    AutomationError, VerificationStepFailed, _wait_for_element_presence
)
from .logging_setup import setup_logging # Import the setup_logging function

# Initialize logger for this module
# This ensures it uses the centralized logging configuration
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def wait_for_dom_ready(driver: webdriver.Firefox, timeout: int = DEFAULT_TIMEOUT):
    """Waits for the page's document.readyState to be 'complete'."""
    logger.info("Waiting for page DOM to be ready...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        logger.info("Page DOM is ready.")
        return True
    except TimeoutException:
        current_state = "unknown"
        try:
            current_state = driver.execute_script("return document.readyState")
        except Exception as e:
            logger.error(f"Could not get document.readyState from browser: {e}")
        logger.error(f"Timeout waiting for page DOM to be ready. Current state: '{current_state}'")
        _save_screenshot_on_error(driver, logger, "dom_not_ready_timeout")
        return False

def handle_captcha_on_page(driver: webdriver.Firefox, max_attempts: int = DEFAULT_RETRIES):
    """Handle captcha on the website with retry logic"""
    logger.info("Handling CAPTCHA on page using selenium_utils...")
    attempt = 0

    while attempt < max_attempts:
        logger.info(f"CAPTCHA attempt {attempt + 1} of {max_attempts}")
        try:
            # Solve CAPTCHA using the utility function
            captcha_solved_successfully = _solve_captcha_with_api(driver, logger)

            if captcha_solved_successfully:
                # Click submit button after entering CAPTCHA
                _click_element(driver, logger, ELEMENTS["LOGIN_FORM_SUBMIT_BUTTON"])
                logger.info("Clicked submit after entering CAPTCHA.")
                wait_for_dom_ready(driver, timeout=7) # Wait for page to potentially reload or show error

                try:
                    # Check for immediate 'incorrect captcha' error message
                    error_message_element = _wait_for_element_presence(driver, logger, ELEMENTS["LOGIN_CAPTCHA_ERROR_MESSAGE_ID"], timeout=2)
                    if error_message_element.is_displayed() and "The captcha entered is incorrect" in error_message_element.text:
                        logger.warning("CAPTCHA incorrect. Refreshing...")
                        _send_text(driver, logger, ELEMENTS["LOGIN_CAPTCHA_INPUT"], "", clear_first=True) # Clear input
                        _click_element(driver, logger, ELEMENTS["LOGIN_CAPTCHA_REFRESH_BUTTON"])
                        time.sleep(2)
                        continue
                    else:
                        logger.info("CAPTCHA submitted, no immediate 'incorrect captcha' error found.")
                        return True
                except TimeoutException: # Error message element not found, likely moved past
                    logger.info("No CAPTCHA error message element found. Assuming CAPTCHA was accepted or page changed.")
                    return True
            else:
                logger.warning("CAPTCHA API did not return text or failed to solve. Refreshing CAPTCHA on page.")
                _click_element(driver, logger, ELEMENTS["LOGIN_CAPTCHA_REFRESH_BUTTON"])
                time.sleep(2)
                attempt += 1
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"CAPTCHA element not found or not interactable: {e}.")
            _save_screenshot_on_error(driver, logger, "captcha_elements_missing")
            # Attempt to refresh if refresh button is present
            try:
                _click_element(driver, logger, ELEMENTS["LOGIN_CAPTCHA_REFRESH_BUTTON"], timeout=3)
                time.sleep(2)
            except Exception as refresh_e:
                logger.warning(f"Could not refresh CAPTCHA after missing element: {refresh_e}")
            attempt += 1
            if attempt >= max_attempts: return False # If max attempts reached, exit
        except Exception as e:
            logger.error(f"General error in handle_captcha_on_page: {e}")
            _save_screenshot_on_error(driver, logger, f"captcha_handling_general_error_{attempt+1}")
            attempt += 1
            if attempt < max_attempts:
                try:
                    _click_element(driver, logger, ELEMENTS["LOGIN_CAPTCHA_REFRESH_BUTTON"], timeout=3)
                    time.sleep(2)
                except Exception as refresh_e:
                    logger.warning(f"Could not refresh CAPTCHA after general error: {refresh_e}")
            time.sleep(1)
    logger.error("Max CAPTCHA attempts reached without successful submission.")
    return False

def close_initial_popup_option_b(driver: webdriver.Firefox, max_close_attempts: int = DEFAULT_RETRIES):
    """
    Close the initial popup if present, using Option B (check for absence) with retries.
    Adjust XPATH as needed.
    """
    for attempt in range(max_close_attempts):
        logger.info(f"Attempting to close pop-up and verify absence (Attempt {attempt + 1} of {max_close_attempts})...")
        try:
            _click_element(driver, logger, ELEMENTS["LOGIN_POPUP_XPATH"], timeout=3) # Use utility click
            logger.info(f"Clicked pop-up element on attempt {attempt + 1}.")
            time.sleep(0.5)

            try:
                WebDriverWait(driver, 2).until_not(
                    EC.presence_of_element_located(ELEMENTS["LOGIN_POPUP_XPATH"])
                )
                logger.info("Pop-up successfully closed (element no longer present).")
                return True
            except TimeoutException:
                logger.warning(f"Pop-up element still present after click attempt {attempt + 1}.")
                if attempt < max_close_attempts - 1:
                    logger.info("Will retry closing pop-up.")
                else:
                    logger.error("Max attempts reached, pop-up still present.")
                    _save_screenshot_on_error(driver, logger, "popup_not_closed_final")
                    return False
        
        except TimeoutException:
            logger.info(f"Pop-up element not found or not clickable on attempt {attempt + 1}. Assuming pop-up is not an issue.")
            try:
                WebDriverWait(driver, 1).until_not(
                     EC.presence_of_element_located(ELEMENTS["LOGIN_POPUP_XPATH"])
                )
                logger.info("Confirmed: Pop-up element is not present.")
                return True
            except TimeoutException:
                logger.warning(f"Pop-up element (e.g. close button) was not initially clickable/found in attempt {attempt +1}, but an element matching XPath '{ELEMENTS['LOGIN_POPUP_XPATH'][1]}' is still present.")
                if attempt < max_close_attempts - 1:
                    continue
                else:
                    _save_screenshot_on_error(driver, logger, "popup_present_after_check")
                    return False
        except Exception as e:
            logger.error(f"An error occurred during pop-up close attempt {attempt + 1}: {e}")
            _save_screenshot_on_error(driver, logger, f"popup_close_error_{attempt+1}")
            if attempt < max_close_attempts - 1:
                logger.info("Will retry closing pop-up due to error.")
            else:
                logger.error("Max attempts reached due to errors, pop-up could not be closed reliably.")
                return False
    
    logger.error("Exited pop-up close attempts loop without success.")
    return False

def check_login_success_url_only(driver: webdriver.Firefox):
    """Verify if login was successful by checking URL ONLY."""
    logger.info("Checking login success (URL only)...")
    try:
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(
            lambda d: APPLICATION_HISTORY_URL in d.current_url
        )
        current_url = driver.current_url
        logger.info(f"Current URL is: {current_url}. Expected to contain: {APPLICATION_HISTORY_URL}")
        if APPLICATION_HISTORY_URL in current_url:
            logger.info("Login success confirmed by URL.")
            return True
        else:
            logger.error(f"Login failed. URL is: {current_url}, expected to contain: {APPLICATION_HISTORY_URL}")
            _save_screenshot_on_error(driver, logger, "login_url_mismatch")
            return False
    except TimeoutException:
        logger.error(f"Login verification failed: Timed out waiting for URL to contain {APPLICATION_HISTORY_URL}. Current URL: {driver.current_url}")
        _save_screenshot_on_error(driver, logger, "login_url_timeout")
        return False
    except Exception as e:
        logger.error(f"Exception during URL check for login success: {e}")
        _save_screenshot_on_error(driver, logger, "login_url_check_error")
        return False

def login_to_mca_and_verify(driver: webdriver.Firefox, config: dict):
    """Main function to login to MCA and verify."""
    logger.info("Starting MCA login process...")
    login_successful = False
    perform_form_login = True # Flag to determine if form login steps are needed

    try:
        driver.get(LOGIN_URL)
        logger.info(f"Navigated to login page: {LOGIN_URL}")
        wait_for_dom_ready(driver) # Wait for page to be ready

        # --- Check for homepage redirect ---
        current_url_after_get = driver.current_url
        logger.info(f"Current URL after initial load: {current_url_after_get}")

        if MCA_HOME_URL in current_url_after_get:
            logger.info(f"Detected landing on MCA homepage ('{MCA_HOME_URL}'). Attempting to navigate directly to Application History.")
            driver.get(APPLICATION_HISTORY_URL)
            logger.info(f"Navigated to Application History page: {APPLICATION_HISTORY_URL}")
            wait_for_dom_ready(driver) # Allow application history page to load
            perform_form_login = False # Skip form login steps
        else:
            logger.info("Not on MCA homepage. Proceeding with normal login flow.")
            perform_form_login = True

        if perform_form_login:
            # Initial popup handling removed from automation flow
            # close_initial_popup_option_b function is still available if needed
            
            try:
                # Wait for the CAPTCHA image to be visible before proceeding
                logger.info("Waiting for login page to be ready by checking for CAPTCHA image...")
                _wait_for_element_presence(driver, logger, ELEMENTS["LOGIN_CAPTCHA_IMAGE"])
                logger.info("Login page is ready. Proceeding to fill details.")

                logger.info("Attempting to fill login details...")
                
                # Debug: Log what we're trying to retrieve from config
                username = config.get("username", "")
                password = config.get("password", "")
                logger.info(f"Retrieved username from config: '{username}' (length: {len(username)})")
                logger.info(f"Retrieved password from config: {'*' * len(password) if password else 'EMPTY'} (length: {len(password)})")
                
                if not username or not password:
                    logger.error(f"Missing credentials in config! Username: {'PRESENT' if username else 'MISSING'}, Password: {'PRESENT' if password else 'MISSING'}")
                    logger.info(f"Config keys available: {list(config.keys())}")
                    _save_screenshot_on_error(driver, logger, "missing_credentials")
                    return driver, False
                
                _send_text(driver, logger, ELEMENTS["LOGIN_USER_FIELD_ID"], username)
                logger.info("Entered Login ID.")

                _send_text(driver, logger, ELEMENTS["LOGIN_PASSWORD_FIELD_ID"], password)
                logger.info("Entered Password.")
            except TimeoutException:
                logger.error("Timeout waiting for login ID or Password field. Check element IDs.")
                _save_screenshot_on_error(driver, logger, "login_fields_timeout")
                return driver, False 
            except NoSuchElementException:
                logger.error("Login ID or Password field not found. Check element IDs.")
                _save_screenshot_on_error(driver, logger, "login_fields_not_found")
                return driver, False

            if not handle_captcha_on_page(driver):
                logger.error("CAPTCHA handling failed during login.")
                # If captcha fails, login_successful remains false, proceed to final check
            else:
                logger.info("CAPTCHA handling reported success or moved past.")
        
        # --- Verify Login Success (common to both paths) ---
        wait_for_dom_ready(driver) # Give a moment for any post-submit redirect or direct navigation to fully complete
        if check_login_success_url_only(driver):
            logger.info("MCA Login Successful!")
            login_successful = True
        else:
            logger.error("MCA Login Failed based on URL check after form submission.")
            logger.info(f"Current page URL: {driver.current_url}")
            logger.info("Current page title: " + driver.title)

        logger.info("Script has finished its tasks.")

    except Exception as e:
        logger.error(f"An unexpected error occurred in the login process: {e}")
        _save_screenshot_on_error(driver, logger, "unexpected_login_error")
    finally:
        if driver:
            logger.info("Browser will remain open as per request (if not explicitly closed by calling function).")
        else:
            logger.error("Driver was not initialized, or an error occurred before initialization was complete.")
            
    return driver, login_successful

def check_login_required(driver: webdriver.Firefox, target_url: str):
    """
    Check if login is required by comparing current URL with target URL
    
    Args:
        driver: WebDriver instance
        target_url: Expected URL if already logged in
        
    Returns:
        bool: True if login is required, False otherwise
    """
    current_url = driver.current_url
    logger.info(f"Checking if login is required. Current URL: {current_url}, Target URL: {target_url}")
    
    # Check if we're already on the target page (SPICE form)
    if target_url in current_url:
        logger.info("Already on the target page, login not required.")
        return False
    
    # Check if we're on the login page
    if LOGIN_URL in current_url or "fologin.html" in current_url:
        logger.info("Login page detected, login required.")
        return True
    
    # Neither on login page nor target page - check for other indicators
    try:
        # Look for login elements that would only be present if login is required
        login_elements = driver.find_elements(By.XPATH, f"{ELEMENTS['LOGIN_PASSWORD_FIELD'][1]} | {ELEMENTS['LOGIN_BUTTON'][1]}")
        if login_elements:
            logger.info("Login elements detected on page, login required.")
            return True
    except Exception as e:
        logger.warning(f"Error checking for login elements: {e}")
    
    logger.info("Login not required (no clear indicators).")
    return False

# Main function for when this script is run directly (for testing login)
if __name__ == "__main__":
    # Setup basic logging for standalone execution
    log_file = setup_logging()
    logger.info("Running login_with_persistence.py directly.")
    
    # Load config from config.json for direct execution
    try:
        with open("config.json", "r") as f:
            app_config = json.load(f)
    except FileNotFoundError:
        logger.error("config.json not found. Cannot run login_with_persistence.py directly without it.")
        exit(1)
    
    # Initialize Firefox driver for this standalone test
    browser_options = FirefoxOptions()
    if app_config['meta'].get('firefox_profile_path') and os.path.exists(app_config['meta']['firefox_profile_path']):
        browser_options.add_argument("-profile")
        browser_options.add_argument(app_config['meta']['firefox_profile_path'])
        logger.info(f"Using Firefox profile: {app_config['meta']['firefox_profile_path']}")
    else:
        logger.info("No valid Firefox profile path provided or found. Using default profile.")

    # Using geckodriver from PATH or a specified location
    geckodriver_path = os.getenv("GECKODRIVER_PATH", "geckodriver") # Assuming GECKODRIVER_PATH can be set in .env or default to 'geckodriver'
    if not os.path.exists(geckodriver_path) and geckodriver_path != "geckodriver":
        logger.error(f"Geckodriver path '{geckodriver_path}' is invalid or file not found. Please set GECKODRIVER_PATH in .env.")
        exit(1)
    
    service = FirefoxService(executable_path=geckodriver_path)
    test_driver = webdriver.Firefox(service=service, options=browser_options)
    test_driver.maximize_window()
    logger.info("Test Firefox browser initialized.")

    active_driver, success_status = login_to_mca_and_verify(test_driver, app_config)
    logger.info(f"Final Login Status: {'Successful' if success_status else 'Failed'}")
    
    # Keep browser open for inspection if login failed or successful for testing
    if active_driver:
        logger.info("Python script execution finished. The browser window should remain open for inspection.")
        # input("Press Enter to close the browser...") # Uncomment to manually close
        # active_driver.quit() # Uncomment to automatically quit
    else:
        logger.info("Driver was not returned, likely due to an initialization error.")