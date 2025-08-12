# `README.md` for BeyondTrust Azure Function 💻

### Overview

This repository contains Python code for an Azure Function App that provides two HTTP-triggered endpoints. These functions interact with the BeyondTrust Privileged Remote Access API to retrieve key information about your environment. This is useful for integrating BeyondTrust data into other systems, such as endpoint management solutions like Intune or network security tools for firewall rule automation.

### Endpoints 🚀

The function app exposes the following endpoints:

#### 1. `GET /api/GetBeyondTrustData`

This endpoint retrieves and processes information about BeyondTrust Jump Client installers. It's designed to return details for the **most recently created installer** for each Jump Group.

**Response:** Returns a JSON array of objects. Each object represents an installer and includes the following fields:

* `JumpGroupName`: The name of the Jump Group.
* `InstallerName`: The name of the installer.
* `InstallerID`: The unique ID of the installer.
* `ExpirationDate`: The expiration timestamp of the installer.
* `WindowsDownloadURL`: A direct download URL for the Windows MSI installer.
* `MacDownloadURL`: A direct download URL for the macOS installer.

**Example JSON Response:**

```json
[
  {
    "JumpGroupName": "IT Support Team",
    "InstallerName": "ITSupport-2025-08-12",
    "InstallerID": "0123456789abcdef",
    "ExpirationDate": "2026-08-12T17:00:00Z",
    "WindowsDownloadURL": "[https://beyondtrust.example.com/download_client_connector?jc=0123456789abcdef&p=winNT-64-msi](https://beyondtrust.example.com/download_client_connector?jc=0123456789abcdef&p=winNT-64-msi)",
    "MacDownloadURL": "[https://beyondtrust.example.com/download_client_connector?jc=0123456789abcdef&p=mac-osx-x86](https://beyondtrust.example.com/download_client_connector?jc=0123456789abcdef&p=mac-osx-x86)"
  }
]
```

#### 2. `GET /api/GetBeyondTrustJumpClientIPs`

This endpoint retrieves a sorted list of all unique public IP addresses for currently deployed BeyondTrust Jump Clients. This is particularly useful for dynamically updating firewall rules to permit traffic from your remote Jump Clients.

**Response:** Returns a `text/plain` body with one IP address per line.

**Example Text Response:**

```text
192.0.2.1
198.51.100.2
203.0.113.3
```

### Configuration ⚙️

This Azure Function requires the following Application Settings (environment variables) to be configured in your Azure Function App instance.

| Name | Value | Description |
|---|---|---|
| `BeyondTrustSiteUrl` | `https://beyondtrust.example.com` | The base URL for your BeyondTrust site. |
| `BeyondTrustApiKey` | `<Your-API-Key>` | The API key generated in the BeyondTrust Admin console. |
| `BeyondTrustApiSecret` | `<Your-API-Secret>` | The corresponding API secret. |

### Requirements 📋

* Python 3.8+
* The following Python libraries:
    * `azure-functions`
    * `requests`

These can be installed using `pip`:

```bash
pip install azure-functions requests
```

### Deployment to Azure ☁️

1. Create a new Function App in the Azure portal.
2. Choose the Python runtime stack.
3. Configure the required **Application Settings** listed above.
4. Deploy this code to your Function App using your preferred method (e.g., Azure CLI, VS Code extension, or CI/CD pipeline).

### How to Use the `GetBeyondTrustData` Endpoint

You can call this endpoint from other services, like a PowerShell script for Intune. Here's a quick example of a PowerShell script to download the latest Windows installer:

```powershell
# The following script is for downloading the BeyondTrust Jump Client installer.
$beyondTrustUrl = "https://<your-function-app>.azurewebsites.net/api/GetBeyondTrustData"
$outputPath = "C:\Temp\BeyondTrust_Installer.msi"

try {
    Write-Host "Fetching BeyondTrust installer data from the Azure Function..."
    $response = Invoke-RestMethod -Uri $beyondTrustUrl -Method GET
    
    if ($null -ne $response -and $response.Count -gt 0) {
        # Assuming you want the first installer returned
        $installerUrl = $response[0].WindowsDownloadURL
        
        Write-Host "Downloading latest installer from: $installerUrl"
        Invoke-WebRequest -Uri $installerUrl -OutFile $outputPath
        
    } else {
        Write-Host "No installer data received from the function."
    }
}
catch {
    Write-Host "An error occurred: $_"
}
