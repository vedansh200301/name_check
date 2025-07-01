import time
import os
import requests
import logging
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementNotInteractableException,
    NoSuchElementException,
    NoAlertPresentException,
)
from .config import ELEMENTS, TRUECAPTCHA_USER, TRUECAPTCHA_KEY, OTP_SERVER_URL, DEFAULT_TIMEOUT, DEFAULT_RETRIES

# --- Custom Exceptions ---
class AutomationError(Exception):
    """Base exception class for this automation library."""
    pass

class VerificationStepFailed(AutomationError):
    """Raised when a multi-step verification fails after all retries."""
    pass

# --- Helper Functions ---
def _save_screenshot_on_error(driver: WebDriver, logger: logging.Logger, step_name: str):
    error_screenshot_dir = "Error Screenshots"
    os.makedirs(error_screenshot_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = os.path.join(error_screenshot_dir, f"error_{step_name}_{timestamp}.png")
    try:
        driver.save_screenshot(filename)
        logger.error(f"Saved error screenshot to: {filename}")
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")

def _wait_for_page_to_load(driver: WebDriver, logger: logging.Logger, guard_locator: tuple = None, timeout: int = DEFAULT_TIMEOUT):
    try:
        WebDriverWait(driver, timeout).until(
            lambda driver_instance: driver_instance.execute_script("return document.readyState") == 'complete'
        )
    except TimeoutException:
        logger.error(f"Synchronization failed: Page did not reach readyState 'complete' within {timeout}s.")
        _save_screenshot_on_error(driver, logger, "page_load_timeout")
        raise
    if guard_locator:
        try:
            WebDriverWait(driver, timeout).until(
                EC.visibility_of_element_located(guard_locator)
            )
        except TimeoutException:
            logger.error(f"Synchronization failed: Guard element {guard_locator} not visible within {timeout}s.")
            _save_screenshot_on_error(driver, logger, f"guard_element_not_visible_{guard_locator[1]}")
            raise

def _wait_for_element_clickable(driver: WebDriver, logger: logging.Logger, locator: tuple, timeout: int = DEFAULT_TIMEOUT):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(locator)
        )
        return element
    except TimeoutException:
        logger.error(f"Element {locator} did not become clickable within {timeout}s.")
        _save_screenshot_on_error(driver, logger, f"element_not_clickable_{locator[1]}")
        raise

def _wait_for_element_presence(driver: WebDriver, logger: logging.Logger, locator: tuple, timeout: int = DEFAULT_TIMEOUT):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return element
    except TimeoutException:
        logger.error(f"Element {locator} did not become present within {timeout}s.")
        _save_screenshot_on_error(driver, logger, f"element_not_present_{locator[1]}")
        raise

def _send_text(driver: WebDriver, logger: logging.Logger, locator: tuple, keys: str, clear_first: bool = True, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES):
    # Debug logging
    logger.info(f"_send_text called with locator: {locator}, keys length: {len(keys) if keys else 'None/Empty'}")
    if not keys:
        logger.error(f"Empty or None keys passed to _send_text for locator: {locator}")
        return
    
    for attempt in range(retries):
        try:
            element = _wait_for_element_clickable(driver, logger, locator, timeout)
            
            # Ensure element is focused
            element.click()
            time.sleep(0.5)  # Small delay to ensure focus
            
            if clear_first:
                element.clear()
                logger.debug(f"Cleared element for locator: {locator}")
            
            element.send_keys(keys)
            logger.info(f"Sent keys to element {locator} (length: {len(keys)})")
            
            # Verify the text was actually entered
            entered_value = element.get_attribute('value')
            logger.info(f"Verification: Element value after send_keys: '{entered_value}' (expected length: {len(keys)})")
            
            # If text wasn't entered properly, try JavaScript approach
            if entered_value != keys:
                logger.warning(f"Text verification failed. Expected: '{keys}', Got: '{entered_value}'. Trying JavaScript approach.")
                driver.execute_script("arguments[0].value = arguments[1];", element, keys)
                driver.execute_script("arguments[0].dispatchEvent(new Event('input', { 'bubbles': true }));", element)
                driver.execute_script("arguments[0].dispatchEvent(new Event('change', { 'bubbles': true }));", element)
                
                # Verify again
                entered_value_js = element.get_attribute('value')
                logger.info(f"After JavaScript: Element value is now: '{entered_value_js}'")
            
            return
        except StaleElementReferenceException:
            logger.warning(f"StaleElementReferenceException for {locator}, retrying... (Attempt {attempt + 1}/{retries})")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error sending text to {locator} on attempt {attempt + 1}: {e}")
            _save_screenshot_on_error(driver, logger, f"send_text_error_{locator[1]}_attempt_{attempt+1}")
            raise ElementNotInteractableException(f"Failed to send text to {locator} after {retries} retries.") # Re-raise final exception
    _save_screenshot_on_error(driver, logger, f"send_text_failure_final_{locator[1]}")
    raise ElementNotInteractableException(f"Failed to send text to {locator} after {retries} retries.")

