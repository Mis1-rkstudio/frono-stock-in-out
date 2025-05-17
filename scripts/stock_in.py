

# This file should only read only






# import os
# import time
# from collections import defaultdict
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.action_chains import ActionChains
# from selenium.webdriver.common.keys import Keys
# from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
# from functools import wraps

# from helper.browser_manager import create_driver
# from helper.common_utils import load_credentials, log
# from helper.fronocloud_login import login

# from google.oauth2 import service_account
# from googleapiclient.discovery import build



# # Timeouts and delays
# DEFAULT_TIMEOUT = 10
# DEFAULT_DELAY = 1
# MAX_RETRIES = 3


# def get_google_credentials():
#     """
#     Get Google credentials from environment or service account file.
#     Returns service account credentials for Google Sheets API.
#     """
#     if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
#         if os.path.exists("service_account_key.json"):
#             os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "service_account_key.json"
#             log("✅ Set GOOGLE_APPLICATION_CREDENTIALS for local run.")
#         else:
#             raise EnvironmentError("No Google credentials found. Please set GOOGLE_APPLICATION_CREDENTIALS or provide service_account_key.json")

#     return service_account.Credentials.from_service_account_file(
#         os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
#         scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
#     )

# def fetch_items_from_sheet():
#     """
#     Fetch items data from a Google Sheet.
#     The sheet should have columns: Design No., Unit, HSN Code, Colors, Sizes
#     Colors and Sizes should be comma-separated values in their respective cells.
#     """
#     try:
#         # Get credentials and build service
#         credentials = get_google_credentials()
#         service = build('sheets', 'v4', credentials=credentials)

#         # The ID of the spreadsheet to retrieve data from
#         SPREADSHEET_ID = os.environ.get('ITEMS_SPREADSHEET_ID')
#         if not SPREADSHEET_ID:
#             raise EnvironmentError("ITEMS_SPREADSHEET_ID environment variable not set")

#         # The range of the sheet to retrieve data from (e.g., 'Sheet1!A2:E')
#         RANGE_NAME = 'Sheet2!A2:F'  # Assuming headers are in row 1
        
#         # Call the Sheets API
#         result = service.spreadsheets().values().get(
#             spreadsheetId=SPREADSHEET_ID,
#             range=RANGE_NAME
#         ).execute()

#         values = result.get('values', [])
#         if not values:
#             log("No data found in the spreadsheet.")
#             return []

#         # Process the data
#         items = []
#         for row in values:
#             if len(row) > 2:  # Ensure we have all required columns
#                 item = {
#                     'Design No.': row[0],
#                     'Color': row[1],
#                     'Size': row[2],
#                     'Qty': row[3],
#                     'Price': row[4],
#                     'Stock In / Out': row[5]
#                 }
#                 items.append(item)

#         log(f"Successfully fetched {len(items)} items from Google Sheet")
#         return items

#     except Exception as e:
#         log(f"Error fetching items from Google Sheet: {e}")
#         return []
# print(fetch_items_from_sheet())
# def merge_items(raw_items):
#     merged = defaultdict(lambda: {
#         'Unit': 'PCS',
#         'HSN Code': '123456',
#         'Colors': set(),
#         'Sizes': set()
#     })

#     for item in raw_items:
#         design = item['Design No.']
#         merged[design]['Colors'].update(item.get('Colors', [])) # type: ignore
#         merged[design]['Sizes'].update(item.get('Sizes', [])) # type: ignore

#     # Convert sets to sorted lists and build final list
#     final_items = []
#     for design, data in merged.items():
#         final_items.append({
#             'Design No.': design,
#             'Unit': data['Unit'],
#             'HSN Code': data['HSN Code'],
#             'Colors': sorted(data['Colors']),
#             'Sizes': sorted(data['Sizes'])
#         })

#     return final_items

