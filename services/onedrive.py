"""
services/onedrive.py

Handles OneDrive/SharePoint interactions using Guest Cookies via requests.
"""
import os
import requests
import urllib.parse

def get_sharepoint_config():
    share_url = os.environ.get("ONEDRIVE_SHARE_URL")
    # Using the hardcoded URLs provided in the upload/download scripts
    base_url = "https://horusuni-my.sharepoint.com"
    site_url = f"{base_url}/personal/aelshafee_horus_edu_eg"
    folder_path = "/personal/aelshafee_horus_edu_eg/Documents/ESSIC_Docs"
    return share_url, base_url, site_url, folder_path

def upload_file_to_share(local_filepath: str, dest_filename: str) -> bool:
    """
    Uploads a local file to the shared OneDrive folder using Guest Cookies.
    Returns True on success, False on failure.
    """
    share_url, base_url, site_url, folder_path = get_sharepoint_config()
    
    if not share_url:
        print("[Upload Error] ONEDRIVE_SHARE_URL not configured.")
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
    })

    try:
        # STEP 1: Fetch guest cookies
        initial_response = session.get(share_url)
        initial_response.raise_for_status()

        # STEP 2: Generate fresh x-requestdigest token
        context_info_url = f"{site_url}/_api/contextinfo"
        ctx_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/json;odata=verbose'
        }
        ctx_response = session.post(context_info_url, headers=ctx_headers)
        if ctx_response.status_code != 200:
            print("[Upload Error] Failed to get authorization token.")
            print(ctx_response.text)
            return False

        request_digest = ctx_response.json()['d']['GetContextWebInformation']['FormDigestValue']

        # STEP 3: Upload the File
        encoded_folder = urllib.parse.quote(folder_path, safe='')
        encoded_filename = urllib.parse.quote(dest_filename, safe='')

        upload_endpoint = (
            f"{site_url}/_api/web/GetFolderByServerRelativePath(DecodedUrl=@a1)/Files/AddUsingPath"
            f"(DecodedUrl=@a2,AutoCheckoutOnInvalidData=@a3)"
            f"?@a1=%27{encoded_folder}%27&@a2=%27{encoded_filename}%27&@a3=true"
        )

        upload_headers = {
            'Accept': 'application/json;odata=verbose',
            'Content-Type': 'application/octet-stream',
            'X-RequestDigest': request_digest
        }

        with open(local_filepath, 'rb') as f:
            upload_response = session.post(upload_endpoint, headers=upload_headers, data=f)

        if upload_response.status_code in [200, 201, 202]:
            return True
        else:
            print(f"[Upload Error] {upload_response.status_code}")
            print(upload_response.text)
            return False
            
    except Exception as e:
        print(f"[Upload Exception] {e}")
        return False


def download_file_from_share(target_file_name: str, local_save_path: str) -> bool:
    """
    Downloads a file from SharePoint folder using Guest Cookies.
    """
    share_url, base_url, site_url, folder_path = get_sharepoint_config()
    
    if not share_url:
        print("[Download Error] ONEDRIVE_SHARE_URL not configured.")
        return False
        
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    })
    
    try:
        # STEP 1: Acquire Guest Cookies
        response = session.get(share_url)
        if 'FedAuth' not in session.cookies:
            print("[Download Error] The FedAuth cookie was not set. Check your sharing link.")
            return False

        # STEP 2: Download the File
        file_path = f"{folder_path}/{target_file_name}"
        encoded_file_path = urllib.parse.quote(file_path, safe='')
        
        download_endpoint = (
            f"{site_url}/_api/web/GetFileByServerRelativePath(DecodedUrl=@v)/$value"
            f"?@v=%27{encoded_file_path}%27"
        )

        download_response = session.get(download_endpoint, stream=True)
        if download_response.status_code == 200:
            with open(local_save_path, 'wb') as f:
                for chunk in download_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            print(f"[Download Error] {download_response.status_code}")
            print(download_response.text)
            return False
            
    except Exception as e:
        print(f"[Download Exception] {e}")
        return False


# app.py calls upload_file_to_onedrive(...), but this module only defined
# upload_file_to_share(...) — that mismatch would raise an ImportError the
# first time a document gets auto-approved. Alias it so the existing call
# site in app.py keeps working without changes.
upload_file_to_onedrive = upload_file_to_share