def _click_element(driver: WebDriver, logger: logging.Logger, locator: tuple, guard_locator: tuple = None, timeout: int = DEFAULT_TIMEOUT, retries: int = DEFAULT_RETRIES):
    _wait_for_page_to_load(driver, logger, guard_locator=guard_locator, timeout=timeout)
    
    for attempt in range(retries):
        try:
            element = _wait_for_element_clickable(driver, logger, locator, timeout)
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)
            try:
                element.click()
            except ElementNotInteractableException:
                logger.warning(f"ElementNotInteractableException for {locator}, attempting JS click... (Attempt {attempt + 1}/{retries})")
                driver.execute_script("arguments[0].click();", element)
            return
        except StaleElementReferenceException:
            logger.warning(f"StaleElementReferenceException for {locator}, retrying... (Attempt {attempt + 1}/{retries})")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error clicking {locator} on attempt {attempt + 1}: {e}")
            _save_screenshot_on_error(driver, logger, f"click_error_{locator[1]}_attempt_{attempt+1}")
            raise ElementNotInteractableException(f"Failed to click {locator} after {retries} retries.") # Re-raise final exception
    _save_screenshot_on_error(driver, logger, f"click_failure_final_{locator[1]}")
    raise ElementNotInteractableException(f"Failed to click {locator} after {retries} retries.")

def _force_click_js(driver: WebDriver, logger: logging.Logger, locator: tuple, timeout: int = DEFAULT_TIMEOUT):
    try:
        element = _wait_for_element_presence(driver, logger, locator, timeout)
        driver.execute_script("arguments[0].click();", element)
    except TimeoutException:
        logger.error(f"Element {locator} not present for JS click within {timeout}s.")
        _save_screenshot_on_error(driver, logger, f"js_click_timeout_{locator[1]}")
        raise
    except Exception as e:
        logger.error(f"Error performing JS click on {locator}: {e}")
        _save_screenshot_on_error(driver, logger, f"js_click_error_{locator[1]}")
        raise

def _handle_alert(driver: WebDriver, logger: logging.Logger, timeout: int = DEFAULT_TIMEOUT) -> bool:
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
        logger.info("Alert detected and accepted successfully.")
        return True
    except (TimeoutException, NoAlertPresentException):
        logger.info("No alert detected within the timeout period.")
        return False
    except Exception as e:
        logger.error(f"Error handling alert: {e}")
        _save_screenshot_on_error(driver, logger, "handle_alert_error")
        raise

