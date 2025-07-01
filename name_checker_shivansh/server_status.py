# server_status.py

import requests
import logging
from typing import Tuple

# Initialize logger for this module
logger = logging.getLogger(__name__)

def check_server_status_robust(url: str, content_check_id: str, timeout: int = 10) -> Tuple[bool, str]:
    """
    Performs a robust server status check using a session and mimicking browser headers
    to avoid being blocked by security measures like a WAF.

    Args:
        url: The URL to check.
        content_check_id: The string (element ID) to search for in the page content.
        timeout: Timeout in seconds for the GET request.

    Returns:
        A tuple containing:
        - bool: True if the site is up and content is verified, False otherwise.
        - str: A message describing the status.
    """
    # Create a session object to persist headers and cookies
    session = requests.Session()

    # Set the headers to mimic a real browser, based on the provided HAR file
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:139.0) Gecko/20100101 Firefox/139.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/incorporation-change-services/spice.html",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1"
    })

    try:
        logger.info(f"[Status Check] Performing robust GET request to {url}")
        
        # The session will automatically handle any cookies set by the server
        response = session.get(url, timeout=timeout)

        # Check the final status code
        if response.status_code == 200:
            # If successful, verify the page content
            if content_check_id in response.text:
                logger.info("[Status Check] Request successful and page content verified.")
                return True, "Website is online and operational."
            else:
                logger.warning(f"[Status Check] Website is online, but the expected content ('{content_check_id}') was not found. It may be a maintenance or error page.")
                return False, "The website is online but not fully functional."
        
        elif response.status_code == 403:
            logger.error("[Status Check] Request failed with status code 403 (Forbidden). The server is actively blocking this script.")
            return False, "The server is blocking automated access."
            
        else:
            logger.warning(f"[Status Check] Request failed with status code {response.status_code}.")
            return False, f"The website returned an error (Status: {response.status_code})."

    except requests.exceptions.Timeout:
        logger.error(f"[Status Check] Request to {url} timed out after {timeout} seconds.")
        return False, "The website is too slow or unresponsive."
    except requests.exceptions.RequestException as e:
        logger.error(f"[Status Check] Request to {url} failed with an exception: {e}")
        return False, "Could not connect to the website due to a network error."

# This block allows you to run the script directly for testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] [%(module)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )

    target_url = "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/incorporation-change-services/spice.html"
    element_id_to_check = "guideContainer-rootPanel-panel_copy_222446296-guidebutton_copy_748_1005506464___widget"

    print(f"--- Running Robust Server Status Check for: {target_url} ---")

    is_online, status_message = check_server_status_robust(
        url=target_url,
        content_check_id=element_id_to_check
    )

    print("\n--- Check Complete ---")
    print(f"Status: {'ONLINE' if is_online else 'OFFLINE'}")
    print(f"Message: {status_message}")
    print("--------------------")