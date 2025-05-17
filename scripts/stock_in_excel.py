import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from functools import wraps

from scripts.helper.browser_manager import create_driver
from scripts.helper.common_utils import load_credentials, log
from scripts.helper.fronocloud_login import login

from google.oauth2 import service_account
from googleapiclient.discovery import build



# Timeouts and delays
DEFAULT_TIMEOUT = 10
DEFAULT_DELAY = 1
MAX_RETRIES = 3


def get_google_credentials():
    """
    Get Google credentials from environment or service account file.
    Returns service account credentials for Google Sheets API.
    """
    if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        if os.path.exists("service_account_key.json"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service_account_key.json"
            log("✅ Set GOOGLE_APPLICATION_CREDENTIALS for local run.")
        else:
            raise EnvironmentError("No Google credentials found. Please set GOOGLE_APPLICATION_CREDENTIALS or provide service_account_key.json")

    return service_account.Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )

def fetch_items_from_sheet():
    """
    Fetch items data from a Google Sheet.
    The sheet should have columns: Design No., Unit, HSN Code, Colors, Sizes
    Colors and Sizes should be comma-separated values in their respective cells.
    """
    try:
        # Get credentials and build service
        credentials = get_google_credentials()
        service = build('sheets', 'v4', credentials=credentials)

        # The ID of the spreadsheet to retrieve data from
        SPREADSHEET_ID = os.environ.get('ITEMS_SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            raise EnvironmentError("ITEMS_SPREADSHEET_ID environment variable not set")

        # The range of the sheet to retrieve data from (e.g., 'Sheet1!A2:E')
        RANGE_NAME = 'Sheet2!A2:F'  # Assuming headers are in row 1
        
        # Call the Sheets API
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME
        ).execute()

        values = result.get('values', [])
        if not values:
            log("No data found in the spreadsheet.")
            return []

        # Process the data
        items = []
        for row in values:
            if len(row) > 2:  # Ensure we have all required columns
                item = {
                    'Design No.': row[0],
                    'Color': row[1],
                    'Size': row[2],
                    'Qty': row[3],
                    'Price': row[4],
                    'Stock In / Out': row[5]
                }
                items.append(item)

        log(f"Successfully fetched {len(items)} items from Google Sheet")
        return items

    except Exception as e:
        log(f"Error fetching items from Google Sheet: {e}")
        return []

# print(fetch_items_from_sheet())

def retry_on_failure(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except (TimeoutException, StaleElementReferenceException) as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise e
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_failure(max_attempts=3)
def wait_and_click(driver, xpath, timeout=10):
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )
    element.click()
    return element

@retry_on_failure(max_attempts=3)
def wait_and_send_keys(driver, xpath, keys, timeout=10):
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.XPATH, xpath))
    )
    element.clear()
    element.send_keys(keys)
    return element



def is_size_in_group(excel_size, sheet_size_group):
    """Check if a size falls within a size group (e.g., '38.0' is in '38-44')."""
    try:
        # Convert excel_size to float and round to nearest integer
        size = round(float(excel_size))
        
        # Parse the size group (e.g., '38-44' -> [38, 44])
        if '-' in sheet_size_group:
            start, end = map(int, sheet_size_group.split('-'))
            return start <= size <= end
        else:
            # If it's a single size, do exact match
            return size == int(sheet_size_group)
    except (ValueError, TypeError):
        return False

