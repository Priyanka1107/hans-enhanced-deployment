# HANS GUI - Staff PC Setup Guide

Complete step-by-step guide for deploying the HANS GUI on staff workstations at HTW Berlin.

---

## Prerequisites Check

Before starting, verify:
- [ ] Staff PC has Python 3.8 or higher installed
- [ ] Staff member has SSH access to the HANS server (username: `aleks`, server: `10.2.100.35`)
- [ ] Staff PC is connected to HTW network (or VPN if remote)
- [ ] HANS API server is running on `10.2.100.35`

---

## Part 1: One-Time Setup (Per Staff PC)

### Step 1: Install Required Software

#### Check Python Installation

```bash
python3 --version
```

**Expected:** `Python 3.8.x` or higher

**If not installed:**
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt-get update
  sudo apt-get install python3 python3-pip python3-tk
  ```
- **Linux (RHEL/CentOS):**
  ```bash
  sudo yum install python3 python3-pip python3-tkinter
  ```
- **macOS:**
  - Download from [python.org](https://www.python.org/downloads/)
  - Tkinter comes bundled
- **Windows:**
  - Download from [python.org](https://www.python.org/downloads/)
  - During installation, check "tcl/tk and IDLE" option

#### Install Python Dependencies

```bash
pip3 install requests
```

---

### Step 2: Copy GUI Files to Staff PC

Create a directory for HANS:

```bash
mkdir -p ~/HANS
cd ~/HANS
```

**Transfer these files to `~/HANS/` on the staff PC:**

1. `htw_assistant_api_gui.py` - The GUI application
2. `QUICK_START.md` - Quick reference guide (optional)

**Transfer methods:**
- USB drive
- Network share
- Email attachment
- SCP: `scp htw_assistant_api_gui.py staff@workstation:~/HANS/`

---

### Step 3: Verify Server Access

Test SSH connection to the HANS server:

```bash
ssh aleks@10.2.100.35
```

**Expected:**
- Password prompt
- Successful login to server

**If this fails:**
- ✗ Check HTW network connection
- ✗ Verify VPN is connected (if working remotely)
- ✗ Contact IT for SSH access setup

Once verified, exit the server:
```bash
exit
```

---

## Part 2: Daily Usage Workflow

Every time a staff member wants to use HANS, they follow these steps:

### Step 1: Connect to HTW Network

**If on campus:** Connected automatically via campus WiFi/Ethernet

**If remote:** Connect to HTW VPN first

---

### Step 2: Start SSH Tunnel

Open a terminal and run:

```bash
ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35
```

**What happens:**
1. Prompts for password → Enter server password
2. Terminal appears to hang with no output → **This is correct!**
3. Cursor just sits there → **Tunnel is working!**

**Important:**
- ⚠️ Keep this terminal window open while using HANS
- ⚠️ Don't close it or press Ctrl+C
- ⚠️ Minimize it if needed, but leave it running

---

### Step 3: Launch HANS GUI

Open a **new terminal** (keep the first one running!) and run:

```bash
cd ~/HANS
python3 htw_assistant_api_gui.py
```

**Expected:**
- GUI window opens
- Status shows: ✅ "API online (http://127.0.0.1:8080)" in green

**If status is red:**
- Check tunnel terminal is still running
- Verify HANS API is running on server (contact admin)
- Click "Test API" button to retry

---

### Step 4: Use HANS

1. Type your question in the input box
2. Click "Generate Response"
3. Wait 5-30 seconds for the answer
4. View response and sources
5. Click "Show Details" for metadata
6. Click "Copy Response" to copy answer to clipboard

---

### Step 5: Shut Down

When finished:

1. **Close GUI window** (click X or close normally)
2. **Stop SSH tunnel**: Go to tunnel terminal, press `Ctrl+C`
3. Terminal will show "Connection to 10.2.100.35 closed"

---

## Part 3: Creating Desktop Shortcuts (Optional)

To make it easier for staff, create launcher scripts.

### Linux Desktop Launcher

Create `~/Desktop/HANS.desktop`:

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=HANS Assistant
Comment=HTW Berlin Student Services Assistant
Exec=/home/USERNAME/HANS/launch_hans.sh
Icon=applications-education
Terminal=true
Categories=Education;
```

Create `~/HANS/launch_hans.sh`:

```bash
#!/bin/bash
echo "================================================"
echo "  HANS - HTW Berlin Student Services Assistant"
echo "================================================"
echo ""
echo "Step 1: Starting SSH tunnel..."
echo "You will be prompted for the server password."
echo ""

# Start tunnel in background and save PID
ssh -f -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35
TUNNEL_PID=$!

echo ""
echo "Step 2: Starting HANS GUI..."
sleep 2

# Launch GUI
cd ~/HANS
python3 htw_assistant_api_gui.py

# When GUI closes, kill tunnel
echo ""
echo "Closing SSH tunnel..."
pkill -f "ssh.*-L 8080:127.0.0.1:8080.*aleks@10.2.100.35"
echo "Done!"
```

