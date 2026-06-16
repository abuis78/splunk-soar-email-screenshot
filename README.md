# Email Screenshot — Splunk SOAR App

**Publisher:** Andreas Buis  
**Contributors:** Andreas Buis, Created with Claude (model claude-sonnet-4-6)  
**Version:** 1.4.0  
**Min. Phantom Version:** 6.0.0  
**Python:** 3  

---

## Overview

This app renders email content (HTML or plain text) as a PNG screenshot in Outlook style and stores the result in the SOAR vault. The image is displayed directly in the Investigation widget.

**Use cases:**
- Phishing analysis with visual email screenshot
- Incident documentation
- Threat intelligence reports

---

## Prerequisites

### Python Dependencies (auto-installed by SOAR)

The following Python modules are installed automatically by SOAR via `pip3_dependencies` on app import:

| Module | Version | Purpose |
|--------|---------|---------|
| `html2image` | latest | HTML → PNG rendering via Chromium |
| `Pillow` | latest | Auto-crop PNG to content height |

> **Note:** `numpy` is already included in the SOAR Python environment and does not need to be installed separately.

### OS Dependency: Google Chrome / Chromium

`html2image` requires an installed Chrome or Chromium binary on the SOAR appliance operating system. This is a **system dependency** and **cannot** be installed via pip.

---

## Browser Installation

### Red Hat Enterprise Linux (RHEL) 8 / 9

#### Option 1: Google Chrome (recommended)

```bash
# Download RPM directly from Google and install
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
sudo dnf install ./google-chrome-stable_current_x86_64.rpm -y

# Verify
google-chrome-stable --version
```

#### Option 2: Chromium via EPEL

```bash
# Enable EPEL repository (if not already active)
sudo dnf install epel-release -y

# Install Chromium
sudo dnf install chromium -y

# Verify
chromium --version
```

> **Note for RHEL 9:** Chromium is no longer available via EPEL in RHEL 9. Google Chrome (Option 1) is the more reliable choice.

---

### Amazon Linux 2023 (AL2023)

Chromium is **not available** in the standard Amazon Linux 2023 repositories. Google Chrome must be installed directly from Google.

#### Install Google Chrome

```bash
# 1. Download the RPM
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm

# 2. Install required system dependencies
sudo dnf install -y libgbm libxkbcommon libxss alsa-lib atk cups-libs gtk3 \
    libdrm libxcomposite libxdamage libxfixes libxrandr mesa-libgbm pango \
    xorg-x11-fonts-75dpi xorg-x11-fonts-Type1

# 3. Install Chrome
sudo dnf install ./google-chrome-stable_current_x86_64.rpm -y

# 4. Verify
google-chrome-stable --version
# Expected output: Google Chrome 1xx.x.xxxx.xxx

# 5. Optional headless test
google-chrome-stable --headless --no-sandbox --disable-gpu \
    --dump-dom https://example.com > /dev/null && echo "Chrome OK"
```

#### Troubleshooting AL2023

If the dnf install fails with dependency errors:

```bash
# Resolve all missing dependencies at once
sudo dnf install -y $(rpm -qpR ./google-chrome-stable_current_x86_64.rpm \
    | grep -v rpmlib | tr '\n' ' ') 2>/dev/null || true
sudo dnf install ./google-chrome-stable_current_x86_64.rpm --skip-broken -y
```

---

### Amazon Linux 2 (AL2) — Legacy

```bash
# Download Google Chrome RPM
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm

# Install dependencies via yum
sudo yum install -y libgbm libxkbcommon libxss alsa-lib atk cups-libs gtk3

# Install Chrome
sudo yum localinstall ./google-chrome-stable_current_x86_64.rpm -y

# Verify
google-chrome-stable --version
```

---

## App Installation in SOAR

1. Open **SOAR UI** → Apps → **Install App**
2. Upload `email_screenshot_v1.4.0.tar`
3. SOAR automatically installs `html2image` and `Pillow` via pip
4. **Create asset:** Apps → Email Screenshot → **Configure New Asset**
   - Asset Name: e.g. `email screenshot`
   - No additional configuration fields required
