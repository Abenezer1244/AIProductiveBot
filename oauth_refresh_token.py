from __future__ import annotations
import argparse
from google_auth_oauthlib.flow import InstalledAppFlow
SCOPES = ["https://www.googleapis.com/auth/calendar"]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()
    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob","http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_console()
    print("\n=== COPY THIS REFRESH TOKEN ===")
    print(creds.refresh_token)
    print("================================")
if __name__ == "__main__":
    main()
