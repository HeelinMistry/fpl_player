import logging

def setup_user_output(log_file_path='project_results.log', console_level=logging.INFO):
    """
    Configures logging to separate user-facing output (console)
    from a detailed audit trail (file).
    """
    # 1. Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set root to DEBUG to allow all messages through

    # Optional: Clear existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # 2. Define a simple, clean format for the console (User Output)
    user_formatter = logging.Formatter('%(levelname)s: %(message)s')

    # 3. Define a detailed format for the file (Audit Trail)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 4. Console Handler (For user-facing output)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(user_formatter)
    # Only show INFO, WARNING, ERROR, and CRITICAL messages to the user
    console_handler.setLevel(console_level)
    root_logger.addHandler(console_handler)

    # 5. File Handler (For complete technical and user output)
    file_handler = logging.FileHandler(log_file_path, mode='a')
    file_handler.setFormatter(file_formatter)
    # Log everything (DEBUG and up) to the file
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Inform the user (this will show in console and file because it's INFO)
    logging.info(f"Project initialized. All primary output logged to console and '{log_file_path}'.")

# Call this at the start of your main.py
# setup_user_output()