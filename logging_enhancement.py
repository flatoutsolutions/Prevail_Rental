import logging
import os
import sys
from datetime import datetime

def setup_logging(log_file=None, console_level=logging.INFO, file_level=logging.DEBUG):
    """
    Set up logging configuration with both console and file handlers.
    
    Args:
        log_file: Path to log file. If None, only console logging is set up.
        console_level: Logging level for console output (default: INFO)
        file_level: Logging level for file output (default: DEBUG)
    """
    # Create a custom logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set root logger to lowest level
    
    # Clear any existing handlers
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Create formatters
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if log_file is provided
    if log_file:
        # Make sure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Add timestamp to log filename if desired
        # log_file = f"{os.path.splitext(log_file)[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    # Log startup information
    logger.info("="*50)
    logger.info(f"Logging initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if log_file:
        logger.info(f"Log file: {os.path.abspath(log_file)}")
    logger.info("="*50)
    
    # Return the configured logger
    return logger

def get_logger(name):
    """
    Get a logger with the specified name.
    This is a convenience function for getting named loggers.
    
    Args:
        name: Name of the logger, typically __name__ from the calling module
    
    Returns:
        A logger instance
    """
    return logging.getLogger(name)