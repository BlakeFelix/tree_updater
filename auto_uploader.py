from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import argparse
import time
import os
from pathlib import Path

CONFIG = Path.home() / ".auto_uploader_config"
TREE_FILE_PATH = str(Path.home() / "tree_updater" / "tree_output_compact.txt")
CHATGPT_URL = "https://chat.openai.com/"

USER_DATA_ENV = "CHROME_USER_DATA_DIR"
CHROMEDRIVER_ENV = "CHROMEDRIVER"
DEFAULT_USER_DATA_DIR = os.getenv(USER_DATA_ENV, "/home/erisfelix/.config/google-chrome")
DEFAULT_CHROMEDRIVER = os.getenv(CHROMEDRIVER_ENV, "/usr/bin/chromedriver")

def main():
    parser = argparse.ArgumentParser(description="Upload a tree snapshot to ChatGPT")
    parser.add_argument("--file", type=Path, help="Override tree snapshot path")
    parser.add_argument("--user-data-dir", default=DEFAULT_USER_DATA_DIR,
                        help="Chrome user data directory")
    parser.add_argument("--chromedriver", default=DEFAULT_CHROMEDRIVER,
                        help="Path to chromedriver executable")
    args = parser.parse_args()

    snapshot = args.file
    if snapshot is None and CONFIG.exists():
        snapshot = Path(CONFIG.read_text().strip())
    if snapshot is None:
        snapshot = Path(TREE_FILE_PATH)

    print("[🛡️] Starting cautious uploader (Google Chrome, patched for Selenium 4.31+)...")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"user-data-dir={args.user_data_dir}")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Correct for Selenium 4.31+ to force classic handshake
    options.set_capability("goog:chromeOptions", {"w3c": False})

    chrome_service = Service(executable_path=args.chromedriver)
    driver = webdriver.Chrome(service=chrome_service, options=options)

    driver.get(CHATGPT_URL)

    print("[⏳] Using your existing Google Chrome session.")
    print("👆 Please manually open the ChatGPT conversation where you want to upload.")
    input("[⏩] Press ENTER here to trigger the upload...")

    try:
        upload_button = driver.find_element(By.XPATH, "//button[contains(., 'Upload') or contains(., 'Attach')]")
        upload_button.click()
        time.sleep(2)
        file_input = driver.find_element(By.XPATH, "//input[@type='file']")
        file_input.send_keys(str(snapshot))
        print(f"[📂] Uploaded: {snapshot}")
    except Exception as e:
        print(f"[⚠️] Upload failed: {e}")

    input("[⏹️] Press ENTER to close the browser...")
    driver.quit()

if __name__ == "__main__":
    main()
