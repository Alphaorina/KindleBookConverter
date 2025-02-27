import os
import time
import logging
import subprocess
import smtplib
import shutil
from email.message import EmailMessage
from tqdm import tqdm
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from plyer import notification

# Set paths
DOWNLOADS_DIR = os.path.expanduser("~/Downloads/ebooks/")
KINDLE_DIR = os.path.join(DOWNLOADS_DIR, "kindle/")
MOBI_SAVE_DIR = os.path.join(KINDLE_DIR, "mobi")  # Folder to save converted MOBI files
PROCESSED_DIR = os.path.join(DOWNLOADS_DIR, "processed/")

# Create directories if they don't exist
for path in [DOWNLOADS_DIR, KINDLE_DIR, MOBI_SAVE_DIR, PROCESSED_DIR]:
    os.makedirs(path, exist_ok=True)

# Logging setup
logging.basicConfig(filename="conversion.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# Kindle email setup
SENDER_EMAIL = "dennisolondo@gmail.com"
KINDLE_EMAIL = "dennisolondo_SnR56l@kindle.com"
EMAIL_PASSWORD = "ouqd oycq psqv wplw"

def get_converted_filename(original_filename):
    """Return a standardized MOBI filename based on the original."""
    base = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1][1:].lower()
    return f"{base}_{ext}.mobi"

def send_file(file_path):
    """Send a file via email to the Kindle."""
    try:
        msg = EmailMessage()
        msg["From"] = SENDER_EMAIL
        msg["To"] = KINDLE_EMAIL
        msg["Subject"] = "Kindle Upload"
        msg.set_content("Here is your book!")
        with open(file_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="application",
                               subtype="octet-stream", filename=os.path.basename(file_path))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info(f"✅ Sent: {file_path}")
        print(f"✅ Sent: {file_path}")
    except Exception as e:
        logging.error(f"❌ Failed to send {file_path}: {e}")
        print(f"❌ Failed to send {file_path}: {e}")

def is_valid_file(file_path, min_size=1024):
    """Return True if file exists and its size exceeds min_size (default 1KB)."""
    return os.path.exists(file_path) and os.path.getsize(file_path) > min_size

def convert_to_mobi(input_path, output_path):
    """Force conversion using Calibre's ebook-convert tool."""
    retries = 3
    while retries > 0:
        try:
            subprocess.check_call(["ebook-convert", input_path, output_path])
            if is_valid_file(output_path):
                logging.info(f"✅ Conversion succeeded: {input_path} -> {output_path}")
                return True
            else:
                logging.error(f"❌ Conversion produced invalid file: {output_path}")
        except subprocess.CalledProcessError as e:
            logging.error(f"❌ Conversion error for {input_path}: {str(e)}")
        except Exception as e:
            logging.error(f"❌ Unexpected error for {input_path}: {str(e)}")
        retries -= 1
        time.sleep(5)
    return False

def process_file(f):
    """Process a file from DOWNLOADS_DIR:
       - If it's PDF or EPUB: send original, convert to MOBI (saved in MOBI_SAVE_DIR) but do NOT email the MOBI.
       - If it's already MOBI, do not send email.
    """
    full_path = os.path.join(DOWNLOADS_DIR, f)
    ext = os.path.splitext(f)[1][1:].lower()
    
    if ext not in ['pdf', 'epub', 'mobi']:
        return

    # For PDF and EPUB, send original via email.
    if ext in ['pdf', 'epub']:
        print(f"\n📤 Sending original: {f}")
        send_file(full_path)
        # Then convert to MOBI and save it (do not send by email).
        mobi_filename = get_converted_filename(f)
        mobi_path = os.path.join(MOBI_SAVE_DIR, mobi_filename)
        # Remove any pre-existing MOBI file for a fresh conversion.
        if os.path.exists(mobi_path):
            try:
                os.remove(mobi_path)
                logging.info(f"Removed old MOBI: {mobi_path}")
            except Exception as e:
                logging.error(f"Failed to remove {mobi_path}: {e}")
        print(f"\n📖 Converting {f} to MOBI...")
        if convert_to_mobi(full_path, mobi_path):
            logging.info(f"✅ MOBI saved: {mobi_filename} in {MOBI_SAVE_DIR}")
            print(f"✅ MOBI saved: {mobi_filename} in {MOBI_SAVE_DIR}")
        else:
            print(f"\n🚨 Conversion failed for {f}.")
    elif ext == 'mobi':
        # For files already in MOBI, do not send email.
        print(f"\n📂 {f} is already MOBI. Not sending via email.")

    # Finally, move the processed original to PROCESSED_DIR.
    try:
        shutil.move(full_path, os.path.join(PROCESSED_DIR, f))
        logging.info(f"Moved original file to processed: {f}")
    except Exception as e:
        logging.error(f"Failed to move {f} to processed folder: {e}")

def process_all_files():
    """Process all files in DOWNLOADS_DIR one at a time."""
    files = [f for f in os.listdir(DOWNLOADS_DIR) if os.path.isfile(os.path.join(DOWNLOADS_DIR, f))]
    for f in tqdm(files, desc="Processing all files"):
        process_file(f)

class Watcher:
    def __init__(self, folder):
        self.folder = folder
        self.observer = Observer()

    def run(self):
        event_handler = Handler()
        self.observer.schedule(event_handler, self.folder, recursive=False)
        self.observer.start()
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"\n🆕 New file detected: {event.src_path}")
            process_all_files()

if __name__ == "__main__":
    print("📚 Kindle Converter is running... Drop files in 'Downloads/ebooks' to process!")
    w = Watcher(DOWNLOADS_DIR)
    try:
        w.run()
    except Exception as e:
        logging.error(f"🚨 Fatal error: {str(e)}")
        print(f"🚨 Fatal error: {str(e)}")
