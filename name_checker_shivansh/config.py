import os
from selenium.webdriver.common.by import By
from dotenv import load_dotenv

load_dotenv()

# --- URLs ---
LOGIN_URL = "https://www.mca.gov.in/content/mca/global/en/foportal/fologin.html"
APPLICATION_HISTORY_URL = "https://www.mca.gov.in/content/mca/global/en/application-history.html"
MCA_HOME_URL = "https://www.mca.gov.in/content/mca/global/en/home.html"
SPICE_FORM_URL = "https://www.mca.gov.in/content/mca/global/en/mca/e-filing/incorporation-change-services/spice.html"

# --- TrueCaptcha Credentials & OTP Server ---
TRUECAPTCHA_USER = os.getenv("TRUECAPTCHA_USER", "your_username_here") # Fallback for local testing
TRUECAPTCHA_KEY = os.getenv("TRUECAPTCHA_KEY", "your_api_key_here") # Fallback for local testing
OTP_SERVER_URL = os.getenv("OTP_SERVER_URL", "http://127.0.0.1:3000")

# --- Selenium Defaults ---
DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3

# --- Element Locators ---
ELEMENTS = {
    # Main Form (Part A) - General
    "OK_BUTTON_POPUP": (By.ID, "guideContainer-rootPanel-modal_container_copy-panel-guidebutton_65123201___widget"),
    "MODAL_BACKDROP": (By.CLASS_NAME, "modal-backdrop"),

    # Company Type Selection
    "COMPANY_TYPE_DROPDOWN": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-guidedropdownlist___widget"),

    # Company Class Selection
    "COMPANY_CLASS_DROPDOWN": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-guidedropdownlist_co___widget"),

    # Company Category Selection
    "COMPANY_CATEGORY_DROPDOWN": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-guidedropdownlist_co_1813708729___widget"),

    # Company Sub-Category Selection
    "COMPANY_SUB_CATEGORY_DROPDOWN": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-guidedropdownlist_co_175619313___widget"),

    # NIC Code Selection
    "NIC_BUTTON": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-panel_1663114232_cop-panel_1119548299-panel-mca_button_v2___widget"),
    "NIC_SEARCH_BAR": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-panel_1663114232_cop-modal_container_1602-panel-panel-guidetextbox___widget"),
    "NIC_PAGE_SIZE_DROPDOWN": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-panel_1663114232_cop-modal_container_1602-panel-customdropdown___widget"),
    "NIC_CHECKBOX_XPATH": "//input[@type='checkbox' and @value='{}']", # Formattable string for dynamic value
    "NIC_ADD_BUTTON": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel-panel_1663114232_cop-modal_container_1602-panel-panel-guidebutton___widget"),

    # Company Name Input
    "COMPANY_NAME_INPUT": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel_copy-panel-panel-guidetextbox_1884163___widget"),
    "AUTO_CHECK_BUTTON": (By.ID, "guideContainer-rootPanel-panel_copy_222446296-guidebutton_copy_748_1005506464___widget"),

    # Post Name-Check Actions
    "PROCEED_INCORPORATION_RADIO": (By.CSS_SELECTOR, "input[type='radio'][id='option2']"),
    "CONTINUE_BUTTON": (By.ID, "guideContainer-rootPanel-panel_copy-modal_container-panel-guidebutton_65123201___widget"),

    # Login Page Elements
    "LOGIN_INITIAL_OK_BUTTON": (By.XPATH, "//button[@class='btn btn-primary' and @data-dismiss='modal' and contains(text(), 'OK')]"),
    "LOGIN_USER_ID_FIELD_XPATH": "//input[@type='text']", # Primary XPath
    "LOGIN_USER_ID_FIELD_PLACEHOLDER_XPATH": "//input[contains(@placeholder,'User ID')]", # Fallback
    "LOGIN_USER_ID_FIELD_NAME_XPATH": "//input[contains(@name,'userId')]", # Fallback
    "LOGIN_PASSWORD_FIELD": (By.CSS_SELECTOR, "input[type='password']"),
    "LOGIN_CAPTCHA_IMAGE": (By.CSS_SELECTOR, "img[src*='captcha']"),
    "LOGIN_CAPTCHA_INPUT": (By.ID, "customCaptchaInput"),
    "LOGIN_BUTTON": (By.XPATH, "//button[contains(text(),'Login') or @type='submit']"),
    "LOGIN_ERROR_MESSAGE": (By.CSS_SELECTOR, ".alert-danger"),
    "LOGIN_CAPTCHA_REFRESH_BUTTON": (By.ID, "refresh-img"),
    "LOGIN_POPUP_XPATH": (By.XPATH, "/html/body/div[2]/div/div[2]/div/div/div/div[2]/button"), # From login_with_persistence
    "LOGIN_FORM_SUBMIT_BUTTON": (By.ID, "guideContainer-rootPanel-panel_1846244155-submit___widget"), # From login_with_persistence
    "LOGIN_CAPTCHA_ERROR_MESSAGE_ID": (By.ID, "showResult"), # From login_with_persistence
    "LOGIN_USER_FIELD_ID": (By.ID, "guideContainer-rootPanel-panel_1846244155-guidetextbox___widget"),
    "LOGIN_PASSWORD_FIELD_ID": (By.ID, "guideContainer-rootPanel-panel_1846244155-guidepasswordbox___widget"),
    
    # Scrape Tabs Elements
    "ERROR_TAB": (By.XPATH, "//a[.//span[text()='Errors/Info']]"),
    "NAME_SIMILARITY_TAB": (By.XPATH, "//a[.//span[text()='Name Similarity Alerts']]"),
    "TRADEMARK_TAB": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel_672096424-panel_copy-panel1629804157135___guide-item-nav"),
    "ERROR_TABLE": (By.ID, "errorTable"),
    "NAME_SIMILARITY_TABLE": (By.ID, "nameSimilarityAlertsTable"),
    "TRADEMARK_TABLE": (By.ID, "guideContainer-rootPanel-panel_2017717670_cop-panel_672096424-panel_copy-panel1629804157135__")
}