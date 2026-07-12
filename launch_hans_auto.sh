#!/bin/bash
# Automated HANS Launcher - Handles tunnel + GUI automatically
# For Linux/macOS

# Configuration
SERVER_USER="aleks"
SERVER_HOST="10.2.100.35"
SERVER_PORT=22
LOCAL_PORT=8080
REMOTE_PORT=8080

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   HANS - HTW Berlin Student Services Assistant            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if GUI file exists
if [ ! -f "$SCRIPT_DIR/htw_assistant_api_gui.py" ]; then
    echo -e "${RED}Error: htw_assistant_api_gui.py not found in $SCRIPT_DIR${NC}"
    echo "Please ensure the GUI file is in the same directory as this script."
    exit 1
fi

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher first."
    exit 1
fi

# Check if requests module is installed
if ! python3 -c "import requests" 2>/dev/null; then
    echo -e "${YELLOW}Warning: 'requests' module not found${NC}"
    echo "Installing requests module..."
    pip3 install requests --user
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install requests. Please run: pip3 install requests${NC}"
        exit 1
    fi
fi

# Check if tunnel is already running
if lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}⚠ Port ${LOCAL_PORT} is already in use${NC}"
    echo ""
    read -p "A tunnel may already be running. Continue anyway? (y/n): " continue_anyway
    if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
        echo "Exiting..."
        exit 0
    fi
fi

echo -e "${BLUE}Step 1: Establishing SSH tunnel to HANS server...${NC}"
echo "Server: ${SERVER_USER}@${SERVER_HOST}:${SERVER_PORT}"
echo "You will be prompted for your SSH password."
echo ""

# Start SSH tunnel in background with ControlMaster for connection sharing
# This allows the tunnel to run independently and be killed later
SSH_CONTROL_PATH="/tmp/hans_ssh_control_$$"

ssh -f -N \
    -L ${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT} \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -o ControlMaster=yes \
    -o ControlPath="${SSH_CONTROL_PATH}" \
    ${SERVER_USER}@${SERVER_HOST} -p ${SERVER_PORT}

SSH_EXIT_CODE=$?

if [ $SSH_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}✗ Failed to establish SSH tunnel${NC}"
    echo ""
    echo "Common issues:"
    echo "  • Incorrect password"
    echo "  • Not connected to HTW network/VPN"
    echo "  • Server unreachable"
    echo ""
    echo "Try manually: ssh ${SERVER_USER}@${SERVER_HOST}"
    rm -f "${SSH_CONTROL_PATH}"
    exit 1
fi

# Wait for tunnel to establish
echo -e "${YELLOW}Waiting for tunnel to establish...${NC}"
sleep 3

# Verify tunnel is working
if ! lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}✗ Tunnel failed to start${NC}"
    ssh -O exit -o ControlPath="${SSH_CONTROL_PATH}" ${SERVER_USER}@${SERVER_HOST} 2>/dev/null
    rm -f "${SSH_CONTROL_PATH}"
    exit 1
fi

echo -e "${GREEN}✓ SSH tunnel established successfully!${NC}"
echo ""

# Test API connection
echo -e "${BLUE}Step 2: Testing connection to HANS API...${NC}"
HEALTH_CHECK=$(curl -s -m 5 http://127.0.0.1:${LOCAL_PORT}/health 2>&1)
CURL_EXIT=$?

if [ $CURL_EXIT -eq 0 ] && echo "$HEALTH_CHECK" | grep -q "status"; then
    echo -e "${GREEN}✓ HANS API is responding${NC}"
else
    echo -e "${YELLOW}⚠ API connection test failed${NC}"
    echo "The GUI may show a connection error. Ensure HANS API is running on the server."
fi

echo ""
echo -e "${BLUE}Step 3: Launching HANS GUI...${NC}"
echo ""

# Store control path for cleanup
echo "${SSH_CONTROL_PATH}" > /tmp/hans_control_path_$$

# Function to cleanup tunnel on exit
cleanup_tunnel() {
    CONTROL_PATH_FILE="/tmp/hans_control_path_$$"
    if [ -f "$CONTROL_PATH_FILE" ]; then
        CONTROL_PATH=$(cat "$CONTROL_PATH_FILE")
        echo ""
        echo -e "${YELLOW}Closing SSH tunnel...${NC}"
        ssh -O exit -o ControlPath="${CONTROL_PATH}" ${SERVER_USER}@${SERVER_HOST} 2>/dev/null
        rm -f "${CONTROL_PATH}"
        rm -f "$CONTROL_PATH_FILE"
        echo -e "${GREEN}✓ Tunnel closed${NC}"
    fi
}

# Set trap to cleanup on script exit
trap cleanup_tunnel EXIT

# Launch GUI in foreground (script waits for GUI to close)
cd "$SCRIPT_DIR"
python3 htw_assistant_api_gui.py

# When GUI closes, trap will handle cleanup
echo ""
echo -e "${BLUE}HANS closed. Have a great day!${NC}"
