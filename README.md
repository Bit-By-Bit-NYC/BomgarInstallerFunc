BeyondTrust Azure Function Documentation 🚀
This document provides a detailed explanation and reference for the provided Python code, which is designed to be deployed as an Azure Function. The script defines two separate HTTP trigger functions to interact with the BeyondTrust Privileged Remote Access API.

1. GetBeyondTrustData 📄
Function: This function retrieves and processes information about BeyondTrust Jump Client installers. It's designed to be a data source for other systems, like an Intune app deployment script.

Workflow:

Environment Variable Check: It first verifies that the necessary environment variables (BeyondTrustSiteUrl, BeyondTrustApiKey, BeyondTrustApiSecret) are set. These variables are crucial for authenticating with the BeyondTrust API.

OAuth 2.0 Authentication: It authenticates with the BeyondTrust API using a client_credentials grant type. It constructs an Authorization header with a Base64-encoded string of the api_key and api_secret.

Fetch Jump Groups: It makes an API call to .../api/config/v1/jump-group to get a list of all Jump Groups. This is used to map jump_group_id to jump_group_name later.

Fetch Jump Client Installers (with Pagination): It makes a series of API calls to .../api/config/v1/jump-client/installer. This API endpoint supports pagination, so the code iteratively fetches all pages of installers.

Data Processing: After collecting all installers, it performs the following:

Groups the installers by their jump_group_id.

Within each group, it sorts the installers by expiration_timestamp in descending order.

It selects only the single installer with the latest expiration date for each group.

Construct Output: It creates a JSON object for each selected installer, containing the JumpGroupName, InstallerName, InstallerID, ExpirationDate, and a dynamically generated WindowsDownloadURL and MacDownloadURL.

Return: The function returns an HTTP 200 OK response with a JSON body containing the list of processed installer details. It includes robust try...except blocks to handle HTTP errors and other unexpected exceptions, returning appropriate status codes (401, 500) and error messages.

Reference API Endpoints:

GET {BeyondTrustSiteUrl}/api/config/v1/jump-group

GET {BeyondTrustSiteUrl}/api/config/v1/jump-client/installer

POST {BeyondTrustSiteUrl}/oauth2/token

2. GetBeyondTrustJumpClientIPs 🖥️
Function: This function retrieves a list of public IP addresses for all deployed BeyondTrust Jump Clients. This is useful for firewall rules or other security purposes where you need to allow inbound connections from the Jump Clients.

Workflow:

Environment Variable Check: Same as the previous function, it checks for the required environment variables.

OAuth 2.0 Authentication: It performs the same authentication process to obtain a valid access token.

Fetch Jump Clients (with Pagination): It makes paginated API calls to .../api/config/v1/jump-client to retrieve all Jump Clients.

IP Address Extraction and Validation: It iterates through all the retrieved Jump Clients and extracts the public_ip for each one.

A set is used to automatically store only unique IP addresses.

It uses the ipaddress library to validate that each value is a legitimate IP address before adding it to the set, preventing malformed data from being included.

Return: It returns an HTTP 200 OK response with a text/plain body. The body contains a newline-separated list of all unique, validated public IP addresses, sorted alphabetically. Error handling is also included to provide clear messages and appropriate status codes (401, 500) in case of failure.

Reference API Endpoints:

GET {BeyondTrustSiteUrl}/api/config/v1/jump-client

POST {BeyondTrustSiteUrl}/oauth2/token

General Notes 📝
Technology Stack: This script is written in Python and is designed to run as an Azure Function. The decorators (@app.route(...)) are specific to the Azure Functions v2 programming model for Python.

Dependencies: The code relies on the requests library for HTTP calls, base64 for encoding, and ipaddress for IP validation. azure.functions is the core library for the Azure Function environment.

Authentication: Authentication is handled securely using environment variables for the API key and secret, and the OAuth 2.0 client credentials flow. The access token is then used as a Bearer token for subsequent API calls.

Error Handling: Both functions include comprehensive try...except blocks to gracefully handle various errors, including missing environment variables, failed authentication, HTTP errors from the API, and unexpected runtime exceptions. This ensures the function provides informative error messages and appropriate HTTP status codes to the caller.

Efficiency: The code uses pagination to handle large numbers of Jump Clients or installers, preventing a single request from timing out or consuming too much memory. It also uses a set to efficiently store unique IP addresses without duplicates.
