from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, WebDriverException

app = FastAPI()

# --- CONFIGURATION ---
PASSWORD = "100005"
RENDER_EMAIL = "oskar.loytonen@icloud.com"
RENDER_PASSWORD = "Kettufox13"
RENDER_DASHBOARD_URL = "https://dashboard.render.com/web/srv-d0j0o524d50c73e26o60/settings"

# Track users awaiting password confirmation for /destroy
pending_destroy_password = {}

@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return JSONResponse({"reply": "Missing user_id or message."}, status_code=400)

    # Check if user is currently asked for password
    if pending_destroy_password.get(user_id):
        if message.strip() == PASSWORD:
            pending_destroy_password.pop(user_id)
            success = await suspend_service_async()
            if success:
                return JSONResponse({"reply": "✅ Service suspended successfully."})
            else:
                return JSONResponse({"reply": "❌ Failed to suspend service."})
        else:
            pending_destroy_password.pop(user_id)
            return JSONResponse({"reply": "❌ Incorrect password. Destroy command cancelled."})

    if message.strip() == "/destroy":
        pending_destroy_password[user_id] = True
        return JSONResponse({"reply": "🔒 Please enter the password to confirm suspension:"})

    return JSONResponse({"reply": f"Message received: {message}"})


def suspend_service():
    print("[+] Starting suspend_service()...")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.get("https://dashboard.render.com/login")
        time.sleep(3)

        # Login email input
        email_input = driver.find_element(By.ID, "email")
        email_input.clear()
        email_input.send_keys(RENDER_EMAIL)

        # Login password input
        password_input = driver.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys(RENDER_PASSWORD)
        password_input.send_keys(Keys.RETURN)
        print("[+] Submitted login form.")
        time.sleep(6)  # Wait for login

        # Navigate to service settings
        driver.get(RENDER_DASHBOARD_URL)
        time.sleep(5)

        # Scroll down to bottom (sometimes needed to reveal buttons)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Find the Suspend button - update this selector if needed
        try:
            suspend_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Suspend Web Service')]")
        except NoSuchElementException:
            print("[-] Suspend button not found.")
            return False

        suspend_btn.click()
        print("[+] Clicked suspend button.")
        time.sleep(3)

        # If confirmation dialog appears, try to confirm (adjust selector as needed)
        try:
            confirm_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Suspend Web Service')]")
            confirm_btn.click()
            print("[+] Confirmed suspension.")
        except NoSuchElementException:
            print("[*] No confirmation button found, maybe suspend was immediate.")

        time.sleep(5)
        print("[+] Suspension should be completed now.")

        return True
    except WebDriverException as e:
        print(f"[!] Selenium WebDriver error: {e}")
        return False
    except Exception as e:
        print(f"[!] Unexpected error: {e}")
        return False
    finally:
        if driver:
            driver.quit()
            print("[+] Chrome driver quit.")


async def suspend_service_async():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, suspend_service)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
