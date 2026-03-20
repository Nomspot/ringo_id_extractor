import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import requests
from urllib.parse import urlparse
import sqlite3
import shutil
import batch_prepare
import subprocess
from google.cloud import storage
from google.genai import Client
import glob
import vertex_ai
import json_to_excel
import check_gemini_models
from tqdm import tqdm

""" GENERAL SETTINGS"""
# --- 1. Flags (Booleans) ---
CLEAR_DATABASE = os.getenv("CLEAR_DATABASE", "False").lower() == "true"
CLEAR_IMAGE_FOLDER = os.getenv("CLEAR_IMAGE_FOLDER", "False").lower() == "true"
SILENT_LOG = os.getenv("SILENT_LOG", "False").lower() == "true"

# --- 2. Credentials & URLs ---
RINGO_EMAIL = os.getenv("RINGO_EMAIL", "")
RINGO_PASSWORD = os.getenv("RINGO_PASSWORD", "")
BASE_URL = "https://app.ringo.chat/chat"
LOG_IN_URL = "https://app.ringo.chat/login"

# --- 3. Chat Logic Settings (Integers) --
NUMBER_OF_MESSAGES_TO_LOAD_FROM_CHAT = int(os.getenv("CHAT_MESSAGE_COUNT", 100))
NUMBER_OF_CONVERSATIONS_TO_LOAD_PER_SESSION = int(os.getenv("CHAT_LOAD_PER_SESSION", 50))
START_OF_CONVERSATION = int(os.getenv("CHAT_START_INDEX", 0))
TOTAL_NUMBER_OF_CONVERSATION_ITERATIONS = int(os.getenv("CHAT_LOAD_ITERATIONS", 10))


# --- 4. File System & DB Paths ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "saved_data.db")
SAVE_FOLDER = os.getenv("SAVE_FOLDER", "downloads")
RESULTS_NAME = os.getenv("RESULTS_NAME", "results.jsonl")

# --- 5. Google Cloud & AI Settings ---
PROJECT_ID = os.getenv("GC_PROJECT_ID", "")
LOCATION = os.getenv("GC_LOCATION", "global")
BUCKET_NAME = os.getenv("GC_BUCKET_ID", "")
MODEL_ID = os.getenv("AI_MODEL", "gemini-3.1-pro-preview")
storage_client = storage.Client(project=PROJECT_ID)
genai_client = Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
bucket = storage_client.bucket(BUCKET_NAME)

# --- 6. Tool Paths ---
GSUTIL = os.getenv("GSUTIL", "gsutil")

def check_gcp_login():
    print("🔍 Checking Google Cloud credentials...")
    result = subprocess.run(
        [GSUTIL, "ls", f"gs://{BUCKET_NAME}"], 
        shell=True, 
        capture_output=True, 
        text=True
    )
    
    if result.returncode == 0:
        print("✅ GCP Credentials are valid.")
        return True
    else:
        print("\n❌ GOOGLE ERROR MESSAGE:")
        print(result.stderr) # This tells us EXACTLY what's wrong
        print("\nPlease run this in your terminal first:")
        print(f"   gcloud auth login")
        print(f"   gcloud config set project {PROJECT_ID}")
        return False

