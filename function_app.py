# api/function_app.py
import logging
import os
import json
import base64
import requests # Used for making HTTP requests

import azure.functions as func

# Initialize the Function App instance 
app = func.FunctionApp()

# Define your HTTP trigger function using a decorator
@app.route(route="GetBeyondTrustData", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def GetBeyondTrustData(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    # Retrieve BeyondTrust credentials from environment variables
    beyond_trust_site_url = os.environ.get('BeyondTrustSiteUrl')
    api_key = os.environ.get('BeyondTrustApiKey')
    api_secret = os.environ.get('BeyondTrustApiSecret')

    # --- Basic Variable Check ---
    if not beyond_trust_site_url or not api_key or not api_secret:
        error_msg = "Error: BeyondTrust credentials environment variables are not set."
        logging.error(error_msg)
        return func.HttpResponse(
            json.dumps({"error": error_msg}),
            mimetype="application/json",
            status_code=500
        )

    # --- Authentication Step ---
    auth_url = f"{beyond_trust_site_url}/oauth2/token"
    auth_string = f"{api_key}:{api_secret}"
    base64_auth_string = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    auth_headers = {
        "Authorization": f"Basic {base64_auth_string}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    auth_body = {"grant_type": "client_credentials"}

    logging.info(f"Attempting to obtain access token from: {auth_url}")

    try:
        auth_response = requests.post(auth_url, headers=auth_headers, data=auth_body)
        auth_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        auth_token_response = auth_response.json()

        access_token = auth_token_response.get('access_token')
        token_type = auth_token_response.get('token_type')

        if not access_token:
            error_details = auth_token_response.get('error_description', auth_token_response.get('error', 'Unknown authentication error.'))
            logging.error(f"Failed to obtain access token. Details: {error_details}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to obtain access token.", "details": error_details}),
                mimetype="application/json",
                status_code=401
            )
        logging.info("Successfully obtained access token.")

        # --- Fetch All Jump Groups ---
        jump_group_api_url = f"{beyond_trust_site_url}/api/config/v1/jump-group"
        jump_group_headers = {
            "Authorization": f"{token_type} {access_token}",
            "Accept": "application/json"
        }
        logging.info(f"Attempting to retrieve all Jump Groups from: {jump_group_api_url}")
        jump_groups_response = requests.get(jump_group_api_url, headers=jump_group_headers)
        jump_groups_response.raise_for_status()
        all_jump_groups = jump_groups_response.json()
        logging.info(f"Successfully retrieved {len(all_jump_groups)} Jump Groups.")

        jump_group_map = {group['id']: group['name'] for group in all_jump_groups}

        # --- Fetch All Jump Client Installers ---
        base_installers_api_url = f"{beyond_trust_site_url}/api/config/v1/jump-client/installer"
        installer_list_headers = {
            "Authorization": f"{token_type} {access_token}",
            "Accept": "application/json"
        }
        
        all_installers_data = []
        current_page = 1 # API uses 1-based indexing for pages
        per_page = 100  # Equivalent to limit

        logging.info(f"Attempting to retrieve ALL Jump Client Installers from: {base_installers_api_url} with pagination (per_page={per_page}).")

        while True:
            paginated_url = f"{base_installers_api_url}?per_page={per_page}&current_page={current_page}"
            logging.info(f"Fetching installers page {current_page}: {paginated_url}")
            
            page_response = requests.get(paginated_url, headers=installer_list_headers)
            page_response.raise_for_status()
            current_page_installers = page_response.json()

            if not isinstance(current_page_installers, list):
                logging.error(f"Expected a list of installers but got {type(current_page_installers)}. Stopping.")
                # Potentially raise an error or return an appropriate HTTP response
                break 

            if not current_page_installers: # No more installers on this page
                logging.info("No more installers found on this page. End of data.")
                break
            
            all_installers_data.extend(current_page_installers)
            logging.info(f"Retrieved {len(current_page_installers)} installers from this page. Total retrieved so far: {len(all_installers_data)}.")

            if len(current_page_installers) < per_page: # Last page reached
                logging.info("Last page of installers reached.")
                break
            
            current_page += 1 # Prepare for the next page

        all_installers = all_installers_data
        logging.info(f"Successfully retrieved a total of {len(all_installers)} Jump Client Installers after pagination.")

        installer_details_output = []
        if all_installers:
            logging.info("Processing and grouping Jump Client Installers...")
            installers_by_group = {}
            for installer in all_installers:
                group_id = installer.get('jump_group_id')
                if group_id not in installers_by_group:
                    installers_by_group[group_id] = []
                installers_by_group[group_id].append(installer)

            for group_id, installers_in_group in installers_by_group.items():
                jump_group_name = jump_group_map.get(group_id, f"Unknown Group (ID: {group_id})")

                sorted_installers = sorted(
                    installers_in_group,
                    key=lambda x: x.get('expiration_timestamp', ''),
                    reverse=True
                )

                # Select only the installer with the latest expiration date for this group
                if sorted_installers: # Check if there are any installers for this group
                    latest_installer_for_group = sorted_installers[0] # The first one is the latest due to reverse sort
                    
                    installer_id = latest_installer_for_group.get('installer_id')
                    windows_download_url = f"{beyond_trust_site_url}/download_client_connector?jc={installer_id}&p=winNT-64-msi"
                    mac_download_url = f"{beyond_trust_site_url}/download_client_connector?jc={installer_id}&p=mac-osx-x86"

                    installer_details_output.append({
                        "JumpGroupName": jump_group_name,
                        "InstallerName": latest_installer_for_group.get('name'),
                        "InstallerID": installer_id,
                        "ExpirationDate": latest_installer_for_group.get('expiration_timestamp'),
                        "WindowsDownloadURL": windows_download_url,
                        "MacDownloadURL": mac_download_url
                    })
            logging.info(f"Finished processing installers. Total items in output: {len(installer_details_output)}")
        else:
            logging.info("No Jump Client Installers found or the response was empty.")

        # Return the data as JSON
        return func.HttpResponse(
            json.dumps(installer_details_output),
            mimetype="application/json",
            status_code=200
        )

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_details = e.response.text
        logging.error(f"HTTP Error: {status_code} - {error_details}")
        return func.HttpResponse(
            json.dumps({"error": f"API request failed: {e}", "details": error_details}),
            mimetype="application/json",
            status_code=status_code
        )
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"An unexpected error occurred: {e}"}),
            mimetype="application/json",
            status_code=500
        )