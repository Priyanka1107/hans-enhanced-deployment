# HANS GUI Deployment Guide

## Overview
The HANS GUI is a Python Tkinter application that connects to your hosted FastAPI server at HTW Berlin. This guide covers deploying the GUI on staff workstations.

---

## Prerequisites

### Server Requirements (Already Met ✅)
- ✅ API server running at HTW Berlin
- ✅ Server accessible on port 8080
- ✅ `/health` and `/ask` endpoints operational

### Client Workstation Requirements
- **OS**: Windows, macOS, or Linux with desktop environment
- **Python**: 3.8 or higher
- **Network**: Access to HTW internal network (server reachable)
- **Display**: GUI requires X11/Wayland on Linux, or native display on Windows/macOS

---

## Deployment Steps

### 1. Determine Server Address

First, identify the server's hostname or IP address:

```bash
# On the HTW server, find the hostname:
hostname -f
# Example output: hans-server.htw-berlin.de

# Or find the IP address:
hostname -I
# Example output: 10.20.30.40
```

**Your server address will be one of:**
- `http://hans-server.htw-berlin.de:8080` (if DNS configured)
- `http://10.x.x.x:8080` (internal IP address)
- `http://127.0.0.1:8080` (if running GUI on same server)

---

### 2. Test Server Connectivity

**From the client workstation**, verify you can reach the server:

```bash
# Test health endpoint
curl -s http://YOUR-SERVER-ADDRESS:8080/health

# Expected output:
# {"status":"ok","timestamp":"2025-11-04T..."}
```

**If this fails:**
- ✗ Check network connectivity: `ping YOUR-SERVER-IP`
- ✗ Check firewall rules on server
- ✗ Verify server is bound to `0.0.0.0:8080` (not just `127.0.0.1`)
- ✗ Check HTW network policies (VPN required?)

---

### 3. Install GUI Dependencies

On the **client workstation**:

```bash
# Install Python dependencies
pip3 install requests

# Tkinter is usually pre-installed, but if missing:

# On Ubuntu/Debian:
sudo apt-get install python3-tk

# On RHEL/CentOS:
sudo yum install python3-tkinter

# On macOS (usually pre-installed):
# (Tkinter comes with Python from python.org)

# On Windows (usually pre-installed):
# (Tkinter comes with official Python installer)
```

---

### 4. Transfer GUI File

Copy `htw_assistant_api_gui.py` to the client workstation:

```bash
# Option A: Using scp
scp htw_assistant_api_gui.py user@workstation:/path/to/destination/

# Option B: Using USB drive, network share, or email
# Just copy the single file: htw_assistant_api_gui.py
```

---

### 5. Configure and Run GUI

#### Option A: Using Environment Variable (Recommended)

```bash
# Linux/macOS:
export HANS_API_BASE="http://YOUR-SERVER-ADDRESS:8080"
python3 htw_assistant_api_gui.py

# Windows (Command Prompt):
set HANS_API_BASE=http://YOUR-SERVER-ADDRESS:8080
python htw_assistant_api_gui.py

# Windows (PowerShell):
$env:HANS_API_BASE="http://YOUR-SERVER-ADDRESS:8080"
python htw_assistant_api_gui.py
```

#### Option B: Edit the File Directly

Edit line 20 in `htw_assistant_api_gui.py`:

```python
# Before:
API_BASE = os.getenv("HANS_API_BASE", "http://127.0.0.1:8080")

# After (replace with your actual server address):
API_BASE = os.getenv("HANS_API_BASE", "http://hans-server.htw-berlin.de:8080")
```

Then run:
```bash
python3 htw_assistant_api_gui.py
```

---

### 6. Verify GUI Connection

When the GUI launches:

1. **Check status indicator**: Should show "✅ API online (http://...)"
   - ✅ Green = Connected successfully
   - ❌ Red = Connection failed (see troubleshooting)

2. **Test with a query**:
   - Type: "What are the admission requirements?"
   - Click "Generate Response"
   - Should receive an answer within 5-30 seconds

---

## Deployment Scenarios

### Scenario 1: Multiple Staff Desktops

**Best Practice**: Create a launcher script

**Linux/macOS** (`launch_hans_gui.sh`):
```bash
#!/bin/bash
export HANS_API_BASE="http://hans-server.htw-berlin.de:8080"
python3 /path/to/htw_assistant_api_gui.py
```

**Windows** (`launch_hans_gui.bat`):
```batch
@echo off
set HANS_API_BASE=http://hans-server.htw-berlin.de:8080
python C:\path\to\htw_assistant_api_gui.py
```