def run_cloud_automation():

    print(f"🧹 Clearing bucket gs://{BUCKET_NAME}...")
    try:
        # gsutil rm -rf gs://bucket/** deletes all contents recursively
        # We use a wildcard ** to ensure we get everything
        subprocess.run(
            [GSUTIL, "-m", "rm", "-rf", f"gs://{BUCKET_NAME}/**"],
            shell=True,
            capture_output=True # This hides the "bucket not found" errors if it's already empty
        )
        print("✅ Bucket cleared.")
    except Exception as e:
        # If the bucket is already empty, gsutil might throw an error. 
        # We catch it so the script keeps moving.
        print(f"⚠️ Note: Bucket was already empty or couldn't be cleared: {e}")

    print("📤 Uploading images to the cloud...")
    try:
        if not SILENT_LOG:
            subprocess.run(
                [GSUTIL, "-m", "cp", "-r", f"{SAVE_FOLDER}/*", f"gs://{BUCKET_NAME}/{SAVE_FOLDER}/"],
                check=True,
                shell=True
            )
        else:
            subprocess.run(
                [GSUTIL, '-q', "-m", "cp", "-r", f"{SAVE_FOLDER}/*", f"gs://{BUCKET_NAME}/{SAVE_FOLDER}/"],
                check=True,
                shell=True
            )
        print("✅ Upload successful!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Upload failed! Error: {e}")
        return False

    print("📝 Creating requests.jsonl...")
    created_file = batch_prepare.create_jsonl(BUCKET_NAME, SAVE_FOLDER, "requests.jsonl")

    time.sleep(2)

    if created_file:
        print("🌐 Uploading requests.jsonl...")
        jsonl_blob = bucket.blob("requests.jsonl")
        jsonl_blob.upload_from_filename("requests.jsonl")

        # 3. Trigger the Batch Job
        print("🚀 Triggering Vertex AI Batch Job...")
        batch_job = vertex_ai.create_job(PROJECT_ID)

        print("Waiting to download results.jsonl...")
        wait_and_download(batch_job.name)
    else:
        print("❌ Try fixing the error and re-run the code")
        return False
    
    return True

def wait_and_download(batch_job_name):
    client = Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    
    print(f"⏳ Waiting for job {batch_job_name} to complete...")

    pbar = None
    last_completed = 0
    
    while True:
        try:
            job = client.batches.get(name=batch_job_name)
            
            status = str(job.state).upper()
            status_text = status.split('.', 1)[1]
            
            if "RUNNING" in status:
                stats = job.completion_stats

                completed = getattr(stats, 'successful_count', 0) or 0
                failed = getattr(stats, 'failed_count', 0) or 0
                incomplete = getattr(stats, 'incomplete_count', 0) or 0
                total = completed + failed + incomplete

                if pbar is None and total > 0:
                    pbar = tqdm(total=total, desc="AI Working", unit="completed")

                if pbar is not None:
                    new_increments = completed - last_completed
                    if new_increments > 0:
                        pbar.update(new_increments)
                        last_completed = completed
                    
                    # Add status/info to the right side of the bar
                    pbar.set_postfix({"status": status_text, "failed": failed})

            # Check if 'SUCCEEDED' is anywhere in the status string
            if "SUCCEEDED" in status:
                print("\n✅ Batch Job Finished!")
                
                try:
                    gcs_output_path = job.dest.gcs_uri
                    print(f"📂 Results found at: {gcs_output_path}")
                except AttributeError:
                    print("❌ Error: Could not find 'dest' attribute. Printing job structure again:")
                    print(vars(job))
                    return
                
                break
            elif any(x in status for x in ["FAILED", "CANCELLED", "ERROR"]):
                print(f"\n❌ Job ended with status: {status}. Error: {getattr(job, 'error', 'Unknown Error')}")
                return

        except Exception as e:
            # If the internet drops, just wait and try again
            print(f"📡 Connection blip: {e}. Retrying in 30 seconds...")

        time.sleep(30)

    # 1. Download all split files to a temporary hidden folder
    temp_dir = ".temp_results"
    os.makedirs(temp_dir, exist_ok=True)
    
    print("📥 Downloading results...")
    remote_path = f"{gcs_output_path.rstrip('/')}/**/*.jsonl"
    subprocess.run(
        [GSUTIL, "-m", "cp", remote_path, temp_dir],
        check=True,
        shell=True
    )

    # 2. Merge all split files into one "results.jsonl" in the current folder
    final_filename = RESULTS_NAME
    print(f"Merge and rename -> {final_filename}")
    
    with open(final_filename, "w", encoding="utf-8") as outfile:
        # Find all jsonl files in the temp folder
        for part_file in glob.glob(os.path.join(temp_dir, "*.jsonl")):
            with open(part_file, "r", encoding="utf-8") as infile:
                outfile.write(infile.read())
            os.remove(part_file) # Clean up the part file

    # 3. Remove the temp directory
    os.rmdir(temp_dir)
    print(f"✨ All done! Final data is in {os.path.abspath(final_filename)}")

