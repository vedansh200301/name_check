import json
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException, NoSuchElementException

from .config import ELEMENTS, DEFAULT_TIMEOUT
from .selenium_utils import _click_element, _wait_for_element_presence, _save_screenshot_on_error

# Initialize logger for this module
logger = logging.getLogger(__name__)

def click_tab(driver, tab_locator, tab_name):
    """Clicks a tab using robust utility function."""
    try:
        logger.info(f"[SCRAPE] Attempting to click tab: {tab_name}")
        _click_element(driver, logger, tab_locator)
        logger.info(f"[SCRAPE] Clicked tab: {tab_name}")
    except (TimeoutException, ElementClickInterceptedException, NoSuchElementException) as e:
        logger.warning(f"[SCRAPE] Tab '{tab_name}' not found or not clickable: {e}")
        _save_screenshot_on_error(driver, logger, f"tab_click_failed_{tab_name}")
        raise # Re-raise to be caught by scrape_all_tabs for proper skipping

def scrape_table(driver, table_locator, tab_name):
    """Scrapes data from a table using robust utility function."""
    logger.info(f"[SCRAPE] Waiting for table '{table_locator[1]}' in tab: {tab_name}")
    try:
        _wait_for_element_presence(driver, logger, table_locator)
        table = driver.find_element(*table_locator)
        rows = table.find_elements(By.TAG_NAME, "tr")
        data = []
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            data.append([cell.text for cell in cells])
        logger.info(f"[SCRAPE] Scraped {len(data)} rows from table '{table_locator[1]}' in tab: {tab_name}")
        return data
    except (TimeoutException, NoSuchElementException) as e:
        logger.warning(f"[SCRAPE] Table '{table_locator[1]}' not found in tab '{tab_name}': {e}")
        _save_screenshot_on_error(driver, logger, f"table_scrape_failed_{tab_name}")
        raise # Re-raise to be caught by scrape_all_tabs for proper skipping

def scrape_all_tabs(driver, output_json_path="scraped_results.json"):
    tab_mapping = {
        "error": (ELEMENTS["ERROR_TAB"], ELEMENTS["ERROR_TABLE"]),
        "name_similarity": (ELEMENTS["NAME_SIMILARITY_TAB"], ELEMENTS["NAME_SIMILARITY_TABLE"]),
        "trademark": (ELEMENTS["TRADEMARK_TAB"], ELEMENTS["TRADEMARK_TABLE"])
    }
    result = {}
    for key, (tab_locator, table_locator) in tab_mapping.items():
        tab_name = key.replace('_', ' ').title()
        try:
            click_tab(driver, tab_locator, tab_name)
            data = scrape_table(driver, table_locator, tab_name)
            result[key] = data
        except (TimeoutException, NoSuchElementException, ElementClickInterceptedException): # Catch exceptions from robust helpers
            logger.warning(f"[SCRAPE] Skipping {tab_name} tab due to previous error.")
            result[key] = None
            continue # Continue to next tab even if one fails
    
    if output_json_path is not None:
        try:
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"[SCRAPE] All tab data saved to {output_json_path}")
        except Exception as e:
            logger.error(f"[SCRAPE] Error saving scraped data to JSON file: {e}")
    
    return result