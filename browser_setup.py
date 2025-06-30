import logging
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
import os
import time
import platform
import sys
import login_with_persistence  # Import the login module
from config import SPICE_FORM_URL # Import SPICE_FORM_URL from config
from logging_setup import setup_logging # Import setup_logging
from webdriver_manager.firefox import GeckoDriverManager # Import GeckoDriverManager

# Initialize logger for this module
logger = logging.getLogger(__name__)

def setup_firefox_profile_and_options(profile_path: str):
    """Setup Firefox with specific profile and return Options."""
    logger.info(f'Setting up Firefox profile from: {profile_path}')
    
    options = FirefoxOptions()
    if profile_path and os.path.exists(profile_path):
        options.add_argument("-profile")
        options.add_argument(profile_path)
        logger.info(f"Using existing Firefox profile: {profile_path}")
    else:
        logger.warning(f"Firefox profile path not found: {profile_path}. Using a new temporary profile.")
    
    logger.info('Firefox profile setup completed.')
    return options

def initialize_browser(config: dict):
    """Initialize browser with configuration and navigate to URL."""
    logger.info('Starting browser initialization.')
    
    driver = None # Initialize driver to None
    try:
        # Setup Firefox profile options
        options = setup_firefox_profile_and_options(config['meta']['firefox_profile_path'])
        
        # Automatically download and get the path to geckodriver
        logger.info('Attempting to automatically download/locate Geckodriver...')
        geckodriver_path = GeckoDriverManager().install()
        logger.info(f'Geckodriver located at: {geckodriver_path}')

        # Initialize Firefox driver
        logger.info('Starting Firefox browser.')
        service = FirefoxService(executable_path=geckodriver_path)
        driver = webdriver.Firefox(service=service, options=options)
        logger.info('Firefox browser started.')
        
        # Maximize window
        logger.info('Maximizing browser window.')
        driver.maximize_window()
        
        # Navigate to the URL
        target_url = config["meta"]["url"]
        logger.info(f'Navigating to URL: {target_url}')
        driver.get(target_url)
        logger.info('Page loaded.')
        
        # Check if login is required
        logger.info('Checking if login is required.')
        if login_with_persistence.check_login_required(driver, SPICE_FORM_URL): # Use SPICE_FORM_URL for check
            logger.info('Login is required. Starting login process.')
            
            # Perform login using the login_with_persistence module
            driver, login_success = login_with_persistence.login_to_mca_and_verify(driver=driver, config=config)
            if not login_success:
                logger.error('Login failed.')
                raise Exception('Failed to login to the portal.')
            
            # After successful login, ensure we are on the SPICE form.
            # login_to_mca_and_verify should ideally land us there or on application history.
            # If not already on SPICE, navigate explicitly.
            if SPICE_FORM_URL not in driver.current_url:
                logger.info(f"Not directly on SPICE form after login, navigating to {SPICE_FORM_URL}.")
                driver.get(SPICE_FORM_URL)
                time.sleep(3) # Give page time to load
                if SPICE_FORM_URL not in driver.current_url:
                    logger.error('Failed to navigate to SPICE form after login and explicit attempt.')
                    raise Exception('Failed to navigate to SPICE form after login.')
            
            logger.info('Login and navigation to SPICE form successful.')
        else:
            logger.info('No login required. Already on the target page or logged in.')
        
        logger.info('Browser initialization completed.')
        return driver
    except Exception as e:
        logger.error(f'Error during browser initialization: {str(e)}')
        # Ensure driver is closed if an error occurs during initialization before it's returned
        if driver:
            try:
                driver.quit()
                logger.info("Browser closed due to initialization error.")
            except Exception as quit_e:
                logger.error(f"Error closing browser after initialization failure: {quit_e}")
        raise # Re-raise the exception