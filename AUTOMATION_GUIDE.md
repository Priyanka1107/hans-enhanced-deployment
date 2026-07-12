# HANS GUI - Automated Deployment Guide

This guide covers automated launcher scripts that simplify HANS deployment for staff members.

---

## Overview

Instead of manually running two commands (tunnel + GUI), staff can now use **one command** that:
1. ✅ Automatically creates SSH tunnel
2. ✅ Tests connection to API
3. ✅ Launches GUI
4. ✅ Automatically closes tunnel when done

---

## Automated Launchers

### Option 1: Automated Script (Recommended)

**What it does:**
- Creates tunnel in background
- Tests API connection
- Launches GUI
- Closes tunnel when GUI exits
- **One command, fully automated!**

**Files:**
- `launch_hans_auto.sh` (Linux/macOS)
- `launch_hans_auto.bat` (Windows)

**Usage:**
```bash
# Mac/Linux:
./launch_hans_auto.sh

# Windows:
launch_hans_auto.bat
```

**Advantages:**
- ✅ Only one command needed
- ✅ Automatic tunnel cleanup
- ✅ Auto-installs dependencies
- ✅ Connection testing built-in
- ✅ User-friendly error messages

**Disadvantages:**
- ⚠️ Still requires password entry each time
- ⚠️ Slightly more complex script

---

### Option 2: SSH Key Authentication (Most Automated)

**What it does:**
- Eliminates password prompts entirely
- One-click launch with NO typing
- Most user-friendly option

**Setup (one-time per PC):**

#### Step 1: Generate SSH Key (on staff PC)

```bash
# Mac/Linux:
ssh-keygen -t ed25519 -C "hans-gui-access"
# Press Enter for default location
# Press Enter twice for no passphrase (or set one for security)

# Windows:
ssh-keygen -t ed25519 -C "hans-gui-access"
# Press Enter for default location
# Press Enter twice for no passphrase
```

#### Step 2: Copy Key to Server

```bash
# Mac/Linux:
ssh-copy-id aleks@10.2.100.35

# Windows:
type %USERPROFILE%\.ssh\id_ed25519.pub | ssh aleks@10.2.100.35 "cat >> ~/.ssh/authorized_keys"
```

Enter server password one last time. After this, no password needed!

#### Step 3: Test Passwordless Login

```bash
ssh aleks@10.2.100.35
```

Should connect instantly without password prompt!

#### Step 4: Use Automated Launcher

```bash
./launch_hans_auto.sh
# No password prompt! GUI launches immediately!
```

**Advantages:**
- ✅ Zero password prompts
- ✅ True one-click launch
- ✅ Faster startup
- ✅ Better user experience

**Disadvantages:**
- ⚠️ Requires one-time SSH key setup per PC
- ⚠️ Requires server access to add keys

---

### Option 3: Desktop Shortcuts

Make it even easier with desktop icons!

#### Linux Desktop Entry

Create `~/Desktop/HANS.desktop`:

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=HANS Assistant
Comment=HTW Berlin Student Services Assistant
Exec=/home/USERNAME/HANS/launch_hans_auto.sh
Icon=applications-education
Terminal=true
Categories=Education;Office;
```

Make executable:
```bash
chmod +x ~/Desktop/HANS.desktop
```

**Result:** Double-click desktop icon → HANS launches!

---

#### macOS Application Bundle

Create `HANS.app` application:

1. Open **Automator**
2. Choose "Application"
3. Add "Run Shell Script" action
4. Enter:
   ```bash
   cd ~/HANS
   ./launch_hans_auto.sh
   ```
5. Save as `HANS.app` to Desktop

**Result:** Double-click HANS.app → Launches like any Mac app!

---

#### Windows Shortcut

1. Right-click `launch_hans_auto.bat`
2. Click "Create shortcut"
3. Drag shortcut to Desktop
4. Right-click shortcut → Properties
5. Change icon (optional)

**Result:** Double-click shortcut → HANS launches!

---

## Deployment Comparison

### Manual Method (Original)

**Staff workflow:**
```bash
# Terminal 1:
ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35
# Enter password, keep open

# Terminal 2:
cd ~/HANS
python3 htw_assistant_api_gui.py