5. Run **Test Connectivity** → should report which Chrome binary was found

---

## Test Connectivity

The test checks:
1. Is `html2image` installed and importable?
2. Is a Chrome/Chromium binary available in the system PATH?

**Successful output:**
```
Test Connectivity Passed. Engine: html2image (Chrome: /usr/bin/google-chrome-stable)
```

**Error message if browser is missing:**
```
html2image installed but no Chrome/Chromium binary in PATH.
Install: wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
         && sudo dnf install ./google-chrome-stable_current_x86_64.rpm -y
```

---

## Actions

### render email

Renders an email body as an Outlook-style PNG screenshot.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `email_body` | string | ✅ | — | Email content (HTML or plain text) |
| `content_type` | string | | `text/html` | `text/html` or `text/plain` |
| `subject` | string | | `(No Subject)` | Subject line |
| `sender` | string | | — | Sender address or display name |
| `recipient` | string | | — | Recipient address |
| `date` | string | | — | Date e.g. `Thu, 20 Feb 2026 14:30:00 +0100` |
| `width` | numeric | | `900` | Screenshot width in pixels |
| `filename_prefix` | string | | — | Optional output-filename prefix (alphanumeric + `_`, max 32 chars) |

**Output data paths:**

| Data path | Type | Description |
|-----------|------|-------------|
| `action_result.data.*.vault_id` | string | SOAR vault ID of the PNG file |
| `action_result.data.*.artifact_id` | string | ID of the `email screenshot` artifact created on the container |
| `action_result.data.*.file_name` | string | Generated PNG filename |
| `action_result.data.*.base64_data` | string | Base64-encoded PNG (for direct downstream use; not shown as a table column) |
| `action_result.data.*.file_size_bytes` | numeric | File size in bytes |
| `action_result.data.*.subject` | string | Subject line |
| `action_result.data.*.sender` | string | Sender address |
| `action_result.data.*.content_type_rendered` | string | Rendered content type |

---

## Widget Display

The app uses a **custom widget** that displays the screenshot directly in the Investigation panel. The widget supports:

- **Inline display** of the PNG via base64
- **Lightbox zoom** by clicking on the image
- Display of metadata (sender, recipient, date, file size)
- Vault ID for direct access to the stored file

If the widget is not displayed:
1. Open the Investigation page
2. Click **Manage Widgets**
3. Toggle **Email Screenshot** to **On**
4. Click **Save Layout** → **Close**

---

## Rendering Engine Fallback Chain

```
html2image (Chromium-based)       ← Primary, auto-installed via pip3_dependencies
    │
    └─ Chrome not found?
         ↓
imgkit (wkhtmltoimage)            ← Fallback, install manually if needed
         ↓
    neither available → APP_ERROR
```

### Install imgkit fallback manually

```bash
# RHEL / CentOS
sudo dnf install wkhtmltopdf -y

# Amazon Linux 2023 (not in repos — direct download required)
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/\
wkhtmltox-0.12.6.1-3.almalinux9.x86_64.rpm
sudo dnf install ./wkhtmltox-0.12.6.1-3.almalinux9.x86_64.rpm -y
```

---

## Auto-Crop Algorithm

Since `html2image` renders on a fixed canvas of `8000px` height, the PNG is automatically cropped to the actual content height after rendering:

1. **Detect background colour** — median of the bottom-right 20×20 pixels
2. **Row-by-row scan** (numpy, from bottom up) — maximum colour distance per row
3. **Threshold of 15 RGB units** — rows differing by less are considered background
4. **+40px padding** at the bottom edge
5. **Only active if >50px empty space** is present

Typical savings: **30–60% of PNG file size**.

---

## Security Model

This app renders **attacker-controlled HTML** (phishing email bodies) in headless Chromium. Two layers protect the SOAR appliance:

1. **No outbound network during rendering.** Chrome is started with `--host-resolver-rules=MAP * ~NOTFOUND` (plus `--no-proxy-server`, `--dns-prefetch-disable`). Every hostname resolution fails, so the email **cannot fire tracking pixels, load remote images/CSS/fonts, or reach internal hosts (SSRF)**. The phisher gets no "mail was opened" callback. Local rendering of the supplied HTML needs no DNS, so visual fidelity is unaffected.
2. **Active content is stripped.** Before rendering, `<script>`, `<iframe>`, `<object>`, `<embed>`, inline `on*=` event handlers and `javascript:` URIs are removed from the email body (defense in depth, in case a binary ever runs with network access).

> Chrome still runs with `--no-sandbox` (required for the `phantom` service user on most appliances). The two layers above are what keep hostile email content contained.

---

## Known Limitations

- **External images in HTML emails** are not loaded — remote fetches are deliberately blocked (see Security Model). Images appear as empty placeholders. This is intentional, not a bug.
- **Fonts** in the screenshot reflect the system font of the SOAR appliance OS, not the original email client.
- **Unicode / Emoji** require corresponding system fonts. If emoji appear as boxes: `sudo dnf install google-noto-emoji-fonts -y`
- **Very long emails** (>500 KB HTML) may result in long rendering times (>30s).

---

## Troubleshooting

### Emoji appear as ☐

```bash
sudo dnf install google-noto-emoji-fonts -y
# or
sudo dnf install google-noto-color-emoji-fonts -y
fc-cache -fv
```

### Chrome does not start / permission errors

```bash
# SOAR runs Chrome as the phantom user — ensure the user can execute Chrome
which google-chrome-stable
ls -la $(which google-chrome-stable)

# Sandbox issue on some systems — already mitigated via --no-sandbox flag
google-chrome-stable --headless --no-sandbox --disable-gpu --dump-dom about:blank
```

### Check app interface log

```bash
# Custom view errors
tail -f /var/log/phantom/app_interface.log

# Rendering errors
tail -f /var/log/phantom/spawn.log
```

### html2image not installed

```bash
# Run SOAR pip manually
/opt/phantom/usr/bin/pip3 install html2image Pillow
```

---

## Local Testing (SSH to SOAR Appliance)

```bash
# Create test JSON
cat > /tmp/test_render.json << 'ENDJSON'
{
    "identifier": "render_email",
    "asset_id": "1",
    "parameters": [{
        "email_body": "<h1>Test</h1><p>Hello World</p>",
        "content_type": "text/html",
        "subject": "Test Email",
        "sender": "test@example.com",
        "recipient": "analyst@company.com",
        "date": "Thu, 20 Feb 2026 14:30:00 +0100"
    }],
    "config": {}
}
ENDJSON

# Run
cd /opt/phantom/apps/email_screenshot_*/
phenv python3 email_screenshot_connector.py /tmp/test_render.json
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.4.0 | 2026-06-16 | **Security:** block all outbound network during rendering (`--host-resolver-rules=MAP * ~NOTFOUND`) so phishing mails can't fire tracking pixels / SSRF; strip `<script>`, `<iframe>`, `<object>`, `<embed>`, inline `on*=` handlers and `javascript:` URIs from the email body before rendering. **Fix:** always delete the temp PNG after vault add (no more `/tmp` leak). base64 no longer a result-table column (DB/UI bloat). Unknown action now returns `APP_ERROR`. |
| 1.3.0 | 2026-02-23 | First public release. Create an `email screenshot` artifact on the container (vaultId/fileName CEF); expose `artifact_id` in output + widget; `filename_prefix` parameter |
| 1.2.0 | 2026-02-20 | Added Pillow auto-crop, numpy-based background detection algorithm |
| 1.1.0 | 2026-02-20 | Custom widget (email_screenshot_view.py + .html), scrollbar fix, `--hide-scrollbars` Chrome flag |
| 1.0.0 | 2026-02-19 | Initial release, `render_email` and `test_connectivity` actions |