def delete_folder_entirely(folder_path):
    # Convert to absolute path to be 100% sure where we are deleting
    target = os.path.abspath(folder_path)
    
    if os.path.exists(target):
        try:
            shutil.rmtree(target)
            print(f"Successfully deleted: {target}")
        except PermissionError:
            print(f"Error: Permission denied. Close any files open in {target}.")
        except Exception as e:
            print(f"An error occurred: {e}")
    else:
        print("Folder does not exist, nothing to delete.")

def get_json(driver, url):
    script = """
    const callback = arguments[arguments.length - 1];
    fetch(arguments[0])
        .then(res => res.json())
        .then(data => callback(data))
        .catch(err => callback({error: err.message}));
    """
    return driver.execute_async_script(script, url)

def setup_db():
    """Creates the database and table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # We use 'name' as a PRIMARY KEY so it's indexed (blazing fast)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_files (
            name TEXT PRIMARY KEY
        )
    ''')
    conn.commit()
    conn.close()

def clear_db():
    """Removes every entry from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM processed_files')
    conn.commit()
    conn.close()
    print("Database cleared!")

def has_been_processed(name):
    """Returns True if the name is in the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM processed_files WHERE name = ?', (name,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_as_processed(name):
    """Adds a name to the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO processed_files (name) VALUES (?)', (name,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists
    finally:
        conn.close()

def setup_driver():
    options = uc.ChromeOptions() # Use uc.ChromeOptions specifically
    
    # 1. Standard UC bypasses
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36')

    current_version = get_chrome_major_version()

    return uc.Chrome(options=options, version_main=current_version, use_subprocess=True)

def get_chrome_major_version():
    """Detects the installed Chrome version on Windows."""
    try:
        # Standard path for Chrome on Windows
        path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(path):
            path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            
        # Run a quick shell command to get the version string
        stream = os.popen(f'powershell -command "(Get-Item \'{path}\').VersionInfo.ProductVersion"')
        full_version = stream.read().strip()
        
        # Extract the major version (e.g., '145' from '145.0.7632.160')
        major_version = full_version.split('.')[0]
        return int(major_version)
    except Exception:
        return None # Fallback if detection fails
    
