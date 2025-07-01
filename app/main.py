import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict
import logging
import time

# Add project root to allow imports from sibling directories
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .models import NameCheckResult, NameCheckPayload
from .cache import RedisCache
from .analyser import ConflictAnalyser

# Import the automation functions directly
from name_checker_shivansh import browser_setup
from name_checker_shivansh.main import (
    load_config, click_okay_button, select_company_type, select_company_class,
    select_company_category, select_company_subcategory, open_nic_code_dialog,
    select_nic_codes_dynamic, enter_company_name, handle_name_check_and_submit
)
from name_checker_shivansh.scrape_tabs import scrape_all_tabs
from name_checker_shivansh.selenium_utils import AutomationError, VerificationStepFailed

# Enhanced FastAPI app with comprehensive documentation
app = FastAPI(
    title="Name Check Service",
    description="""
    ## Company Name Validation & Suggestion Service

    This API provides intelligent company name validation against MCA (Ministry of Corporate Affairs) 
    registrations and suggests alternative names when conflicts are detected.
    """,
    version="2.0.0", # Version bump for single-server architecture
    contact={
        "name": "Name Check API Support",
        "email": "support@namecheck.com",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

cache = RedisCache()
BASE_CONFIG = load_config()
logger = logging.getLogger(__name__)

# Serve static files for frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root():
    """Serve the main frontend application."""
    static_file_path = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file_path):
        return FileResponse(static_file_path)
    else:
        return HTMLResponse("<h1>Frontend not found</h1><p>Please build the frontend and place it in the static directory.</p>", status_code=404)

@app.post("/check_name")
async def check_name(payload: NameCheckPayload) -> Dict[str, Any]:
    """
    Takes a company name, runs it through the MCA portal automation,
    and if conflicts are found, uses an LLM to provide suggestions.
    This endpoint now runs the full process in a single service.
    """
    if not payload.names:
        raise HTTPException(status_code=400, detail="No names provided")

    config = BASE_CONFIG.copy()
    config["meta"] = config.get("meta", {}).copy()
    config["meta"]["company_name"] = payload.names[0]

    driver = None
    try:
        logger.info(f"[API] Starting browser for company name: {payload.names[0]}")
        driver = browser_setup.initialize_browser(config)
        
        # --- Execute the automation steps ---
        click_okay_button(driver)
        select_company_type(driver)
        select_company_class(driver)
        select_company_category(driver)
        select_company_subcategory(driver)
        open_nic_code_dialog(driver)
        select_nic_codes_dynamic(driver, config['meta']['nic_code'])
        enter_company_name(driver, config['meta']['company_name'])
        handle_name_check_and_submit(driver)
        
        time.sleep(3)  # Wait for tables to load

        # --- Scrape the tabs ---
        scraped_data = scrape_all_tabs(driver, output_json_path=None)
        
        if not scraped_data or ("error" not in scraped_data and "name_similarity" not in scraped_data):
            raise AutomationError("Scraping failed to return valid data from the portal.")

        # --- Analyze the results ---
        analyser = ConflictAnalyser(scraped_data)
        result = await analyser.analyse_async(check_type=payload.check_type)
        return result.dict()

    except (AutomationError, VerificationStepFailed, Exception) as e:
        # Log the full, detailed error for debugging purposes on the server.
        logger.exception(f"[API] Full error during name check automation for '{payload.names[0]}': {e}")
        
        # Return a simple, user-friendly error message to the frontend.
        user_error_message = "The automation script failed. This could be due to the MCA portal being slow, an invalid configuration, or an unexpected change on the website. Please try again in a few moments."
        return {"success": False, "data": None, "error": user_error_message}
    finally:
        if driver:
            driver.quit()
            logger.info("[API] Browser closed after API call")


@app.post(
    "/conflict-check", 
    response_model=NameCheckResult,
    tags=["Primary API"],
    summary="Company Name Conflict Analysis (Data Only)",
    description="""
    Analyze pre-scraped MCA (Ministry of Corporate Affairs) conflict data to determine name validity.
    This endpoint is useful for testing the analysis logic without running the full browser automation.
    """,
)
async def conflict_check(raw_data: dict):
    """
    **Analysis Endpoint**: Processes official MCA conflict data to determine if a proposed 
    company name is valid for registration.
    """
    analyser = ConflictAnalyser(raw_data)

    # Caching based on raw_data hash
    cache_key_payload = {"conflict_json": raw_data}
    if cached := cache.get(cache_key_payload):
        return cached

    result = await analyser.analyse_async()
    cache.set(cache_key_payload, result.dict())
    return result


@app.get("/health", tags=["System"], summary="Health Check")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/docs-info", tags=["System"], summary="API Information")  
async def docs_info():
    """Get information about available endpoints and their usage"""
    return {
        "primary_endpoint": "/conflict-check",
        "description": "Use /conflict-check for MCA conflict analysis",
        "documentation": "/docs",
        "frontend": "/",
        "health": "/health"
    } 