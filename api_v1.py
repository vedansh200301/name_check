from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import logging
import time
# import os # No longer needed

# Import browser and automation setup
import browser_setup
from scrape_tabs import scrape_all_tabs

# Import high-level automation functions from main.py
from main import (
    click_okay_button, select_company_type, select_company_class, select_company_category,
    select_company_subcategory, open_nic_code_dialog, select_nic_codes_dynamic, enter_company_name,
    handle_name_check_and_submit, load_config
)

# Import specific exceptions to handle them gracefully
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException
)
from selenium_utils import AutomationError, VerificationStepFailed

# Initialize logging
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Company Name Check API",
    description="An API to automate company name availability checks on the MCA portal.",
    docs_url="/docs",
    openapi_prefix="/name-check"
)

# Load base configuration once at startup
BASE_CONFIG = load_config()

# Define the request model - NOW ONLY CONTAINS company_name
class NameCheckRequest(BaseModel):
    company_name: str

# Define the standard success and error response models for documentation
class SuccessResponse(BaseModel):
    success: bool = True
    data: Dict[str, Any]

class ErrorResponse(BaseModel):
    success: bool = False
    data: None = None
    error: str

@app.post("/check_name", responses={200: {"model": SuccessResponse}})
def check_name(request: NameCheckRequest):
    """
    Runs the full automation to check company name availability on the MCA portal.

    - **Launches a browser** and automates the form-filling process.
    - **Scrapes the results** and returns them in a JSON format.
    """
    # --- Step 1 (was 2): Prepare configuration and start automation ---
    config = BASE_CONFIG.copy()
    config["meta"] = config["meta"].copy()
    config["meta"]["company_name"] = request.company_name
    # The nic_code is now taken directly from the loaded base config

    driver = None
    try:
        logger.info(f"[API] Initializing browser for: '{request.company_name}'")
        driver = browser_setup.initialize_browser(config)

        # Execute the automation steps
        click_okay_button(driver)
        select_company_type(driver)
        select_company_class(driver)
        select_company_category(driver)
        select_company_subcategory(driver)
        open_nic_code_dialog(driver)
        select_nic_codes_dynamic(driver, config['meta']['nic_code'])
        enter_company_name(driver, config['meta']['company_name'])
        handle_name_check_and_submit(driver)

        time.sleep(3)  # Wait for results to load

        # Scrape the data from the result tabs
        result = scrape_all_tabs(driver, output_json_path=None)
        
        logger.info(f"[API] Successfully completed automation for: '{request.company_name}'")
        return {"success": True, "data": result}

    # --- Step 3: Comprehensive Error Handling ---
    except (AutomationError, VerificationStepFailed) as e:
        logger.error(f"[API] A defined automation step failed: {e}")
        return {"success": False, "data": None, "error": f"Automation process failed at a critical step: {e}"}
    
    except TimeoutException:
        logger.error("[API] A step timed out waiting for an element. The website is likely too slow or unresponsive.")
        return {"success": False, "data": None, "error": "A required element on the page did not load in time. The website may be experiencing high load or is unresponsive."}

    except NoSuchElementException:
        logger.error("[API] A required element could not be found. The website layout may have changed.")
        return {"success": False, "data": None, "error": "Automation failed because a required element could not be found. The website's structure may have been updated."}

    except ElementNotInteractableException:
        logger.error("[API] An element was found but could not be interacted with (e.g., obscured by an overlay).")
        return {"success": False, "data": None, "error": "Automation failed because an element was blocked by another element on the page (like a pop-up or loading spinner)."}

    except Exception as e:
        # Generic catch-all for any other unexpected errors
        logger.exception(f"[API] An unexpected error occurred during automation: {e}. Site might be slow or unresponsive.")
        # Check for browser crash error text
        if "Browse context has been discarded" in str(e).lower():
            return {"success": False, "data": None, "error": "A critical error occurred with the automation browser. Please try again."}
        return {"success": False, "data": None, "error": f"An unexpected error occurred: {e}. Site might be slow or unresponsive."}

    finally:
        # --- Step 4: Cleanup ---
        if driver:
            driver.quit()
            logger.info("[API] Browser session closed.")