# def design_exists(driver, design_no):
#     try:
#         # Clear and enter the design number in the search field
#         search_input = WebDriverWait(driver, 5).until(
#             EC.presence_of_element_located((By.XPATH, '//input[@id="globalSearch"]'))
#         )
#         search_input.clear()
#         search_input.send_keys(design_no)
#         search_input.send_keys(Keys.ENTER)

#         time.sleep(2)  # Small delay for search results to load

#         # Check if the design number appears in the first row
#         # result_xpath = f"//td[contains(text(), '{design_no}')]"
#         result_xpath = f"//*[@id='pn_id_3-table']/tbody/tr/td/div[contains(text(), '{design_no}')]"
#         WebDriverWait(driver, 5).until(
#             EC.presence_of_element_located((By.XPATH, result_xpath))
#         )
#         return True
#     except:
#         return False


# def retry_on_failure(max_attempts=3, delay=1):
#     def decorator(func):
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             attempts = 0
#             while attempts < max_attempts:
#                 try:
#                     return func(*args, **kwargs)
#                 except (TimeoutException, StaleElementReferenceException) as e:
#                     attempts += 1
#                     if attempts == max_attempts:
#                         raise e
#                     time.sleep(delay)
#             return None
#         return wrapper
#     return decorator

# @retry_on_failure(max_attempts=3)
# def wait_and_click(driver, xpath, timeout=10):
#     element = WebDriverWait(driver, timeout).until(
#         EC.element_to_be_clickable((By.XPATH, xpath))
#     )
#     element.click()
#     return element

# @retry_on_failure(max_attempts=3)
# def wait_and_send_keys(driver, xpath, keys, timeout=10):
#     element = WebDriverWait(driver, timeout).until(
#         EC.presence_of_element_located((By.XPATH, xpath))
#     )
#     element.clear()
#     element.send_keys(keys)
#     return element


# # def fill_color_entries(driver, data_list):
# #     """
# #     Fill qty and price inputs based on color blocks in the UI
# #     """
# #     # Normalize color order based on actual DOM headings
# #     color_blocks = driver.find_elements(By.XPATH, "//div[normalize-space(text()) and following::input[contains(@id, 'setqty')]]")

# #     color_to_index = {}
# #     for idx, block in enumerate(color_blocks):
# #         color_text = block.text.strip().upper()
# #         if color_text:
# #             color_to_index[color_text] = idx

# #     for entry in data_list:
# #         color = entry['Color'].strip().upper()
# #         qty = entry['Qty']
# #         price = entry['Price']

# #         index = color_to_index.get(color)
# #         if index is None:
# #             print(f"❌ Couldn't find UI block for color: {color}")
# #             continue

# #         try:
# #             qty_input = driver.find_element(By.ID, f"setqty{index}")
# #             price_input = driver.find_element(By.ID, f"costPrice{index}")

# #             qty_input.clear()
# #             qty_input.send_keys(str(qty))

# #             price_input.clear()
# #             price_input.send_keys(str(price))

# #             print(f"✅ Filled {color} — Qty: {qty}, Price: {price}")
# #         except Exception as e:
# #             print(f"❌ Error filling inputs for {color} at index {index}: {e}")




# def addNewItem(location):
#     username, password = load_credentials(location)
#     driver = create_driver()
#     actions = ActionChains(driver)
#     failed_items = []
#     success_count = 0

#     try:
#         # Fetch items to add
#         items_to_add = fetch_items_from_sheet()

#         if not items_to_add:
#             log("No new items to add")
#             return "No items to add"

#         log(f"Starting to process {len(items_to_add)} items...")
#         login(driver, username, password)

#         log("Navigating to Items page...")
#         time.sleep(DEFAULT_DELAY)
#         driver.get(driver.current_url.replace("/dashboard", "/stockinout"))
        
#         time.sleep(DEFAULT_DELAY + 1)
#         wait_and_click(driver, f"//select[@id='basicSelect']/option[text()='Stock In']")