def start_autimation(driver):
    global START_OF_CONVERSATION
    global NUMBER_OF_CONVERSATIONS_TO_LOAD_PER_SESSION
    global TOTAL_NUMBER_OF_CONVERSATION_ITERATIONS

    driver.get(LOG_IN_URL)

    wait = WebDriverWait(driver, 30)

    email_element = wait.until(EC.visibility_of_element_located((By.ID, "email")))
    email_element.send_keys(RINGO_EMAIL)
    time.sleep(0.2)
    password_element = wait.until(EC.visibility_of_element_located((By.ID, "password")))
    password_element.send_keys(RINGO_PASSWORD)
    log_in_element = wait.until(EC.visibility_of_element_located((By.XPATH, '//button[contains(@class, "submit-button")]')))
    log_in_element.click()

    try:
        wait.until(EC.url_matches(BASE_URL))
    except:
        print("URL DID NOT PASS, STOPPING SCRIPT!")
        return False

    driver.set_window_position(-2000, 0)

    for i in range(TOTAL_NUMBER_OF_CONVERSATION_ITERATIONS):
        try:
            print(f"Checking messages in conversations : {START_OF_CONVERSATION} To {START_OF_CONVERSATION + NUMBER_OF_CONVERSATIONS_TO_LOAD_PER_SESSION}")

            # --- STEP 1: Get all the IDs ---
            list_url = f"https://app.ringo.chat/conversations?agency_id=248&start={START_OF_CONVERSATION}&count={NUMBER_OF_CONVERSATIONS_TO_LOAD_PER_SESSION}"
            data = get_json(driver, list_url)

            if isinstance(data, dict) and "result" in data:
                conversations = data["result"].get("conversations", [])
                all_ids = [item['id'] for item in conversations]
            else:
                all_ids = []

            # --- STEP 2: Loop and check for images ---
            for conv_id in all_ids:
                read_url = f"https://app.ringo.chat/messages/{conv_id}?offset=0&limit={NUMBER_OF_MESSAGES_TO_LOAD_FROM_CHAT}&reverse=true"
                if not SILENT_LOG:
                    print(f"\nChecking conversation {conv_id}...")
                
                data = get_json(driver, read_url)
                payload = data.get('result', [])
                messages = payload.get('messages', []) if isinstance(payload, dict) else payload

                if isinstance(messages, list):
                    for msg in messages:
                        if msg.get('file_count', 0) > 0:
                            media = msg.get('media', [{}])[0]
                            image_url = media.get('renderUrl')

                            path = urlparse(image_url).path
                            file_name = os.path.basename(path)

                            if has_been_processed(file_name):
                                if not SILENT_LOG:
                                    print(f"File - {file_name} has already been processed, coninuing...")
                                continue
                            
                            valid_extensions = (".jpg", ".jpeg", ".png")
                            if not file_name.lower().endswith(valid_extensions):
                                if not SILENT_LOG:
                                    print(f"File - {file_name} is not a supported image, skipping...")
                                mark_as_processed(file_name)
                                continue
                            
                            # Get the phone number (sender's number)
                            phone_number = msg.get('from', 'unknown_number')

                            try:
                                phone_number = "0" + str(phone_number).split('972', 1)[1]
                            except:
                                phone_number = str(phone_number)

                            if image_url:
                                if not SILENT_LOG:
                                    print(f"📥 Downloading image from {phone_number}...")

                                if not os.path.exists(SAVE_FOLDER):
                                    os.makedirs(SAVE_FOLDER)
                                    
                                extension = os.path.splitext(file_name)[1]
                                base_name = f"{phone_number}"
                                final_file_name = f"{base_name}{extension}"
                                file_path = os.path.join(SAVE_FOLDER, final_file_name)

                                counter = 0
                                while os.path.exists(file_path):
                                    final_file_name = f"{base_name}_{counter}{extension}"
                                    file_path = os.path.join(SAVE_FOLDER, final_file_name)
                                    counter += 1

                                # Download the actual file
                                try:
                                    img_data = requests.get(image_url).content
                                    with open(file_path, 'wb') as handler:
                                        handler.write(img_data)
                                    mark_as_processed(file_name)
                                    if not SILENT_LOG:
                                        print(f"✅ Saved to: {file_path}")
                                except Exception as e:
                                    print(f"❌ Failed to download {image_url}: {e}")
                
                #time.sleep(0.5)
            START_OF_CONVERSATION += NUMBER_OF_CONVERSATIONS_TO_LOAD_PER_SESSION
        except Exception as e:
            print(f"An error occured - {e}")
            return False
    return True

def main():
    if not check_gcp_login():
        return
    if not check_gemini_models.is_model_available(MODEL_ID):
        return

    if CLEAR_DATABASE:
        clear_db()

    if CLEAR_IMAGE_FOLDER:
        delete_folder_entirely(SAVE_FOLDER)

    setup_db()
    driver = None
    automation_successfull = False
    try:
        driver = setup_driver()
        automation_successfull = start_autimation(driver)
    except Exception as e:
        print(f"❌ Automation Error: {e}")
    finally:
        if driver:
            print("🛑 Closing Chrome Driver...")
            driver.quit() # Use .quit() not .close()
    if not automation_successfull:
        return
    print("Process Ended...")
    time.sleep(1)
    print("Running Cloud automation...")
    time.sleep(1)
    if run_cloud_automation():
        time.sleep(1)
        json_to_excel.run(RESULTS_NAME)


if "__main__" in __name__:
    main()