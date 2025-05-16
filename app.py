from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

app = FastAPI()

# --- CONFIGURATION ---
PASSWORD = "100005"
RENDER_EMAIL = "oskar.loytonen@icloud.com"
RENDER_PASSWORD = "Kettufox13"
RENDER_DASHBOARD_URL = "https://dashboard.render.com/web/srv-d0j0o524d50c73e26o60/settings"

# In-memory state to track password request per user
pending_destroy_password = {}

# --- Chat Endpoint ---
@app.post("/chat")
async def chat_endpoint(request: Request):
    data = await request.json()
    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return JSONResponse({"reply": "Missing user_id or message."}, status_code=400)

    # Check if user is in password prompt state for /destroy
    if pending_destroy_password.get(user_id):
        if message.strip() == PASSWORD:
            pending_destroy_password.pop(user_id)
            # Run suspend service in background
            success = await suspend_service_async()
            if success:
                return JSONResponse({"reply": "✅ Service suspended successfully."})
            else:
                return JSONResponse({"reply": "❌ Failed to suspend service."})
        else:
            pending_destroy_password.pop(user_id)
            return JSONResponse({"reply": "❌ Incorrect password. Destroy command cancelled."})

    # Detect /destroy command
    if message.strip() == "/destroy":
        pending_destroy_password[user_id] = True
        return JSONResponse({"reply": "🔒 Please enter the password to confirm suspension:"})

    # Otherwise, normal echo chat
    return JSONResponse({"reply": f"Message received: {message}"})


# --- Suspend service using Selenium (blocking) ---
def suspend_service():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    try:
        # Login to Render.com
        driver.get("https://dashboard.render.com/login")
        time.sleep(3)

        # Fill email
        email_input = driver.find_element(By.ID, "email")
        email_input.clear()
        email_input.send_keys(RENDER_EMAIL)

        # Fill password
        password_input = driver.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys(RENDER_PASSWORD)
        password_input.send_keys(Keys.RETURN)

        # Wait for login
        time.sleep(6)

        # Go to your service settings page
        driver.get(RENDER_DASHBOARD_URL)
        time.sleep(5)

        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        # Find "Suspend Web Service" button and click it
        # Note: You may need to adjust this selector if Render UI changes
        suspend_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Suspend Web Service')]")
        suspend_btn.click()
        time.sleep(3)

        # Find input box to type command
        # Adjust selector according to actual input box
        input_box = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
        input_box.send_keys("sudo suspend web service fastapi")
        time.sleep(1)

        # Confirm suspend by clicking the button again (or confirm button)
        confirm_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Suspend Web Service')]")
        confirm_btn.click()

        time.sleep(5)  # Wait for action to complete

        driver.quit()
        return True
    except Exception as e:
        print(f"Error suspending service: {e}")
        try:
            driver.quit()
        except:
            pass
        return False


# --- Run suspend_service() async ---
async def suspend_service_async():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, suspend_service)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
