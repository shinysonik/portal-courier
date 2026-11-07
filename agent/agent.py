import os
import sys

def main():
    print("[-] Agent started inside the container.")
    print(f"[-] PORTAL_URL: {os.getenv('PORTAL_URL', 'not set')}")
    print(f"[-] OUT_DIR: {os.getenv('OUT_DIR', 'not set')}")
    
# TODO: Guys, your Playwright code will be here.
    #1. Run Chromium with --no-sandbox
    #2. Lien to the portal
    # 3. Download PDF in OUT_DIR
    
    print("[-] Agent finished. This is a stub.")
    sys.exit(0)

if __name__ == "__main__":
    main()