Make executable:
```bash
chmod +x ~/HANS/launch_hans.sh
chmod +x ~/Desktop/HANS.desktop
```

---

### macOS Application Launcher

Create `~/HANS/launch_hans.command`:

```bash
#!/bin/bash
echo "================================================"
echo "  HANS - HTW Berlin Student Services Assistant"
echo "================================================"
echo ""
echo "Starting SSH tunnel to HANS server..."
echo "Enter server password when prompted."
echo ""

# Start tunnel
ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35 &
TUNNEL_PID=$!

sleep 3

# Launch GUI
cd ~/HANS
python3 htw_assistant_api_gui.py

# Kill tunnel when done
kill $TUNNEL_PID 2>/dev/null
echo ""
echo "HANS closed. Goodbye!"
```

Make executable:
```bash
chmod +x ~/HANS/launch_hans.command
```

Staff can double-click `launch_hans.command` from Finder.

---

### Windows Batch Launcher

Create `C:\HANS\launch_hans.bat`:

```batch
@echo off
echo ================================================
echo   HANS - HTW Berlin Student Services Assistant
echo ================================================
echo.
echo Starting SSH tunnel to HANS server...
echo Enter server password when prompted.
echo.

REM Start tunnel in background
start /B ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35

timeout /t 3 /nobreak >nul

echo.
echo Starting HANS GUI...
echo.

REM Launch GUI
cd C:\HANS
python htw_assistant_api_gui.py

REM Kill tunnel when GUI closes
echo.
echo Closing SSH tunnel...
taskkill /F /IM ssh.exe /T >nul 2>&1

echo Done!
pause
```

Staff can double-click `launch_hans.bat` from Desktop.

---

## Part 4: Troubleshooting Guide for Staff

### Issue: "Connection refused" or Red Status

**Symptoms:** GUI shows red ❌ status saying "Connection refused"

**Solutions:**
1. ✓ Check tunnel terminal is still open and running
2. ✓ Verify you entered password correctly when starting tunnel
3. ✓ Restart tunnel: Close tunnel terminal (Ctrl+C), run tunnel command again
4. ✓ Check VPN connection if working remotely
5. ✓ Contact IT support if problem persists

---

### Issue: "Permission denied" when starting tunnel

**Symptoms:** SSH says "Permission denied" after password entry

**Solutions:**
1. ✓ Verify password is correct (try regular SSH first: `ssh aleks@10.2.100.35`)
2. ✓ Check with IT that your account has SSH access
3. ✓ Ensure you're using correct username (`aleks`)

---

### Issue: GUI window doesn't open

**Symptoms:** Command runs but no window appears

**Solutions:**
1. ✓ Check Python is installed: `python3 --version`
2. ✓ Check Tkinter is installed: `python3 -c "import tkinter"`
3. ✓ On Linux, install: `sudo apt-get install python3-tk`
4. ✓ Check for error messages in terminal

---

### Issue: Slow responses (30+ seconds)

**Symptoms:** GUI takes very long to generate responses

**Cause:** High server load or complex queries

**Solutions:**
1. ✓ Wait patiently (RAG processing takes time)
2. ✓ Try simpler, more specific questions
3. ✓ Contact admin if consistently slow (server may need resources)

---

### Issue: Tunnel disconnects after idle time

**Symptoms:** GUI works initially but fails after being idle

**Solutions:**
1. ✓ Restart tunnel with keepalive:
   ```bash
   ssh -N -L 8080:127.0.0.1:8080 -o ServerAliveInterval=60 aleks@10.2.100.35
   ```
2. ✓ Avoid leaving GUI idle for long periods
3. ✓ Restart tunnel if needed

---

## Part 5: Admin Setup Checklist

For the system administrator deploying to multiple staff PCs:

### Pre-Deployment

- [ ] Verify HANS API server is running and stable
- [ ] Test tunnel from admin machine first
- [ ] Create standardized directory structure (e.g., `C:\HANS` or `~/HANS`)
- [ ] Prepare file package: `htw_assistant_api_gui.py`, `QUICK_START.md`, launcher scripts
- [ ] Document server password (secure location)
- [ ] Create quick reference card for staff

### Per-PC Deployment

- [ ] Install Python 3.8+ with Tkinter
- [ ] Install `requests` package: `pip3 install requests`
- [ ] Copy GUI files to standard location
- [ ] Test SSH connection to server
- [ ] Test tunnel manually
- [ ] Launch GUI and verify green status
- [ ] Test with sample query
- [ ] Create desktop shortcut/launcher
- [ ] Show staff member basic usage
- [ ] Leave quick reference guide

### Post-Deployment

- [ ] Monitor server logs for usage patterns
- [ ] Collect feedback from staff
- [ ] Document common issues encountered
- [ ] Schedule follow-up training if needed
- [ ] Plan for updates/patches

---

## Part 6: Network Configuration Notes

### For On-Campus Staff PCs

**Requirements:**
- Connected to HTW internal network
- SSH port 22 access to `10.2.100.35`
- No special firewall rules needed

