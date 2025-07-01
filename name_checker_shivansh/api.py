from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Any, Dict
import logging
import os
import json
import browser_setup
from scrape_tabs import scrape_all_tabs
import time

# Import centralized logging setup
from logging_setup import setup_logging
# Initialize logging for API mode
setup_logging(api_mode=True)
logger = logging.getLogger(__name__)

# Import high-level automation functions from main.py
from main import (
    click_okay_button, select_company_type, select_company_class, select_company_category,
    select_company_subcategory, open_nic_code_dialog, select_nic_codes_dynamic, enter_company_name,
    handle_name_check_and_submit, load_config # load_config is needed to get base config
)
from selenium_utils import AutomationError, VerificationStepFailed # Import custom exceptions

app = FastAPI(title="Company Name Check API", docs_url="/docs")

# Load base config once at startup
BASE_CONFIG = load_config()

class NameCheckRequest(BaseModel):
    company_name: str

@app.post("/check_name")
def check_name(request: NameCheckRequest) -> Dict[str, Any]:
    """
    Run the name check automation for the provided company name and return the scraped results.
    """
    config = BASE_CONFIG.copy() # Start with a copy of the base config
    
    # Ensure 'meta' key exists and is mutable
    if "meta" not in config:
        config["meta"] = {}
    config["meta"] = config["meta"].copy()
    
    # Update company name for this specific request
    config["meta"]["company_name"] = request.company_name
    
    driver = None
    try:
        logger.info(f"[API] Starting browser for company name: {request.company_name}")
        driver = browser_setup.initialize_browser(config)
        
        # --- Execute the minimal automation steps up to and including the auto-check ---
        # Pass the driver instance to each function
        click_okay_button(driver)
        select_company_type(driver)
        select_company_class(driver)
        select_company_category(driver)
        select_company_subcategory(driver)
        open_nic_code_dialog(driver)
        select_nic_codes_dynamic(driver, config['meta']['nic_code'])
        enter_company_name(driver, config['meta']['company_name'])
        handle_name_check_and_submit(driver)
        
        time.sleep(3)  # Wait for tables to load after auto-check

        # --- Scrape the tabs ---
        # Pass the driver instance to scrape_all_tabs
        result = scrape_all_tabs(driver, output_json_path=None)  # Don't write to file, just return dict
        
        return {"success": True, "data": result}
    except (AutomationError, VerificationStepFailed, Exception) as e:
        logger.exception(f"[API] Error during name check automation for '{request.company_name}': {e}")
        return {"success": False, "error": str(e)}
    finally:
        if driver:
            driver.quit()
            logger.info("[API] Browser closed after API call")