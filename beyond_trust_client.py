import logging
import base64
import requests
import time

class BeyondTrustClient:
    """
    A client for interacting with the BeyondTrust API, with built-in token caching.
    """
    def __init__(self, site_url, api_key, api_secret):
        if not all([site_url, api_key, api_secret]):
            raise ValueError("BeyondTrust credentials (site_url, api_key, api_secret) must be provided.")

        self.site_url = site_url
        self.api_key = api_key
        self.api_secret = api_secret
        
        self._access_token = None
        self._token_type = None
        self._token_expires_at = 0
        self.session = requests.Session() # Use a session for connection pooling

    def _get_access_token(self):
        """
        Retrieves an access token, using a cached token if available and not expired.
        A 60-second buffer is used to prevent using a token right before it expires.
        """
        if self._access_token and time.time() < self._token_expires_at - 60:
            logging.info("Using cached BeyondTrust access token.")
            return self._access_token, self._token_type

        logging.info("No valid cached token. Requesting a new BeyondTrust access token.")
        auth_url = f"{self.site_url}/oauth2/token"
        auth_string = f"{self.api_key}:{self.api_secret}"
        base64_auth_string = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

        headers = {
            "Authorization": f"Basic {base64_auth_string}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        body = {"grant_type": "client_credentials"}

        response = self.session.post(auth_url, headers=headers, data=body)
        response.raise_for_status()
        token_data = response.json()

        self._access_token = token_data.get('access_token')
        self._token_type = token_data.get('token_type', 'Bearer')
        expires_in = token_data.get('expires_in', 3600) # Default to 1 hour
        self._token_expires_at = time.time() + expires_in

        if not self._access_token:
            raise ConnectionError("Failed to obtain access token from BeyondTrust.")

        logging.info("Successfully obtained and cached a new access token.")
        return self._access_token, self._token_type

    def _make_api_request(self, url, method='GET', params=None):
        """Helper method to make authenticated API requests."""
        access_token, token_type = self._get_access_token()
        headers = {
            "Authorization": f"{token_type} {access_token}",
            "Accept": "application/json"
        }
        response = self.session.request(method, url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def get_jump_groups(self):
        """Fetches all Jump Groups and returns them as a dict mapping ID to name."""
        logging.info("Retrieving all Jump Groups.")
        api_url = f"{self.site_url}/api/config/v1/jump-group"
        all_jump_groups = self._make_api_request(api_url)
        logging.info(f"Successfully retrieved {len(all_jump_groups)} Jump Groups.")
        return {group['id']: group['name'] for group in all_jump_groups}

    def get_all_installers(self):
        """Fetches all Jump Client Installers, handling pagination."""
        logging.info("Retrieving all Jump Client Installers with pagination.")
        api_url = f"{self.site_url}/api/config/v1/jump-client/installer"
        all_installers = []
        current_page = 1
        per_page = 100

        while True:
            logging.info(f"Fetching installers page {current_page}...")
            params = {"per_page": per_page, "current_page": current_page}
            page_data = self._make_api_request(api_url, params=params)

            if not isinstance(page_data, list):
                logging.error(f"Expected a list of installers but got {type(page_data)}. Stopping.")
                break

            if not page_data:
                logging.info("No more installers found. End of data.")
                break
            
            all_installers.extend(page_data)
            logging.info(f"Retrieved {len(page_data)} installers. Total so far: {len(all_installers)}.")

            if len(page_data) < per_page:
                logging.info("Last page of installers reached.")
                break
            
            current_page += 1
        
        logging.info(f"Successfully retrieved a total of {len(all_installers)} installers.")
        return all_installers

    def _find_group_policy_by_name(self, group_name):
        """Finds a group policy ID by its name, handling pagination."""
        logging.info(f"Searching for group policy with name: '{group_name}'")
        api_url = f"{self.site_url}/api/config/v1/group-policy"
        current_page = 1
        per_page = 100

        while True:
            params = {"per_page": per_page, "current_page": current_page}
            page_data = self._make_api_request(api_url, params=params)
            
            if not isinstance(page_data, list):
                logging.error(f"Expected a list of group policies but got {type(page_data)}. Stopping search.")
                return None

            for policy in page_data:
                if policy.get('name') == group_name:
                    logging.info(f"Found group policy '{group_name}' with ID: {policy.get('id')}")
                    return policy

            if len(page_data) < per_page:
                logging.warning(f"Group policy '{group_name}' not found after searching all pages.")
                return None
            
            current_page += 1

    def create_jump_group_with_permissions(self, name, code_name, permissions_map):
        """
        Creates a Jump Group and assigns permissions to specified user groups.
        :param name: The display name of the Jump Group.
        :param code_name: The code name of the Jump Group.
        :param permissions_map: A dict mapping group names to their permission sets.
                                e.g., {'Group Name': {'is_admin': True}}
        """
        # Step 1: Create the Jump Group
        logging.info(f"Creating Jump Group with name: '{name}'")
        jump_group_url = f"{self.site_url}/api/config/v1/jump-group"
        jump_group_payload = {"name": name, "code_name": code_name}
        created_jump_group = self._make_api_request(jump_group_url, method='POST', params=jump_group_payload)
        jump_group_id = created_jump_group.get('id')
        logging.info(f"Successfully created Jump Group with ID: {jump_group_id}")

        # Step 2: Find group policies and assign permissions
        for group_name, permissions in permissions_map.items():
            group_policy = self._find_group_policy_by_name(group_name)
            if not group_policy:
                logging.error(f"Could not assign permissions because group policy '{group_name}' was not found. Skipping.")
                continue
            
            group_policy_id = group_policy.get('id')
            
            logging.info(f"Assigning permissions to Jump Group ID {jump_group_id} for Group Policy ID {group_policy_id} ({group_name})")
            
            permission_url = f"{self.site_url}/api/config/v1/jump-group/{jump_group_id}/group-policy"
            permission_payload = {
                "group_policy_id": group_policy_id,
                "session_start_permission": permissions.get("start_session", False),
                "session_manage_permission": permissions.get("manage", False),
                "is_admin": permissions.get("administrator", False)
            }
            
            self._make_api_request(permission_url, method='POST', params=permission_payload)
            logging.info(f"Successfully assigned permissions for '{group_name}'.")

        return created_jump_group