**Setup:** Follow standard workflow above

---

### For Remote Staff (VPN)

**Requirements:**
- HTW VPN client installed and configured
- VPN must be connected before starting tunnel
- VPN must remain connected during use

**Setup:**
1. Connect VPN first
2. Verify server reachable: `ping 10.2.100.35`
3. Follow standard workflow

---

### For Staff Outside University Network

**Requirements:**
- HTW VPN mandatory
- Stable internet connection
- May experience slower response times

**Setup:**
1. Connect to HTW VPN
2. Test connectivity: `ssh aleks@10.2.100.35`
3. If successful, proceed with standard workflow

---

## Part 7: Quick Reference Card

Print this and leave at each staff desk:

```
╔══════════════════════════════════════════════════════════╗
║        HANS - Quick Start Guide for Staff                ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. Open Terminal                                        ║
║                                                          ║
║  2. Start Tunnel:                                        ║
║     ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35     ║
║     → Enter password                                     ║
║     → Keep this window open!                             ║
║                                                          ║
║  3. Open NEW Terminal                                    ║
║                                                          ║
║  4. Run GUI:                                             ║
║     cd ~/HANS                                            ║
║     python3 htw_assistant_api_gui.py                     ║
║                                                          ║
║  5. Use HANS:                                            ║
║     → Type question                                      ║
║     → Click "Generate Response"                          ║
║     → Wait 5-30 seconds                                  ║
║     → Read answer and sources                            ║
║                                                          ║
║  6. When Done:                                           ║
║     → Close GUI window                                   ║
║     → In tunnel terminal: Ctrl+C                         ║
║                                                          ║
║  Problems? Check:                                        ║
║  • Tunnel still running?                                 ║
║  • VPN connected? (if remote)                            ║
║  • Click "Test API" in GUI                               ║
║                                                          ║
║  IT Support: [contact info]                              ║
╚══════════════════════════════════════════════════════════╝
```

---

## Part 8: Security Considerations

### Current Setup

✅ **Secure:**
- All traffic encrypted via SSH tunnel
- Server only binds to localhost (not exposed to network)
- Requires valid SSH credentials
- No public internet exposure

⚠️ **Considerations:**
- Shared SSH credentials (`aleks` account)
- No per-user authentication/authorization
- No usage logging/auditing
- No rate limiting

### Recommendations for Production

If deploying widely, consider:

1. **Individual user accounts:**
   - Each staff member has own SSH key
   - Separate HANS user account per person
   - Enables usage tracking and accountability

2. **Authentication layer:**
   - Add login to GUI
   - API token authentication
   - LDAP/Active Directory integration

3. **Monitoring:**
   - Log all queries (with user attribution)
   - Monitor API usage patterns
   - Alert on suspicious activity

4. **Rate limiting:**
   - Prevent abuse/overuse
   - Fair sharing of resources
   - Protects server from overload

---

## Part 9: File Checklist

Files needed on each staff PC:

### Essential
- [x] `htw_assistant_api_gui.py` - Main GUI application

### Optional but Recommended
- [ ] `QUICK_START.md` - Quick reference
- [ ] `launch_hans.sh` / `.command` / `.bat` - Launcher script
- [ ] Desktop shortcut
- [ ] Printed quick reference card

### Not Needed on Staff PCs
- ❌ `api_server.py` - Only on server
- ❌ `hans_db_agents.py` - Only on server
- ❌ `connect_to_hans.sh` - Helpful but not required
- ❌ Database files - Only on server
- ❌ Training data - Only on server

---

## Part 10: Testing Checklist

After setup on each PC, verify:

- [ ] Python version 3.8+ installed
- [ ] Tkinter available
- [ ] `requests` package installed
- [ ] Can SSH to server: `ssh aleks@10.2.100.35`
- [ ] Tunnel starts successfully
- [ ] GUI launches without errors
- [ ] Status shows green ✅
- [ ] Can submit test query: "What are the admission requirements?"
- [ ] Response received within 30 seconds
- [ ] Sources displayed correctly
- [ ] Can copy response to clipboard
- [ ] Can close GUI cleanly
- [ ] Tunnel stops with Ctrl+C

---

## Support Contact

**For technical issues:**
- Server problems: [Admin contact]
- Network/VPN: HTW IT Support
- GUI bugs: [Your contact]

**For content/answer quality:**
- Student Services department
- HANS system administrator

---

## Summary

**For each new staff PC:**
1. Install Python 3.8+ with Tkinter + requests (5 minutes)
2. Copy `htw_assistant_api_gui.py` to `~/HANS/` (1 minute)
3. Test SSH access to server (1 minute)
4. Create launcher script (optional, 2 minutes)
5. Train staff on usage (5 minutes)

**Total time per PC: ~10-15 minutes**

**Daily usage for staff:**
1. Start tunnel (15 seconds)
2. Launch GUI (5 seconds)
3. Use HANS as needed
4. Close when done (5 seconds)

**Total overhead per session: ~25 seconds**