# When done:
# Close GUI
# Ctrl+C in Terminal 1
```

**Complexity:** ★★★☆☆ (Medium - requires 2 terminals)
**Setup time:** 30 seconds per session
**User skill:** Basic terminal knowledge required

---

### Automated Script Method

**Staff workflow:**
```bash
./launch_hans_auto.sh
# Enter password
# GUI opens automatically
# Close GUI when done (tunnel closes automatically)
```

**Complexity:** ★☆☆☆☆ (Easy - one command)
**Setup time:** 5 seconds per session
**User skill:** Minimal terminal knowledge

---

### SSH Key + Automated Script Method

**Staff workflow:**
```bash
./launch_hans_auto.sh
# GUI opens immediately (no password!)
# Close GUI when done
```

**OR:** Double-click desktop icon!

**Complexity:** ⭐ (Easiest - zero commands)
**Setup time:** 1 second per session
**User skill:** None (just click icon)

---

## Recommended Deployment Strategy

### For Tech-Savvy Staff
Use **Manual Method** - gives them full control and visibility

### For Average Staff
Use **Automated Script** - good balance of simplicity and security

### For Non-Technical Staff
Use **SSH Key + Desktop Icon** - zero learning curve

---

## Setup Instructions for Admin

### Deployment Package Contents

For each staff PC, prepare a folder with:

```
HANS/
├── htw_assistant_api_gui.py      # GUI application
├── launch_hans_auto.sh           # Mac/Linux launcher
├── launch_hans_auto.bat          # Windows launcher
├── QUICK_START.md                # Quick reference
└── setup_ssh_key.sh              # Optional: SSH key setup helper
```

---

### Setup Script for SSH Keys (Optional)

Create `setup_ssh_key.sh` to automate SSH key setup:

```bash
#!/bin/bash
# SSH Key Setup Helper for HANS

echo "================================================"
echo "  HANS SSH Key Setup"
echo "================================================"
echo ""
echo "This script will set up passwordless SSH access"
echo "to the HANS server."
echo ""

# Check if key already exists
if [ -f ~/.ssh/id_ed25519 ]; then
    echo "SSH key already exists: ~/.ssh/id_ed25519"
    read -p "Use existing key? (y/n): " use_existing
    if [[ ! $use_existing =~ ^[Yy]$ ]]; then
        echo "Generating new key..."
        ssh-keygen -t ed25519 -C "hans-gui-access"
    fi
else
    echo "Generating SSH key..."
    ssh-keygen -t ed25519 -C "hans-gui-access" -f ~/.ssh/id_ed25519
fi

echo ""
echo "Copying key to HANS server..."
echo "You will be prompted for your server password ONE LAST TIME."
echo ""

ssh-copy-id aleks@10.2.100.35

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SSH key setup complete!"
    echo ""
    echo "Testing passwordless connection..."
    ssh -o BatchMode=yes aleks@10.2.100.35 "echo 'Connection successful!'"

    if [ $? -eq 0 ]; then
        echo ""
        echo "✓ Passwordless SSH is working!"
        echo ""
        echo "You can now use launch_hans_auto.sh without entering a password."
    else
        echo "✗ Passwordless connection test failed"
        echo "You may still need to enter password when launching HANS."
    fi
else
    echo "✗ Failed to copy SSH key"
    echo "Please check your server password and try again."
    exit 1
fi
```

Make executable:
```bash
chmod +x setup_ssh_key.sh
```

**Usage:**
```bash
./setup_ssh_key.sh
```

---

## Installation Steps (Per PC)

### Method A: With SSH Keys (Most Automated)

1. **Copy files to staff PC**
   ```bash
   mkdir ~/HANS
   cd ~/HANS
   # Copy: htw_assistant_api_gui.py, launch_hans_auto.sh, setup_ssh_key.sh
   chmod +x launch_hans_auto.sh setup_ssh_key.sh
   ```

2. **Install dependencies**
   ```bash
   pip3 install requests
   ```

3. **Set up SSH key**
   ```bash
   ./setup_ssh_key.sh
   # Enter server password once
   ```

4. **Test launch**
   ```bash
   ./launch_hans_auto.sh
   # Should launch without password prompt!
   ```

5. **Create desktop shortcut** (optional)
   ```bash
   # Linux: Copy HANS.desktop to ~/Desktop/
   # macOS: Create Automator app
   # Windows: Create shortcut
   ```

**Total time: 5-10 minutes per PC**

---

### Method B: Without SSH Keys (Password Each Time)

1. **Copy files**
   ```bash
   mkdir ~/HANS
   cd ~/HANS
   # Copy: htw_assistant_api_gui.py, launch_hans_auto.sh
   chmod +x launch_hans_auto.sh
   ```

2. **Install dependencies**
   ```bash
   pip3 install requests
   ```

3. **Test launch**
   ```bash
   ./launch_hans_auto.sh
   # Enter password when prompted
   ```

**Total time: 3-5 minutes per PC**

---

## Troubleshooting Automated Scripts

### Issue: "Permission denied" when running script

**Solution:**
```bash
chmod +x launch_hans_auto.sh
```

---

### Issue: Script asks for password every time (even with SSH key)

**Cause:** SSH key not properly installed

**Solution:**
```bash
# Test SSH key:
ssh -v aleks@10.2.100.35

