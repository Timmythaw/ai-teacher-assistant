import logging
import os

#PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

def setup_logger(name="agent", log_file=None, level=logging.INFO):
    """
    Setup a logger that writes to both console and a file.
    """
    # Set default log file if none provided
    if log_file is None:
        log_file = os.environ.get("LOG_PATH")
    
    # If still no log file, use a default path
    if log_file is None:
        # Create logs directory in project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        logs_dir = os.path.join(project_root, "logs")
        log_file = os.path.join(logs_dir, f"{name}.log")
    
    # Ensure logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Create a logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    fh = logging.FileHandler(log_file, mode="a")
    fh.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)

    # Log format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Add handlers
    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

# Default logger for project
logger = setup_logger()