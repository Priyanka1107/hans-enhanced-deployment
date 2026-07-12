# HANS SSH Tunnel Setup Guide

## Problem Summary

Your HANS FastAPI server runs on HTW Berlin server bound to `127.0.0.1:8080` (localhost only), which means it's **not accessible from external machines**. This is actually the **most secure configuration** for an internal service.

## Solution: SSH Tunnel (Port Forwarding)

An SSH tunnel creates a secure, encrypted connection that forwards your local port 8080 to the server's localhost:8080. This requires:
- ✅ No sudo privileges
- ✅ No firewall changes
- ✅ No security exposure
- ✅ Works from anywhere with SSH access

---

## Quick Start (Mac/Linux)

### Step 1: Configure connection script

Edit `connect_to_hans.sh` and update these lines:

```bash
SERVER_USER="your-username"              # Your SSH username
SERVER_HOST="hans-server.htw-berlin.de" # Server hostname or IP
SERVER_PORT=22                           # SSH port (usually 22)
```

### Step 2: Start SSH tunnel

```bash
./connect_to_hans.sh
```

**Keep this terminal open!** The tunnel runs in the foreground.

### Step 3: Test connection (in new terminal)

```bash
./test_connection.sh
```

### Step 4: Run GUI (in new terminal)

```bash
python3 htw_assistant_api_gui.py
```

The GUI will now connect to the server through the tunnel!

---

## Quick Start (Windows)

### Step 1: Enable OpenSSH Client

1. Open **Settings** > **Apps** > **Optional Features**
2. Click **Add a feature**
3. Search for **OpenSSH Client**
4. Install it and restart

### Step 2: Configure connection script

Edit `connect_to_hans.bat` and update these lines:

```batch
set SERVER_USER=your-username
set SERVER_HOST=hans-server.htw-berlin.de
set SERVER_PORT=22
```

### Step 3: Start SSH tunnel

Double-click `connect_to_hans.bat` or run in Command Prompt:

```cmd
connect_to_hans.bat
```

**Keep this window open!** The tunnel runs here.

### Step 4: Run GUI (in new Command Prompt)

```cmd
python htw_assistant_api_gui.py
```

---

## How It Works

```
┌─────────────┐         SSH Tunnel (Encrypted)         ┌──────────────┐
│             │    ─────────────────────────────────▶   │              │
│  Your PC    │                                         │ HTW Server   │
│             │                                         │              │
│ localhost:  │◀─────────────────────────────────────  │ 127.0.0.1:   │
│   8080      │         Data forwarded back            │   8080       │
│             │                                         │              │
│  GUI App    │                                         │  HANS API    │
└─────────────┘                                         └──────────────┘
```

The SSH tunnel forwards:
- **Local**: `localhost:8080` on your PC
- **Remote**: `127.0.0.1:8080` on the server

From the GUI's perspective, it's connecting to a local service!

---

## Manual SSH Tunnel (Without Scripts)

If you prefer to run the SSH command directly:

### Mac/Linux/Windows (with OpenSSH)

```bash
ssh -L 8080:127.0.0.1:8080 your-username@hans-server.htw-berlin.de -N
```

**Flags explained:**
- `-L 8080:127.0.0.1:8080` - Forward local port 8080 to remote localhost:8080
- `-N` - Don't execute a remote command (just tunnel)
- Add `-v` for verbose output if debugging

Keep this terminal open while using the GUI.

---

## Verifying the Tunnel

### Method 1: Test with curl

```bash
# In a new terminal:
curl http://127.0.0.1:8080/health

# Expected output:
{"status":"ok","timestamp":"2025-11-04T..."}
```

### Method 2: Use test script

```bash
./test_connection.sh
```

This runs a full diagnostic:
1. Port accessibility check
2. `/health` endpoint test
3. `/ask` endpoint test with sample query

### Method 3: Check GUI status

Run the GUI - the status indicator should show:
- ✅ Green: "API online (http://127.0.0.1:8080)"

---

## Troubleshooting

### Issue 1: "Connection refused" when starting tunnel

**Symptoms:**
```
channel 2: open failed: connect failed: Connection refused
```

**Cause:** HANS API is not running on the server

**Solution:**
```bash
# SSH into server first
ssh your-username@hans-server.htw-berlin.de

# Check if API is running
curl http://127.0.0.1:8080/health

# If not running, start it:
cd /srv/hans
./start.sh

# Or check status
systemctl status hans-api  # if using systemd
```

---

### Issue 2: "Permission denied (publickey)"

**Symptoms:**
```
Permission denied (publickey).
```

**Cause:** SSH key authentication not set up or password required

**Solution:**

**Option A: Use password authentication** (add `-o PreferredAuthentications=password`):
```bash
ssh -L 8080:127.0.0.1:8080 -o PreferredAuthentications=password user@server -N
```

**Option B: Set up SSH key** (recommended):
```bash
# On your PC:
ssh-keygen -t ed25519 -C "your-email@example.com"

# Copy key to server:
ssh-copy-id your-username@hans-server.htw-berlin.de

# Now tunnel will work without password:
./connect_to_hans.sh
```

---

### Issue 3: "Port 8080 already in use"

**Symptoms:**
```
bind [127.0.0.1]:8080: Address already in use
```

**Cause:** Another tunnel or service is using port 8080

**Solution:**

**Option A: Kill existing tunnel**
```bash
# Find the process
lsof -ti:8080

# Kill it
pkill -f 'ssh.*8080:127.0.0.1:8080'
```

**Option B: Use different local port**
```bash
# Forward to port 8081 instead:
ssh -L 8081:127.0.0.1:8080 user@server -N

# Then run GUI with:
export HANS_API_BASE="http://127.0.0.1:8081"
python3 htw_assistant_api_gui.py
```

