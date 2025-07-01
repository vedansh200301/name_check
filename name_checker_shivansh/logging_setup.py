import os
import logging
from datetime import datetime

def setup_logging(api_mode=False):
    """Setup logging configuration. If api_mode is True, use a fixed log file name."""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    if api_mode:
        log_file = 'logs/automation_api.log'
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f'logs/automation_{timestamp}.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logging.info('Started logging')
    return log_file 