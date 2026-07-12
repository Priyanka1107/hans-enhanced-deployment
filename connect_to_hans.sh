#!/bin/bash
# SSH Tunnel Setup for HANS GUI
# This script creates an SSH tunnel to the HTW server and keeps it alive

set -e

# ============================================================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================================================

# Your HTW server details
SERVER_USER="aleks"              # Replace with your SSH username
SERVER_HOST="10.2.100.35" # Replace with server hostname or IP
SERVER_PORT=22                           # SSH port (usually 22)

# HANS API details
REMOTE_PORT=8080  # Port where HANS API runs on the server
LOCAL_PORT=8080   # Local port to forward to (can be different if 8080 is busy)

# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        HANS SSH Tunnel Connection Manager                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if SSH is available
if ! command -v ssh &> /dev/null; then
    echo -e "${RED}✗ Error: SSH client not found${NC}"
    echo "Please install OpenSSH client first"
    exit 1
fi

# Check if tunnel is already running
EXISTING_PID=$(pgrep -f "ssh.*${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}.*${SERVER_USER}@${SERVER_HOST}" 2>/dev/null || true)

if [ -n "$EXISTING_PID" ]; then
    echo -e "${YELLOW}⚠ SSH tunnel already running (PID: $EXISTING_PID)${NC}"
    echo ""
    echo "Options:"
    echo "  1) Keep existing tunnel and continue"
    echo "  2) Kill existing tunnel and create new one"
    echo "  3) Exit"
    echo ""
    read -p "Choose option (1-3): " choice

    case $choice in
        2)
            echo -e "${YELLOW}Killing existing tunnel...${NC}"
            kill $EXISTING_PID 2>/dev/null || true
            sleep 1
            ;;
        3)
            echo -e "${BLUE}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${GREEN}Using existing tunnel${NC}"
            ;;
    esac
fi

# Test if local port is available
if lsof -Pi :${LOCAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${YELLOW}⚠ Port ${LOCAL_PORT} is already in use${NC}"
    echo "The tunnel may already be running, or another service is using this port"
    echo ""
    read -p "Do you want to try a different local port? (y/n): " use_different
    if [[ $use_different =~ ^[Yy]$ ]]; then
        read -p "Enter alternative port number (e.g., 8081): " LOCAL_PORT
        echo -e "${BLUE}Will use local port ${LOCAL_PORT}${NC}"
    fi
fi

echo ""
echo -e "${BLUE}Connection Details:${NC}"
echo "  Server: ${SERVER_USER}@${SERVER_HOST}:${SERVER_PORT}"
echo "  Remote API: 127.0.0.1:${REMOTE_PORT}"
echo "  Local Port: ${LOCAL_PORT}"
echo ""
echo -e "${YELLOW}Creating SSH tunnel...${NC}"

# Create SSH tunnel with:
# -N = No remote command (just tunnel)
# -L = Local port forwarding
# -o ServerAliveInterval=60 = Keep connection alive
# -o ServerAliveCountMax=3 = Reconnect if 3 keepalives fail
# -o ExitOnForwardFailure=yes = Exit if port forwarding fails

ssh -N \
    -L ${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT} \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    ${SERVER_USER}@${SERVER_HOST} -p ${SERVER_PORT} &

SSH_PID=$!
echo $SSH_PID > /tmp/hans_tunnel.pid

# Wait for tunnel to establish
echo -e "${YELLOW}Waiting for tunnel to establish...${NC}"
sleep 3

# Check if tunnel is still running
if ps -p $SSH_PID > /dev/null; then
    echo -e "${GREEN}✓ SSH tunnel established successfully!${NC}"
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Tunnel is ACTIVE - You can now run the HANS GUI          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  HANS API is now available at: http://localhost:${LOCAL_PORT}"
    echo "  Tunnel PID: $SSH_PID"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Open a new terminal"
    if [ "$LOCAL_PORT" != "8080" ]; then
        echo "  2. Run: export HANS_API_BASE=\"http://127.0.0.1:${LOCAL_PORT}\""
        echo "  3. Run: python3 htw_assistant_api_gui.py"
    else
        echo "  2. Run: python3 htw_assistant_api_gui.py"
    fi
    echo ""
    echo -e "${YELLOW}To stop the tunnel:${NC}"
    echo "  kill $SSH_PID"
    echo "  or run: pkill -f 'ssh.*${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}'"
    echo ""
    echo -e "${BLUE}Press Ctrl+C to close this tunnel${NC}"

    # Keep script running and monitor tunnel
    trap "echo ''; echo 'Closing tunnel...'; kill $SSH_PID 2>/dev/null; rm -f /tmp/hans_tunnel.pid; exit 0" SIGINT SIGTERM

    while ps -p $SSH_PID > /dev/null; do
        sleep 5
    done

    echo -e "${RED}✗ SSH tunnel died unexpectedly${NC}"
    rm -f /tmp/hans_tunnel.pid
    exit 1
else
    echo -e "${RED}✗ Failed to establish SSH tunnel${NC}"
    echo ""
    echo "Common issues:"
    echo "  • Check username and hostname are correct"
    echo "  • Verify you can SSH to the server: ssh ${SERVER_USER}@${SERVER_HOST}"
    echo "  • Check if SSH key authentication is set up"
    echo "  • Verify the server is reachable from your network"
    rm -f /tmp/hans_tunnel.pid
    exit 1
fi