---

### Issue 4: Tunnel keeps disconnecting

**Symptoms:** Tunnel drops after a few minutes of inactivity

**Cause:** Firewall/NAT timeout or server SSH config

**Solution:**

**Option A: Add keepalive** (already in scripts):
```bash
ssh -L 8080:127.0.0.1:8080 \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    user@server -N
```

**Option B: Configure SSH client** (add to `~/.ssh/config`):
```
Host hans-server.htw-berlin.de
    ServerAliveInterval 60
    ServerAliveCountMax 3
    TCPKeepAlive yes
```

---

### Issue 5: GUI shows red status despite tunnel running

**Symptoms:** Tunnel is active, but GUI can't connect

**Cause:** API server not running or crashed

**Solution:**
1. **Verify tunnel is actually working:**
   ```bash
   ./test_connection.sh
   ```

2. **SSH to server and check API status:**
   ```bash
   ssh user@server
   curl http://127.0.0.1:8080/health
   ```

3. **Check API logs on server:**
   ```bash
   # If using systemd:
   journalctl -u hans-api -f

   # If running manually:
   tail -f /srv/hans/logs/api.log
   ```

4. **Restart API if needed:**
   ```bash
   ./stop.sh && ./start.sh
   ```

---

## Advanced: Persistent Tunnel (Background)

If you want the tunnel to run in the background:

### Mac/Linux

```bash
# Start in background:
ssh -f -N -L 8080:127.0.0.1:8080 user@server

# Check if running:
ps aux | grep 'ssh.*8080'

# Stop tunnel:
pkill -f 'ssh.*8080:127.0.0.1:8080'
```

### Windows

Use a scheduled task or install `nssm` (Non-Sucking Service Manager) to run as a service.

---

## SSH Config (Recommended)

For convenience, add this to your `~/.ssh/config`:

```
Host hans
    HostName hans-server.htw-berlin.de
    User your-username
    Port 22
    LocalForward 8080 127.0.0.1:8080
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Then you can connect with:
```bash
ssh -N hans
```

Much simpler!

---

## Alternative: Bind Server to 0.0.0.0 (Not Recommended)

If you have the necessary permissions and understand the security implications, you could make the API accessible directly:

### On the server:

1. Edit `.env` or startup config:
   ```bash
   HANS_BIND=0.0.0.0  # Instead of 127.0.0.1
   ```

2. Restart API:
   ```bash
   ./stop.sh && ./start.sh
   ```

3. Configure firewall (requires sudo):
   ```bash
   sudo firewall-cmd --add-port=8080/tcp --permanent
   sudo firewall-cmd --reload
   ```

### On your PC:

```bash
export HANS_API_BASE="http://hans-server.htw-berlin.de:8080"
python3 htw_assistant_api_gui.py
```

**Security concerns:**
- ❌ API exposed to entire HTW network
- ❌ No authentication (anyone can query)
- ❌ No rate limiting
- ❌ No encryption (HTTP not HTTPS)

**Only do this if:**
- API is on an isolated internal network
- You trust all users on that network
- HTW IT policy allows it

**SSH tunnel is much safer!**

---

## Workflow Summary

### Daily Usage

**Terminal 1** (start once, leave open):
```bash
./connect_to_hans.sh
```

**Terminal 2** (run GUI):
```bash
python3 htw_assistant_api_gui.py
```

That's it!

### Automation Options

1. **Auto-start tunnel on login** (Mac):
   - Add to `~/.bash_profile` or create a LaunchAgent

2. **Auto-start tunnel on login** (Linux):
   - Add to `~/.bashrc` or create a systemd user service

3. **Auto-start tunnel on login** (Windows):
   - Create a scheduled task with trigger "At log on"

---

## Security Notes

✅ **SSH tunnel is secure:**
- All traffic is encrypted
- Uses your SSH authentication
- No additional exposure on server
- Only you can access the forwarded port

✅ **Best practices:**
- Use SSH key authentication (not passwords)
- Keep tunnel running only when needed
- Monitor for unauthorized access attempts
- Consider adding API authentication layer if deployed widely

---

## Files Reference

| File | Purpose |
|------|---------|
| `connect_to_hans.sh` | Mac/Linux tunnel setup script |
| `connect_to_hans.bat` | Windows tunnel setup script |
| `test_connection.sh` | Connection verification tool |
| `htw_assistant_api_gui.py` | GUI application |
| `SSH_TUNNEL_GUIDE.md` | This document |

---

## Quick Commands Cheat Sheet

```bash
# Start tunnel (Mac/Linux)
./connect_to_hans.sh

# Start tunnel (Windows)
connect_to_hans.bat

# Test connection
./test_connection.sh
curl http://127.0.0.1:8080/health

# Run GUI
python3 htw_assistant_api_gui.py

# Check tunnel status
ps aux | grep 'ssh.*8080'           # Mac/Linux
netstat -an | findstr :8080         # Windows

# Stop tunnel
pkill -f 'ssh.*8080'                # Mac/Linux
Ctrl+C in tunnel window             # Any OS

# Troubleshoot
ssh -v -L 8080:127.0.0.1:8080 user@server -N   # Verbose mode
```

---

## Support

**Connection issues?**
1. Run `./test_connection.sh`
2. Check server status: `ssh user@server "curl http://127.0.0.1:8080/health"`
3. Verify SSH access: `ssh user@server`

**GUI issues?**
1. Check API_BASE is set correctly (default: `http://127.0.0.1:8080`)
2. Look for errors in terminal output
3. Click "Test API" button in GUI

**Server issues?**
1. SSH to server and check API logs
2. Verify database is running
3. Check Ollama service status

---

**Ready to connect?** Run `./connect_to_hans.sh` and let's get started!