#         time.sleep(DEFAULT_DELAY + 1)
#         # Click Add New Stock button for each item
#         wait_and_click(driver, "//button[contains(text(), ' Add New Stock')]")
#         time.sleep(DEFAULT_DELAY + 1)

#         # Process each item
#         for item in items_to_add:
#             try:
#                 log(f"Processing item: {item['Design No.']}")
                
                
#                 # Enter design number
#                 color_input = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'P00')))
#                 color_input.clear()
#                 color_input.send_keys(item['Design No.'])

#                 actions.send_keys(Keys.ENTER).perform()
#                 time.sleep(DEFAULT_DELAY)
#                 actions.send_keys(Keys.SPACE).perform()
#                 time.sleep(DEFAULT_DELAY)

#                 # -------------------------------------------------------------------------------------------------------------------
#                 # Locate the <span> element with the exact text
#                 span_element = driver.find_element(By.XPATH, f"//span[normalize-space(text())='{item['Design No.']}']")

#                 # Get the parent of the span
#                 parent = span_element.find_element(By.XPATH, "./..")

#                 # Get all child <span> elements under the same parent
#                 sibling_spans = parent.find_elements(By.TAG_NAME, "span")

#                 # Click all siblings one by one
#                 for i, sibling in enumerate(sibling_spans):
#                     try:
#                         sibling_text = sibling.text.strip()
#                         print(f"Checking sibling {i}: {sibling_text}")
                        
#                         # Only proceed if the sibling text matches the item's color
#                         if sibling_text == item['Color']:
#                             print(f"Found matching color: {sibling_text}")
#                             driver.execute_script("arguments[0].scrollIntoView(true);", sibling)
#                             sibling.click()
#                             time.sleep(0.5)

#                             # Fill in quantity and price with setqty in the id value 
#                             print("====================================", item['Qty'], i-2)
#                             qty = WebDriverWait(driver, 5).until(
#                                 EC.presence_of_element_located((By.ID, f"setqty{i-2}"))
#                             )
#                             qty.clear()
#                             qty.send_keys(item['Qty'] + Keys.ENTER)
        
#                             print("====================================", item['Price'], i-2)
#                             price = WebDriverWait(driver, 5).until(
#                                 EC.presence_of_element_located((By.ID, f"costPrice{i-2}"))
#                             )
#                             price.clear()
#                             price.send_keys(item['Price'] + Keys.ENTER)
                            
#                         else:
#                             print(f"Skipping non-matching color: {sibling_text}")

#                     except Exception as e:
#                         print(f"❌ Could not process span {i}: {e}")

#                 # -------------------------------------------------------------------------------------------------------------------
#                 time.sleep(DEFAULT_DELAY)
#                 WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, 'P03'))).click()
#                 time.sleep(DEFAULT_DELAY)
#                 actions.send_keys(Keys.SPACE).perform()
#                 time.sleep(DEFAULT_DELAY + 5)

#                 # Wait for success message or error
#                 try:
#                     WebDriverWait(driver, 5).until(
#                         EC.presence_of_element_located((By.XPATH, "//div[@role='alert' and @aria-label='Successfully added']"))
#                     )
#                     log(f"✅ Successfully stock in for item: {item['Design No.']}")
#                     success_count += 1
#                 except:
#                     log(f"⚠️ Stock in for item {item['Design No.']} may not have been successfully done")
#                     failed_items.append(item['Design No.'])

#             except Exception as e:
#                 log(f"❌ Error processing item {item['Design No.']}: {e}")
#                 failed_items.append(item['Design No.'])
#                 continue

#         summary = f"Processed {len(items_to_add)} items: {success_count} successful, {len(failed_items)} failed"
#         if failed_items:
#             summary += f"\nFailed items: {', '.join(failed_items)}"
#         print(summary)

#     except Exception as e:
#         log(f"❌ Error during stock in process: {e}")
#         return f"Error: {e}"

#     finally:
#         log("Closing browser...")
#         driver.quit()

# addNewItem("kolkata")
