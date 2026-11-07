
# Node.js Demo Portals

This folder contains 5 extra mock supplier portals built with Node.js and Express. They run independently from the Python portals and are used to add more realistic "noise" to the demo (showing that the bookkeeper has to deal with many different websites).

## What's inside

*   **`server.js`** — The main application. It serves all 5 portals on different routes.
*   **`start.bat`** — A one-click Windows script that starts the server and opens your browser.
*   **`package.json` & `package-lock.json`** — Configuration files that tell Node.js which packages to download (we only use `express`).

*Note: You will NOT see a `node_modules` folder in GitHub. It is ignored by Git because it contains thousands of files. You will generate it automatically in the next step.*

## How to run them

You need to have [Node.js](https://nodejs.org/) installed on your computer.

1. Open your terminal and navigate to this folder:
   ```powershell
   cd portals/node-portals
   ```
2. Install the dependencies (this creates the `node_modules` folder):
   ```powershell
   npm install
   ```
3. Start the server:
   ```powershell
   npm start
   ```
   *(Or just double-click `start.bat` on Windows).*

## Important for the Proxy and Agent teams

These portals run on different ports than the Python ones (e.g., `localhost:3000`, `3001`, etc.). 

When testing the AI agent on these new portals, you **must add their ports to the proxy's allowlist**, otherwise the proxy will block the agent from reaching them. Check the proxy's `ALLOWED_HOSTS` environment variable.