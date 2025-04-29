from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
import os
from pathlib import Path

TREE_FILE_PATH = str(Path.home() / "tree_updater" / "tree_output_compact.txt")
CHATGPT_URL = "https://chat.openai.com/"

def main():
    print("[🛡️] Starting cautious uploader (Google Chrome, patched for Selenium 4.31+)...")

    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("user-data-dir=/home/erisfelix/.config/google-chrome")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Correct for Selenium 4.31+ to force classic handshake
    options.set_capability("goog:chromeOptions", {"w3c": False})

    chrome_service = Service(executable_path="/usr/bin/chromedriver")
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
        file_input.send_keys(TREE_FILE_PATH)
        print(f"[📂] Uploaded: {TREE_FILE_PATH}")
    except Exception as e:
        print(f"[⚠️] Upload failed: {e}")

    input("[⏹️] Press ENTER to close the browser...")
    driver.quit()

if __name__ == "__main__":
    main()
