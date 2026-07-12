# HANS GUI Quick Start

## Setup (Run Once)

Make sure you're connected to HTW VPN!

## Running the GUI

### Terminal 1: Start SSH Tunnel

```bash
cd /Users/koware/Desktop/HANS/Hans_DB
ssh -N -L 8080:127.0.0.1:8080 aleks@10.2.100.35
```

- Enter your password when prompted
- **Leave this terminal open** (it will appear to hang - that's normal!)
- Don't close it while using the GUI

### Terminal 2: Test Connection (Optional)

```bash
cd /Users/koware/Desktop/HANS/Hans_DB
curl http://127.0.0.1:8080/health
```

Expected: `{"status":"ok","timestamp":"..."}`

### Terminal 2: Run the GUI

```bash
cd /Users/koware/Desktop/HANS/Hans_DB
python3 htw_assistant_api_gui.py
```

The GUI window will open with a green ✅ status!

## To Stop

1. Close the GUI window
2. In Terminal 1, press `Ctrl+C` to stop the tunnel

---

## Troubleshooting

**"Connection refused"?**
- Make sure the SSH tunnel (Terminal 1) is still running
- Check VPN is connected

**"Permission denied"?**
- Verify your password is correct
- Try: `ssh aleks@10.2.100.35` first to test

**GUI shows red status?**
- Run: `curl http://127.0.0.1:8080/health`
- If it fails, restart the tunnel

---

## One-Line Version (After tunnel is running)

```bash
python3 /Users/koware/Desktop/HANS/Hans_DB/htw_assistant_api_gui.py
```