# Look for lines like:
# "Offering public key: /home/user/.ssh/id_ed25519"
# "Server accepts key"

# If not working, re-run setup:
./setup_ssh_key.sh
```

---

### Issue: Tunnel starts but GUI shows red status

**Cause:** HANS API not running on server

**Solution:**
1. SSH to server: `ssh aleks@10.2.100.35`
2. Check API: `curl http://127.0.0.1:8080/health`
3. Start API if needed: `cd /srv/hans && ./start.sh`

---

### Issue: Script hangs at "Waiting for tunnel to establish"

**Cause:**
- Wrong password entered
- Server unreachable
- VPN not connected

**Solution:**
1. Check VPN connection
2. Test manual SSH: `ssh aleks@10.2.100.35`
3. Verify credentials

---

## Security Considerations

### SSH Keys

**Pros:**
- ✅ More secure than passwords (when passphrase-protected)
- ✅ Can be revoked individually
- ✅ No password transmission over network
- ✅ Better user experience

**Cons:**
- ⚠️ Private key must be protected
- ⚠️ Lost key requires re-setup
- ⚠️ Shared workstations: use passphrase!

**Best Practice:**
- For personal staff PCs: No passphrase OK (convenience)
- For shared workstations: Use passphrase (security)
- Regularly rotate keys (annually)
- Revoke keys when staff leave

---

### Server-Side Key Management

As admin, you can manage authorized keys:

```bash
# On server as aleks:
cd ~/.ssh

# View authorized keys:
cat authorized_keys

# Each line is one staff member's key
# Add comment to track which PC:
ssh-rsa AAAA... staff-pc-room-301

# To revoke access, delete that line
```

---

## Performance Comparison

| Method | Startup Time | User Actions | Setup Time |
|--------|--------------|--------------|------------|
| Manual (2 terminals) | ~30s | 6 steps | 2min |
| Automated script | ~10s | 2 steps | 5min |
| SSH key + script | ~5s | 1 step | 10min |
| SSH key + icon | ~3s | 1 click | 15min |

---

## Update Strategy

When you update the GUI:

1. **Update only the Python file:**
   ```bash
   # On each staff PC:
   cd ~/HANS
   # Replace htw_assistant_api_gui.py with new version
   ```

2. **Launcher scripts don't need updates** (unless server config changes)

3. **SSH keys never need updates** (unless security policy changes)

---

## Recommended Approach

### For 1-5 Staff Members
- Use automated script without SSH keys
- Quick setup, minimal maintenance
- Password entry acceptable for small team

### For 5-20 Staff Members
- Use SSH keys + automated script
- Better experience scales with team size
- 10 minutes setup per PC worth it

### For 20+ Staff Members
- Use SSH keys + desktop shortcuts
- Maximum automation needed
- Consider config management tool (Ansible, etc.)

---

## Summary

**Automation Levels:**

1. **Basic:** Manual 2-command workflow ⭐⭐☆☆☆
2. **Good:** Automated script with password ⭐⭐⭐☆☆
3. **Better:** Automated script with SSH key ⭐⭐⭐⭐☆
4. **Best:** SSH key + desktop icon ⭐⭐⭐⭐⭐

**Recommendation:**
- Start with **Level 2** (automated script)
- Upgrade to **Level 3** (SSH key) as staff become comfortable
- Add **Level 4** (desktop icons) for non-technical staff

**Files to Deploy:**
- **Essential:** `htw_assistant_api_gui.py`
- **Recommended:** `launch_hans_auto.sh` or `.bat`
- **Optional:** `setup_ssh_key.sh`, desktop shortcuts

Total deployment time with full automation: **10-15 minutes per PC**
Daily usage time for staff: **< 5 seconds** (one click!)
