# api/function_app.py
import logging
import os
import json
import requests

import azure.functions as func
from .beyond_trust_client import BeyondTrustClient

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

    try:
        # Initialize the API client which also validates credentials and handles token caching
        client = BeyondTrustClient(beyond_trust_site_url, api_key, api_secret)

        # Fetch data using the client methods
        jump_group_map = client.get_jump_groups()
        all_installers = client.get_all_installers()

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
                if sorted_installers:
                    latest_installer_for_group = sorted_installers[0]

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

        return func.HttpResponse(
            json.dumps(installer_details_output),
            mimetype="application/json",
            status_code=200
        )

    except ValueError as e:
        # Catches missing environment variables from the client's __init__
        logging.error(f"Configuration Error: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), mimetype="application/json", status_code=500)
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_details = e.response.text
        logging.error(f"HTTP Error: {status_code} - {error_details}")
        return func.HttpResponse(
            json.dumps({"error": "An API request to BeyondTrust failed.", "details": error_details}),
            mimetype="application/json",
            status_code=status_code
        )
    except requests.exceptions.RequestException as e:
        # Catch other request-related errors like connection errors, timeouts, etc.
        logging.error(f"A network error occurred: {e}")
        return func.HttpResponse(
            json.dumps({"error": "A network error occurred while communicating with the BeyondTrust API."}),
            mimetype="application/json",
            status_code=503  # Service Unavailable
        )
    except Exception:
        # Use logging.exception to include stack trace information for any other errors
        logging.exception("An unexpected internal error occurred.")
        return func.HttpResponse(
            json.dumps({"error": "An unexpected internal error occurred."}),
            mimetype="application/json",
            status_code=500
        )

@app.route(route="CreateJumpGroup", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def CreateJumpGroup(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function to create a Jump Group processed a request.')

    try:
        req_body = req.get_json()
        client_code = req_body.get('client_code')
        client_name = req_body.get('client_name')

        if not client_code or not client_name:
            return func.HttpResponse(
                json.dumps({"error": "Please provide both 'client_code' and 'client_name' in the request body."}),
                mimetype="application/json",
                status_code=400
            )

    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON format in request body."}),
            mimetype="application/json",
            status_code=400
        )

    # Retrieve BeyondTrust credentials from environment variables
    beyond_trust_site_url = os.environ.get('BeyondTrustSiteUrl')
    api_key = os.environ.get('BeyondTrustApiKey')
    api_secret = os.environ.get('BeyondTrustApiSecret')

    try:
        client = BeyondTrustClient(beyond_trust_site_url, api_key, api_secret)

        jump_group_name = f"{client_code}_{client_name}"
        
        # Define the permissions to be set
        permissions_to_set = {
            "BBB General Members": {"start_session": True, "manage": True},
            "BBB Bomgar Administrators": {"administrator": True}
        }

        created_group = client.create_jump_group_with_permissions(
            name=jump_group_name,
            code_name=jump_group_name, # Often the same as the name
            permissions_map=permissions_to_set
        )

        return func.HttpResponse(
            json.dumps(created_group),
            mimetype="application/json",
            status_code=201 # 201 Created is appropriate here
        )

    except ValueError as e:
        logging.error(f"Configuration Error: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), mimetype="application/json", status_code=500)
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code
        error_details = e.response.text
        logging.error(f"HTTP Error during Jump Group creation: {status_code} - {error_details}")
        return func.HttpResponse(
            json.dumps({"error": "An API request to BeyondTrust failed during Jump Group creation.", "details": error_details}),
            mimetype="application/json",
            status_code=status_code
        )
    except Exception:
        logging.exception("An unexpected internal error occurred during Jump Group creation.")
        return func.HttpResponse(
            json.dumps({"error": "An unexpected internal error occurred."}),
            mimetype="application/json",
            status_code=500
        )