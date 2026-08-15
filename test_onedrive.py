import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env")

sys.path.append(os.path.join(os.path.dirname(__file__), "flask"))

from services.onedrive import upload_file_to_share

with open("test_upload.txt", "w") as f:
    f.write("Hello OneDrive!")

success = upload_file_to_share("test_upload.txt", "test_upload.txt")
print(f"Upload success: {success}")