def read_excel_data(download_dir):
    """Read and process Excel file from the download directory."""
    try:
        # Remove all existing Excel files
        for file in os.listdir(download_dir):
            if file.endswith('.xlsx'):
                try:
                    os.remove(os.path.join(download_dir, file))
                    log(f"Removed file: {file}")
                except Exception as e:
                    log(f"Warning: Could not remove file {file}: {e}")
        
        time.sleep(4)  # Wait for new download

        # Check if new file was downloaded
        excel_files = [f for f in os.listdir(download_dir) if f.endswith('.xlsx')]
        if not excel_files:
            raise FileNotFoundError("No Excel file was downloaded after waiting")
            
        # Get and process the latest file
        latest_file = max(
            [os.path.join(download_dir, f) for f in excel_files],
            key=os.path.getctime
        )
        
        # Verify file exists and is readable
        if not os.path.exists(latest_file):
            raise FileNotFoundError(f"Downloaded file not found: {latest_file}")
            
        df = pd.read_excel(latest_file)
        if df.empty:
            raise ValueError("Excel file is empty")
            
        items = df.to_dict('records')
        log(f"Successfully read {len(items)} items from Excel file")
        return items, latest_file

    except Exception as e:
        log(f"❌ Error reading Excel file: {e}")
        raise

def update_excel_with_sheet_data(excel_data, sheet_data, excel_file_path):
    """Update Excel data with values from Google Sheet and save back to Excel."""
    try:
        if not excel_data:
            raise ValueError("No data in Excel file")
        if not sheet_data:
            raise ValueError("No data from Google Sheet")
            
        updated_data = []
        for excel_item in excel_data:
            # Find matching item from sheet data
            matching_item = next(
                (item for item in sheet_data if 
                item['Design No.'] == excel_item['Item Name'] 
                and item['Color'] == excel_item['Color Name'] 
                and is_size_in_group(excel_item['Size Name'], item['Size'])),
                None
            )
            
            if matching_item:
                # Update Stock Qty and Cost price
                excel_item['Stock Qty'] = matching_item['Qty']
                excel_item['Cost price'] = matching_item['Price']
                log(f"Updated item: {excel_item['Item Name']} - {excel_item['Color Name']} - {excel_item['Size Name']} (matched with size group {matching_item['Size']})")
            # else:
                # log(f"No match found for: {excel_item['Item Name']} - {excel_item['Color Name']} - {excel_item['Size Name']}")
            
            updated_data.append(excel_item)
            
        # Convert updated data back to DataFrame and save to Excel
        df = pd.DataFrame(updated_data)
        df.to_excel(excel_file_path, index=False)
        log(f"Updated Excel file saved: {excel_file_path}")
            
        log(f"Updated {len(updated_data)} items with sheet data")
        # return updated_data
        
    except Exception as e:
        log(f"❌ Error updating data: {e}")
        raise

def split_sheet_data(sheet_data):
    """Split sheet data into stock in and stock out items."""
    stock_in_items = []
    stock_out_items = []
    
    for item in sheet_data:
        # log(item)
        if item['Stock In / Out'].lower() == 'stock in':
            stock_in_items.append(item)
        elif item['Stock In / Out'].lower() == 'stock out':
            stock_out_items.append(item)
    
    log(f"Split sheet data: {len(stock_in_items)} items for stock in, {len(stock_out_items)} items for stock out")
    return stock_in_items, stock_out_items

def clear_excel_data(excel_file_path):
    """Clear quantity and price columns in the Excel file."""
    try:
        df = pd.read_excel(excel_file_path)
        # Clear Stock Qty and Cost price columns
        df['Stock Qty'] = ''
        df['Cost price'] = ''
        # Save back to the same file
        df.to_excel(excel_file_path, index=False)
        log("Cleared quantity and price columns in Excel file")
    except Exception as e:
        log(f"❌ Error clearing Excel data: {e}")
        raise

def get_or_download_template(driver, download_dir):
    """Get existing template or download new one if none exists."""
    excel_files = [f for f in os.listdir(download_dir) if f.endswith('.xlsx')]
    if excel_files:
        # Get the existing file
        excel_file_path = max(
            [os.path.join(download_dir, f) for f in excel_files],
            key=os.path.getctime
        )
        excel_data = pd.read_excel(excel_file_path).to_dict('records')
        log("Using existing template file")
        return excel_data, excel_file_path
    else:
        # Download new template
        wait_and_click(driver, "//button[contains(text(), 'Download Item File')]")
        time.sleep(DEFAULT_DELAY + 1)
        excel_data, excel_file_path = read_excel_data(download_dir)
        log("Downloaded new template file")
        return excel_data, excel_file_path