def _solve_captcha_with_api(driver: WebDriver, logger: logging.Logger):
    logger.info("Attempting to solve CAPTCHA via API...")
    if not TRUECAPTCHA_USER or not TRUECAPTCHA_KEY:
        logger.error("TrueCaptcha credentials are missing. Please check your .env file or config.py.")
        raise AutomationError("TrueCaptcha credentials missing.")

    try:
        captcha_element = _wait_for_element_presence(driver, logger, ELEMENTS["LOGIN_CAPTCHA_IMAGE"])
        encoded_string = captcha_element.screenshot_as_base64
        response = requests.post(
            'https://api.apitruecaptcha.org/one/gettext',
            json={'userid': TRUECAPTCHA_USER, 'apikey': TRUECAPTCHA_KEY, 'data': encoded_string},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        if 'result' in result:
            captcha_text = result['result']
            logger.info(f"CAPTCHA API returned: {captcha_text}")
            _send_text(driver, logger, ELEMENTS["LOGIN_CAPTCHA_INPUT"], captcha_text)
            return True
        else:
            logger.error(f"Failed to get CAPTCHA result from API: {result}")
            return False
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Network or API error during captcha verification: {req_err}")
        _save_screenshot_on_error(driver, logger, "captcha_api_network_error")
        return False
    except Exception as e:
        logger.error(f"General error in solving and entering captcha: {e}")
        _save_screenshot_on_error(driver, logger, "captcha_solve_general_error")
        return False

def _poll_for_otp(logger: logging.Logger, job_id: str, otp_type: str, timeout: int = 300, poll_interval: int = 3) -> str:
    start_time = time.time()
    logger.info(f"Polling for {otp_type} with job_id: {job_id}...")
    while time.time() - start_time < timeout:
        try:
            url = f"{OTP_SERVER_URL}/get-otp?job_id={job_id}&type={otp_type}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200 and response.json().get("data", {}).get("otp"):
                otp_value = response.json()["data"]["otp"]
                logger.info(f"OTP '{otp_value}' received for type '{otp_type}'!")
                return otp_value
            else:
                logger.debug(f"OTP not yet available or invalid response: {response.json()}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not connect to OTP server or network error: {e}. Retrying...")
        time.sleep(poll_interval)
    logger.error(f"Timed out waiting for {otp_type} from local server after {timeout} seconds.")
    raise TimeoutException(f"Timed out waiting for {otp_type} from local server.")

def _execute_robust_step(driver: WebDriver, logger: logging.Logger, step_name: str, action_callable: callable, submit_callable: callable = None, success_condition: callable = None, failure_condition: callable = None, recovery_callable: callable = None, **kwargs):
    max_retries = kwargs.get('max_retries', DEFAULT_RETRIES)
    wait_timeout = kwargs.get('wait_timeout', DEFAULT_TIMEOUT)
    
    for attempt in range(max_retries):
        logger.info(f"--- Starting {step_name}: Attempt {attempt + 1}/{max_retries} ---")
        
        try:
            if attempt > 0 and recovery_callable:
                logger.info(f"Attempting recovery for {step_name}...")
                recovery_callable()
                time.sleep(1) # Small pause after recovery
            
            action_callable()
            
            if submit_callable:
                logger.info(f"Executing submit action for {step_name}...")
                submit_callable()
                time.sleep(0.5) # Small pause after submit

            if success_condition:
                WebDriverWait(driver, wait_timeout).until(success_condition)
                logger.info(f"SUCCESS: {step_name} completed successfully on attempt {attempt + 1}.")
                return
            else:
                # If no success condition, assume action + submit are sufficient
                logger.info(f"SUCCESS: {step_name} action/submit completed on attempt {attempt + 1} (no specific success condition).")
                return

        except TimeoutException as e:
            if failure_condition:
                try:
                    WebDriverWait(driver, 2).until(failure_condition)
                    logger.warning(f"{step_name} failed due to expected failure condition on attempt {attempt + 1}. Retrying...")
                except TimeoutException:
                    logger.error(f"{step_name} failed: Page in unexpected state after timeout (no failure condition met).")
                    _save_screenshot_on_error(driver, logger, f"{step_name}_unexpected_state_timeout_{attempt+1}")
                    if attempt == max_retries - 1: raise VerificationStepFailed(f"{step_name} failed: Page in unexpected state after max retries.") from e
            else:
                logger.error(f"{step_name} failed: Timeout without specific failure condition. {e}")
                _save_screenshot_on_error(driver, logger, f"{step_name}_timeout_no_failure_cond_{attempt+1}")
                if attempt == max_retries - 1: raise VerificationStepFailed(f"{step_name} timed out after max retries.") from e
        except Exception as e:
            logger.error(f"Caught unexpected exception during {step_name} attempt {attempt + 1}: {type(e).__name__} - {e}")
            _save_screenshot_on_error(driver, logger, f"{step_name}_unexpected_error_{attempt+1}")
            if attempt == max_retries - 1: raise VerificationStepFailed(f"{step_name} failed due to unexpected error after max retries.") from e
        
        time.sleep(2) # Wait before next retry

    logger.critical(f"FINAL FAILURE: {step_name} failed after {max_retries} attempts.")
    _save_screenshot_on_error(driver, logger, f"{step_name}_final_failure")
    raise VerificationStepFailed(f"{step_name} could not be completed after {max_retries} attempts.")