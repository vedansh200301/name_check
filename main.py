import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
import os
import time
import logging
from datetime import datetime
import browser_setup  # Import the browser setup module
from scrape_tabs import scrape_all_tabs  # Import scrape_all_tabs
from config import ELEMENTS, DEFAULT_TIMEOUT, DEFAULT_RETRIES, SPICE_FORM_URL # Import locators and defaults
from selenium_utils import ( # Import robust helper functions
    _click_element, _send_text, _wait_for_element_clickable,
    _wait_for_element_presence, _save_screenshot_on_error,
    VerificationStepFailed, AutomationError
)
from selenium.webdriver.support import expected_conditions as EC # For EC conditions in success/failure
from logging_setup import setup_logging # Import centralized logging setup
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait

# Initialize logger for this module
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from config.json file"""
    logger.info('Loading configuration from config.json')
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            logger.info('Configuration loaded successfully')
            return config
    except FileNotFoundError:
        logger.error('config.json file not found!')
        _save_screenshot_on_error(None, logger, "config_not_found") # No driver yet
        exit(1)
    except json.JSONDecodeError as e:
        logger.error(f'Invalid JSON format in config.json! {e}')
        _save_screenshot_on_error(None, logger, "config_json_error") # No driver yet
        exit(1)
    except Exception as e:
        logger.error(f'Unexpected error loading config: {str(e)}')
        _save_screenshot_on_error(None, logger, "config_load_error") # No driver yet
        exit(1)

def click_okay_button(driver):
    """Click the okay button after page load using robust utility."""
    logger.info('[FORM] Waiting for page to load and okay button to be clickable')
    start_time = time.time()
    try:
        _click_element(driver, logger, ELEMENTS["OK_BUTTON_POPUP"])
        logger.info(f'[FORM] Successfully clicked the okay button in {time.time() - start_time:.2f} seconds')
        # Wait for modal backdrop to disappear
        logger.info('[FORM] Waiting for modal backdrop to disappear')
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(EC.invisibility_of_element_located(ELEMENTS["MODAL_BACKDROP"]))
        time.sleep(2)  # Additional wait to ensure modal is fully gone
        logger.info('[FORM] Modal backdrop disappeared successfully')
    except Exception as e:
        logger.error(f'[FORM] Error clicking okay button: {str(e)}')
        _save_screenshot_on_error(driver, logger, "click_okay_button_failure")
        raise

def _select_dropdown_option(driver, logger, dropdown_locator, option_value, option_text, step_name):
    """Helper to select option from a dropdown robustly."""
    try:
        logger.info(f'Waiting for {step_name} dropdown to be present and clickable')
        dropdown_element = _wait_for_element_clickable(driver, logger, dropdown_locator)
        
        # Try to remove any remaining modal backdrop using JavaScript
        try:
            driver.execute_script("""
                var elements = document.getElementsByClassName('modal-backdrop');
                for(var i=0; i<elements.length; i++){
                    elements[i].parentNode.removeChild(elements[i]);
                }
            """)
            logger.info('Removed any remaining modal backdrop')
        except Exception as e:
            logger.debug(f'No modal backdrop to remove or error during removal: {e}')
        
        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_element)
        time.sleep(1) # Wait for scroll to complete
        
        dropdown = Select(dropdown_element)
        logger.info(f'Selecting "{option_text}" from {step_name} dropdown')
        
        try:
            dropdown.select_by_value(option_value)
        except NoSuchElementException: # Value not found, try text
            try:
                dropdown.select_by_visible_text(option_text)
            except NoSuchElementException: # Text not found, try JS
                driver.execute_script(
                    "arguments[0].value = arguments[1];",
                    dropdown_element,
                    option_value
                )
                # Trigger change event to ensure the selection is registered
                driver.execute_script(
                    "arguments[0].dispatchEvent(new Event('change', { 'bubbles': true }));",
                    dropdown_element
                )
        
        logger.info(f'Successfully selected {step_name}')
        time.sleep(1) # Wait for selection to take effect
        
    except Exception as e:
        logger.error(f'Error selecting {step_name}: {str(e)}')
        _save_screenshot_on_error(driver, logger, f"select_{step_name.replace(' ', '_')}_failure")
        raise

def select_company_type(driver):
    """Select 'New Company (Others)' from the dropdown."""
    _select_dropdown_option(driver, logger, ELEMENTS["COMPANY_TYPE_DROPDOWN"], "New Company (Others)", "New Company (Others)", "company type")

def select_company_class(driver):
    """Select 'Private' from the company class dropdown."""
    _select_dropdown_option(driver, logger, ELEMENTS["COMPANY_CLASS_DROPDOWN"], "Private", "Private", "company class")

def select_company_category(driver):
    """Select 'Company limited by shares' from the company category dropdown."""
    _select_dropdown_option(driver, logger, ELEMENTS["COMPANY_CATEGORY_DROPDOWN"], "Company limited by shares", "Company limited by shares", "company category")

def select_company_subcategory(driver):
    """Select 'Non-government company' from the company sub-category dropdown."""
    _select_dropdown_option(driver, logger, ELEMENTS["COMPANY_SUB_CATEGORY_DROPDOWN"], "Non-government company", "Non-government company", "company sub-category")

def open_nic_code_dialog(driver):
    """Click the NIC button to open the NIC code selection dialog using robust utility."""
    logger.info('Opening NIC code selection dialog.')
    try:
        _click_element(driver, logger, ELEMENTS["NIC_BUTTON"])
        time.sleep(1)
    except Exception as e:
        logger.error(f'Error opening NIC code dialog: {str(e)}')
        _save_screenshot_on_error(driver, logger, "open_nic_dialog_failure")
        raise

def select_nic_codes_dynamic(driver, nic_codes_str):
    """
    Select multiple NIC codes by searching and checking each one, then click Add once at the end.
    Uses robust utilities.
    """
    nic_codes = [code.strip() for code in nic_codes_str.split(',') if code.strip()]
    
    for idx, code in enumerate(nic_codes):
        logger.info(f'Starting NIC code selection for: {code}')
        try:
            _send_text(driver, logger, ELEMENTS["NIC_SEARCH_BAR"], code, clear_first=True)
            time.sleep(1.5) # Wait for table to update

            # Select dropdown value based on code index
            dropdown_element = _wait_for_element_clickable(driver, logger, ELEMENTS["NIC_PAGE_SIZE_DROPDOWN"])
            select = Select(dropdown_element)
            
            page_size_value = '100' # Default
            if idx == 0:
                page_size_value = '100'
            elif idx == 1:
                page_size_value = '10'
            elif idx == 2:
                page_size_value = '100'
            
            logger.info(f'Selecting "{page_size_value}" in page size dropdown for NIC code {code}')
            select.select_by_value(page_size_value)
            time.sleep(0.5)

            checkbox_locator = (By.XPATH, ELEMENTS["NIC_CHECKBOX_XPATH"].format(code))
            checkbox = _wait_for_element_clickable(driver, logger, checkbox_locator)
            
            if not checkbox.is_selected():
                logger.info(f'Clicking checkbox for NIC code {code}')
                _click_element(driver, logger, checkbox_locator)
            else:
                logger.info(f'Checkbox for NIC code {code} already selected')
            time.sleep(0.5)
        except Exception as e:
            logger.error(f'Error selecting NIC code {code}: {str(e)}')
            _save_screenshot_on_error(driver, logger, f"nic_code_selection_failure_{code}")
            raise # Re-raise to stop if a NIC code fails
    
    # After all codes are checked, click the Add button
    logger.info('Clicking Add button after selecting all NIC codes')
    try:
        _click_element(driver, logger, ELEMENTS["NIC_ADD_BUTTON"])
        time.sleep(1)
    except Exception as e:
        logger.error(f'Error clicking Add button for NIC codes: {str(e)}')
        _save_screenshot_on_error(driver, logger, "nic_add_button_failure")
        raise

def format_company_name(name):
    """Format company name according to requirements"""
    logger.debug(f'[FORM] Formatting company name: {name}')
    name = name.upper()
    logger.debug(f'[FORM] Name converted to uppercase: {name}')
    
    if "PRIVATE LIMITED" not in name.upper():
        name = f"{name} PRIVATE LIMITED"
        logger.debug(f'[FORM] Added "PRIVATE LIMITED" suffix: {name}')
    else:
        logger.debug(f'[FORM] "PRIVATE LIMITED" already exists in name, no change needed')
    return name

def enter_company_name(driver, company_name):
    """Enter the formatted company name in the input field using robust utility."""
    logger.info('Waiting for company name input field to be present')
    formatted_name = format_company_name(company_name)
    logger.info(f'Formatted company name: {formatted_name}')
    
    try:
        _send_text(driver, logger, ELEMENTS["COMPANY_NAME_INPUT"], formatted_name)
        
        # Optional: Verify the entered text (this is a good practice)
        entered_value = driver.find_element(*ELEMENTS["COMPANY_NAME_INPUT"]).get_attribute('value')
        if entered_value != formatted_name:
            logger.warning(f'Text verification failed for company name. Expected: {formatted_name}, Got: {entered_value}. Attempting JS input.')
            driver.execute_script(
                "arguments[0].value = arguments[1];",
                driver.find_element(*ELEMENTS["COMPANY_NAME_INPUT"]),
                formatted_name
            )
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', { 'bubbles': true }));",
                driver.find_element(*ELEMENTS["COMPANY_NAME_INPUT"])
            )
        logger.info('Successfully entered company name')
        time.sleep(1)
    except Exception as e:
        logger.error(f'Error entering company name: {str(e)}')
        _save_screenshot_on_error(driver, logger, "enter_company_name_failure")
        raise

def handle_name_check_and_submit(driver):
    """Handle the auto-check process only (do not click submit) using robust utility."""
    logger.info('Starting name auto-check process')
    try:
        _click_element(driver, logger, ELEMENTS["AUTO_CHECK_BUTTON"])
        time.sleep(3) # Wait for auto-check to complete
        logger.info('Auto-check completed (submit not clicked, as requested)')
    except Exception as e:
        logger.error(f'Error in name check process: {str(e)}')
        _save_screenshot_on_error(driver, logger, "name_auto_check_failure")
        raise

def click_proceed_incorporation(driver):
    """Click the 'Proceed for Incorporation' radio button using robust utility."""
    logger.info('Clicking Proceed for Incorporation radio button')
    try:
        _click_element(driver, logger, ELEMENTS["PROCEED_INCORPORATION_RADIO"])
        # Verify the radio button is selected
        is_selected = driver.find_element(*ELEMENTS["PROCEED_INCORPORATION_RADIO"]).is_selected()
        if not is_selected:
            raise AutomationError("Failed to select the radio button")
        logger.info('Successfully selected Proceed for Incorporation option')
        time.sleep(1)
    except Exception as e:
        logger.error(f'Error selecting Proceed for Incorporation option: {str(e)}')
        _save_screenshot_on_error(driver, logger, "proceed_incorporation_failure")
        raise

def click_continue_button(driver):
    """Click the Continue button to complete the first path using robust utility."""
    logger.info('Clicking Continue button')
    try:
        _click_element(driver, logger, ELEMENTS["CONTINUE_BUTTON"])
        logger.info('Successfully clicked Continue button')
        logger.info('First path completed successfully')
        time.sleep(2)
    except Exception as e:
        logger.error(f'Error clicking Continue button: {str(e)}')
        _save_screenshot_on_error(driver, logger, "continue_button_failure")
        raise

def main():
    # Setup logging
    log_file = setup_logging()
    logger.info('Starting automation script')
    driver = None
    
    try:
        # Load configuration
        logger.info('Loading configuration')
        config = load_config()
        
        # Initialize browser using the browser_setup module
        logger.info('Initializing browser')
        driver = browser_setup.initialize_browser(config)
        
        logger.info('Browser initialized successfully')
        
        # Log the start of form automation
        logger.info('Starting Part A of the form')
        
        # Part A of the form - Calling high-level functions
        click_okay_button(driver)
        select_company_type(driver)
        select_company_class(driver)
        select_company_category(driver)
        select_company_subcategory(driver)
        open_nic_code_dialog(driver)
        select_nic_codes_dynamic(driver, config['meta']['nic_code'])
        enter_company_name(driver, config['meta']['company_name'])
        handle_name_check_and_submit(driver)
        
        # Wait for tables to load after auto-check
        time.sleep(3)
        
        # Scrape all tabs after auto-check
        scrape_all_tabs(driver)
        
        print("\nAutomation stopped after auto-check as requested.")
        print("Press Enter to close the browser...")
        input()
        
    except (AutomationError, VerificationStepFailed, Exception) as e:
        logger.error(f'Error during automation: {str(e)}')
        # Take screenshot on error if driver is available and error was not from _save_screenshot_on_error itself
        if driver:
            _save_screenshot_on_error(driver, logger, "automation_script_failure")
        print("\n[ERROR] Automation failed. Browser will remain open for debugging. Press Enter to close the browser when done...")
        input()
    finally:
        if driver:
            driver.quit()
            logger.info('Browser closed')

if __name__ == "__main__":
    main()