def process_stock(driver, stock_items, download_dir, stock_type):
    """Process stock in or stock out items based on stock_type."""
    try:
        # Switch to appropriate stock type
        wait_and_click(driver, f"//select[@id='basicSelect']/option[text()='{stock_type}']")
        time.sleep(DEFAULT_DELAY + 1)
        
        # Click Add New Stock button
        wait_and_click(driver, "//button[contains(text(), ' Add New Stock')]")
        time.sleep(DEFAULT_DELAY + 1)
        
        # Open menu and select Import Item Stock
        wait_and_click(driver, "//*[@data-original-title='Menu']")
        wait_and_click(driver, "//a[contains(text(), 'Import Item Stock')]")
        
        # Check for existing template
        excel_files = [f for f in os.listdir(download_dir) if f.endswith('.xlsx')]
        if not excel_files:
            # Download new template if none exists
            wait_and_click(driver, "//button[contains(text(), 'Download Item File')]")
            time.sleep(DEFAULT_DELAY + 1)
            excel_data, excel_file_path = read_excel_data(download_dir)
            log("Downloaded new template file")
        else:
            # Use existing template
            excel_file_path = max(
                [os.path.join(download_dir, f) for f in excel_files],
                key=os.path.getctime
            )
            excel_data = pd.read_excel(excel_file_path).to_dict('records')
            log("Using existing template file")
        
        # Clear existing data
        clear_excel_data(excel_file_path)
        
        # Update Excel with stock data
        update_excel_with_sheet_data(excel_data, stock_items, excel_file_path)
        
        # Upload the updated file
        time.sleep(2)
        log(f"Uploading {stock_type.lower()} file...")
        file_input = driver.find_element(By.ID, "stockitemimport")
        file_path = os.path.abspath(excel_file_path)
        file_input.send_keys(file_path)
        log(f"Uploaded {stock_type.lower()} file: {excel_file_path}")
        
        # Click upload button
        wait_and_click(driver, "//button[contains(text(), 'Upload file')]")
        time.sleep(DEFAULT_DELAY + 2)
        
    except Exception as e:
        log(f"❌ Error during {stock_type.lower()} process: {e}")
        raise

def stockInItem(location):
    username, password = load_credentials(location)
    
    # Create download directory if it doesn't exist
    download_dir = os.path.join(os.getcwd(), location, "stock_in_data")
    os.makedirs(download_dir, exist_ok=True)
    
    driver = create_driver(download_path=download_dir)

    try:
        login(driver, username, password)

        log("Navigating to Items page...")
        time.sleep(DEFAULT_DELAY)
        driver.get(driver.current_url.replace("/dashboard", "/stockinout"))
        
        # Get data from Google Sheet
        sheet_data = fetch_items_from_sheet()
        if not sheet_data:
            raise ValueError("No data received from Google Sheet")
            
        # Split data into stock in and stock out
        stock_in_items, stock_out_items = split_sheet_data(sheet_data)

# =====================================================================================
        # Process stock in items if any exist
        if stock_in_items:
            log("Processing stock in items...")
            process_stock(driver, stock_in_items, download_dir, "Stock In")
        
        # refresh the page
        driver.refresh()
        time.sleep(DEFAULT_DELAY + 2)

        # Process stock out items if any exist
        if stock_out_items:
            log("Processing stock out items...")
            process_stock(driver, stock_out_items, download_dir, "Stock Out")
# =====================================================================================
            
        log("✅ Stock in/out process completed successfully")
        
    except Exception as e:
        log(f"❌ Error during stock in/out process: {e}")
        return f"Error: {e}"

    finally:
        log("Closing browser...")
        driver.quit()