Distribute this launcher to all staff workstations.

---

### Scenario 2: Running GUI on Server

If the server has a desktop environment (X11):

```bash
# On the server, simply run:
python3 /srv/hans/htw_assistant_api_gui.py

# The default localhost:8080 will work
```

---

### Scenario 3: Remote Desktop / VNC

If staff access the server via remote desktop:

1. Install VNC server or use RDP on the server
2. Staff connect to remote desktop
3. Run GUI directly on server (uses localhost)

---

## Troubleshooting

### Issue: "API Connection Required" Error

**Symptoms**: Red status showing connection timeout or refused

**Solutions**:
1. Verify server is running:
   ```bash
   curl http://YOUR-SERVER:8080/health
   ```

2. Check firewall on server:
   ```bash
   # Allow port 8080
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload
   ```

3. Verify server bind address in `/srv/hans/.env`:
   ```bash
   HANS_BIND=0.0.0.0  # NOT 127.0.0.1
   HANS_PORT=8080
   ```

4. Check network connectivity:
   ```bash
   ping YOUR-SERVER-IP
   telnet YOUR-SERVER-IP 8080
   ```

---

### Issue: Missing Tkinter

**Symptoms**: `ImportError: No module named 'tkinter'`

**Solutions**:
```bash
# Ubuntu/Debian:
sudo apt-get install python3-tk

# RHEL/CentOS:
sudo yum install python3-tkinter

# macOS:
# Reinstall Python from python.org (includes Tkinter)

# Windows:
# Reinstall Python with "tcl/tk and IDLE" option checked
```

---

### Issue: Slow Response Times

**Symptoms**: GUI hangs for 30+ seconds

**Solutions**:
1. Increase timeout in GUI (line 23):
   ```python
   TIMEOUT = float(os.getenv("HANS_API_TIMEOUT", "60"))  # increase to 60s
   ```

2. Check server load:
   ```bash
   # On server:
   top
   # Look for high CPU usage from Ollama or Python
   ```

3. Verify Ollama is running:
   ```bash
   curl http://localhost:11434/api/tags
   ```

---

### Issue: Proxy Authentication Required

**Symptoms**: 407 Proxy Authentication Required

**Solution**: If HTW network requires proxy authentication for external requests:

```bash
# Set proxy with credentials:
export HTTP_PROXY="http://username:password@proxy.htw-berlin.de:8080"
export HTTPS_PROXY="http://username:password@proxy.htw-berlin.de:8080"
```

---

## Security Considerations

### Current Setup (Internal Use)
- ✅ No authentication required (suitable for internal HTW network)
- ✅ CORS enabled for browser access
- ✅ No SSL/TLS (HTTP only - acceptable on internal network)

### If Exposing Outside HTW Network
- ⚠️ Add authentication (Basic Auth, OAuth, or JWT)
- ⚠️ Enable HTTPS with valid SSL certificate
- ⚠️ Add rate limiting to prevent abuse
- ⚠️ Restrict CORS origins

---

## Distribution Checklist

- [ ] Identify server hostname/IP address
- [ ] Test connectivity from client workstation
- [ ] Install Python 3.8+ on client machines
- [ ] Install dependencies (`pip3 install requests`)
- [ ] Copy `htw_assistant_api_gui.py` to workstations
- [ ] Create launcher script with correct `HANS_API_BASE`
- [ ] Test GUI connection and sample query
- [ ] Document server address for staff
- [ ] Provide this guide to IT support team

---

## Quick Reference

**Files**:
- GUI Application: `htw_assistant_api_gui.py` (single file)
- Configuration: Line 20 or `HANS_API_BASE` environment variable

**Endpoints Used**:
- `GET /health` - Connection check
- `POST /ask` - Submit queries

**Default Settings**:
- Port: 8080
- Timeout: 30 seconds
- Auto-retry: No (manual retry via "Test API" button)

**Support**:
- Server logs: `/srv/hans/logs/` or container logs
- GUI logs: Printed to console/terminal
- Debug: Run with `python3 -u htw_assistant_api_gui.py` for unbuffered output

---

## Next Steps

1. **Test deployment** on a single workstation first
2. **Document the server address** for future reference
3. **Create launcher scripts** for easy distribution
4. **Train staff** on basic usage (input question, click button, read response)
5. **Monitor server performance** under real user load
6. **Plan for updates**: Keep `htw_assistant_api_gui.py` in version control for easy updates

---

**Server Status**: ✅ Live at HTW Berlin
**GUI Status**: ✅ Ready for deployment
**Next Action**: Test connectivity from first client workstation
