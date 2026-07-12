#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email Screenshot SOAR App Connector
Renders email bodies (text/plain or text/html) as PNG screenshots
simulating an Outlook-style email client view.

Per Splunk SOAR documentation:
  - html2image declared in pip3_dependencies → auto-installed on app import
  - __init__.py required in app directory
  - Custom view: email_screenshot_view.py + email_screenshot_view.html
  - System requirement: Google Chrome on SOAR appliance
    Amazon Linux 2023:
      wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
      sudo dnf install ./google-chrome-stable_current_x86_64.rpm -y
"""

import phantom.app as phantom
from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult

import base64
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone


class EmailScreenshotConnector(BaseConnector):

    def __init__(self):
        super(EmailScreenshotConnector, self).__init__()

    def initialize(self):
        return phantom.APP_SUCCESS

    def finalize(self):
        return phantom.APP_SUCCESS

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_render_engine(self):
        import shutil
        try:
            from html2image import Html2Image  # noqa: F401
            chrome = (
                shutil.which("google-chrome-stable")
                or shutil.which("google-chrome")
                or shutil.which("chromium-browser")
                or shutil.which("chromium")
            )
            if chrome:
                return "html2image (Chrome: {})".format(chrome), None
            return (
                None,
                "html2image installed but no Chrome/Chromium binary in PATH. "
                "Install: wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm "
                "&& sudo dnf install ./google-chrome-stable_current_x86_64.rpm -y"
            )
        except ImportError:
            pass

        try:
            import imgkit  # noqa: F401
            wk = shutil.which("wkhtmltoimage")
            if wk:
                return "imgkit (wkhtmltoimage: {})".format(wk), None
            return None, "imgkit available but wkhtmltoimage binary not found."
        except ImportError:
            pass

        return (
            None,
            "No rendering engine found. html2image auto-installs via pip3_dependencies. "
            "Also ensure Chrome/Chromium is installed on the appliance."
        )

    def _render_to_png(self, html_str, output_path, tmpdir, width):
        """
        Render HTML to PNG.
        Uses a large canvas height (8000px) so Chromium renders the full
        email without clipping. The actual PNG height is determined by content.
        Returns True on success, False otherwise.
        """
        import shutil

        # --- html2image (preferred) ---
        try:
            from html2image import Html2Image

            chrome = (
                shutil.which("google-chrome-stable")
                or shutil.which("google-chrome")
                or shutil.which("chromium-browser")
                or shutil.which("chromium")
            )
            kwargs = {
                "output_path": tmpdir,
                "custom_flags": [
                    "--no-sandbox",
                    "--disable-gpu",
                    "--disable-dev-shm-usage",
                    "--headless",
                    "--disable-software-rasterizer",
                    "--hide-scrollbars",          # ← explicit: hide scrollbars
                    "--run-all-compositor-stages-before-draw",
                    # ── SECURITY: never fetch remote resources ──
                    # We render attacker-controlled email HTML. Resolving any
                    # hostname to NOTFOUND blocks all outbound requests, so
                    # tracking pixels / remote images / CSS / fonts cannot fire
                    # (no "mail was opened" callback to the phisher) and no SSRF
                    # against internal hosts is possible. Local html_str rendering
                    # needs no DNS, so fidelity is unaffected.
                    "--host-resolver-rules=MAP * ~NOTFOUND",
                    "--no-proxy-server",
                    "--dns-prefetch-disable",
                    # ── SECURITY: disable JavaScript at the engine level ──
                    # A static email screenshot never needs JS. Disabling it in
                    # Blink neutralises ALL script-execution vectors regardless of
                    # HTML-sanitiser bypasses — e.g. `<img src=x/onerror=…>`, where
                    # `/` is a valid HTML attribute separator the regex can't catch.
                    # The regex sanitiser + network block remain as defense in depth.
                    "--blink-settings=scriptEnabled=false",
                ],
            }
            if chrome:
                kwargs["browser_executable"] = chrome

            hti = Html2Image(**kwargs)
            # Large canvas → Chromium renders full content without overflow
            # The HTML uses height:auto so the actual content determines the size
            hti.screenshot(
                html_str=html_str,
                save_as=os.path.basename(output_path),
                size=(width, 8000),
            )
            if os.path.exists(output_path):
                # Crop to actual content height using Pillow if available
                self._try_autocrop(output_path)
                return True
        except Exception as e:
            self.save_progress("html2image failed: {}. Trying imgkit...".format(str(e)))

        # --- imgkit fallback ---
        try:
            import imgkit
            options = {
                "width": str(width),
                "encoding": "UTF-8",
                "quiet": "",
                "format": "png",
                "disable-smart-width": "",
            }
            imgkit.from_string(html_str, output_path, options=options)
            if os.path.exists(output_path):
                return True
        except Exception as e:
            self.save_progress("imgkit fallback failed: {}".format(str(e)))

        return False

    def _try_autocrop(self, png_path):
        """
        Crop PNG to actual content height by removing empty background at bottom.
        Uses numpy for fast row scanning. Non-fatal if Pillow unavailable.
        """
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(png_path).convert("RGB")
            arr = np.array(img)
            height, width, _ = arr.shape

            if height < 100:
                return

            # Detect background colour from bottom-right corner (20x20 pixels)
            sample = arr[max(0, height - 20):height, max(0, width - 20):width]
            bg_color = np.median(sample.reshape(-1, 3), axis=0)

            # Per-row maximum colour distance from background
            diff = np.abs(arr.astype(np.int32) - bg_color.astype(np.int32))
            row_max_diff = diff.max(axis=(1, 2))

            THRESHOLD = 15  # pixels differing by > 15 = content
            content_rows = np.where(row_max_diff > THRESHOLD)[0]
            if len(content_rows) == 0:
                return

            last_content_row = int(content_rows[-1])

            # Only crop when there is a meaningful empty area (> 50px)
            if last_content_row < height - 50:
                crop_height = min(last_content_row + 40, height)
                Image.fromarray(arr[:crop_height]).save(png_path, "PNG", optimize=True)
                self.save_progress(
                    "Auto-cropped: {}px -> {}px (saved {}px)".format(
                        height, crop_height, height - crop_height
                    )
                )
        except Exception as e:
            self.save_progress("Auto-crop skipped: {}".format(str(e)))

    def _make_filename(self, prefix=""):
        """
        Generate a unique filename:
          {prefix_}YYYYMMDD_HHMMSS_{8-hex-chars}.png
        Example: phishing_20260220_143012_a3f7c921.png
        """
        ts  = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        # Sanitise prefix: only alphanumeric + underscore, max 32 chars
        safe_prefix = re.sub(r"[^A-Za-z0-9_]", "_", prefix)[:32] if prefix else ""
        if safe_prefix and not safe_prefix.endswith("_"):
            safe_prefix += "_"
        return "{}{}_{}.png".format(safe_prefix, ts, uid)

    def _store_to_vault(self, raw_bytes, filename):
        """
        Store PNG bytes in the SOAR Vault, then create an Artifact
        'email screenshot' on the container that carries vault_id + filename.
        Returns dict with vault_id and artifact_id.

        The temporary file written for vault_add is always removed afterwards
        (vault_add copies it into the Vault store), so /tmp does not accumulate
        PNGs over repeated runs.
        """
        try:
            import phantom.vault as phantom_vault
            container_id = self.get_container_id()

            # --- 1. Write temp file and add to Vault ---
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".png", prefix="email_screenshot_"
            ) as tmp:
                tmp.write(raw_bytes)
                tmp_path = tmp.name

            try:
                vault_ret = phantom_vault.vault_add(
                    container=container_id,
                    file_location=tmp_path,
                    file_name=filename,
                )
                if not (vault_ret and vault_ret[0]):
                    self.save_progress("Vault warning: {}".format(vault_ret))
                    return {"vault_id": "", "artifact_id": ""}

                vault_id = vault_ret[2]
                self.save_progress("Vault stored: {} → {}".format(filename, vault_id))

                # --- 2. Create Artifact on the container ---
                artifact_id = ""
                try:
                    artifact = {
                        "name":         "email screenshot",
                        "label":        "artifact",
                        "container_id": container_id,
                        "source_data_identifier": filename,
                        "cef": {
                            "vaultId":  vault_id,
                            "fileName": filename,
                        },
                        "cef_types": {
                            "vaultId":  ["vault id"],
                            "fileName": [],
                        },
                        "run_automation": False,
                    }
                    import phantom.rules as ph_rules
                    ret_val, msg, artifact_id_list = ph_rules.add_artifact(
                        container=container_id,
                        artifact=artifact,
                    )
                    if ret_val and artifact_id_list:
                        artifact_id = str(artifact_id_list[0])
                        self.save_progress("Artifact created: id={}".format(artifact_id))
                    else:
                        self.save_progress("Artifact creation warning: {}".format(msg))
                except Exception as art_err:
                    self.save_progress("Artifact creation failed (non-fatal): {}".format(str(art_err)))

                return {
                    "vault_id":    vault_id,
                    "artifact_id": artifact_id,
                }
            finally:
                # vault_add copies the file into the Vault — remove the temp copy
                # (NamedTemporaryFile was opened with delete=False).
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except Exception as e:
            self.save_progress("Vault storage failed (non-fatal): {}".format(str(e)))
            return None

    # ------------------------------------------------------------------
    # Action: test connectivity
    # ------------------------------------------------------------------

    def _handle_test_connectivity(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        self.save_progress("Checking rendering engine...")

        engine, error = self._detect_render_engine()
        if engine is None:
            return action_result.set_status(phantom.APP_ERROR, "Engine not found: {}".format(error))

        self.save_progress("Engine found: {}".format(engine))
        return action_result.set_status(
            phantom.APP_SUCCESS, "Test Connectivity Passed. Engine: {}".format(engine)
        )

    # ------------------------------------------------------------------
    # Action: render email
    # ------------------------------------------------------------------

    def _handle_render_email(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        self.save_progress("Starting email rendering...")

        email_body       = param.get("email_body", "")
        content_type     = param.get("content_type", "text/html").lower().strip()
        subject          = param.get("subject", "(No Subject)")
        sender           = param.get("sender", "")
        recipient        = param.get("recipient", "")
        date_str         = param.get("date", "")
        # Clamp to a sane range: guards against a huge canvas (memory DoS) and
        # against 0/negative values. SOAR validates numeric type, not range.
        width            = max(320, min(int(param.get("width", 900) or 900), 2000))
        filename_prefix  = param.get("filename_prefix", "").strip()

        if not email_body:
            return action_result.set_status(phantom.APP_ERROR, "email_body is required")

        if content_type not in ("text/html", "text/plain"):
            return action_result.set_status(
                phantom.APP_ERROR,
                "content_type must be 'text/html' or 'text/plain'"
            )

        try:
            from email_screenshot_utils import render_html_email, render_plain_email

            if content_type == "text/html":
                full_html = render_html_email(email_body, subject, sender, recipient, date_str, width)
            else:
                full_html = render_plain_email(email_body, subject, sender, recipient, date_str, width)

            # Generate unique filename
            filename = self._make_filename(prefix=filename_prefix)
            self.save_progress("Output filename: {}".format(filename))

            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = os.path.join(tmpdir, filename)

                if not self._render_to_png(full_html, output_path, tmpdir, width):
                    return action_result.set_status(
                        phantom.APP_ERROR,
                        "Rendering failed. Check Chrome installation and html2image setup."
                    )

                with open(output_path, "rb") as f:
                    raw_bytes = f.read()

                file_size  = len(raw_bytes)
                b64_data   = base64.b64encode(raw_bytes).decode("utf-8")
                vault_info = self._store_to_vault(raw_bytes, filename)
                vault_id   = vault_info.get("vault_id", "")   if vault_info else ""
                artifact_id = vault_info.get("artifact_id", "") if vault_info else ""

                action_result.add_data({
                    "base64_data":           b64_data,
                    "file_size_bytes":       file_size,
                    "file_name":             filename,
                    "vault_id":              vault_id,
                    "artifact_id":           artifact_id,
                    "subject":               subject,
                    "sender":                sender,
                    "content_type_rendered": content_type,
                })
                action_result.update_summary({
                    "status":          "success",
                    "vault_id":        vault_id,
                    "artifact_id":     artifact_id,
                    "file_name":       filename,
                    "file_size_bytes": file_size,
                    "subject":         subject,
                })

                self.save_progress("Done. File: {} | Size: {} bytes.".format(filename, file_size))
                return action_result.set_status(phantom.APP_SUCCESS, "Email rendered as PNG successfully.")

        except Exception as e:
            return action_result.set_status(phantom.APP_ERROR, "Rendering failed: {}".format(str(e)))

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def handle_action(self, param):
        action_id = self.get_action_identifier()
        self.debug_print("action_id: {}".format(action_id))
        dispatch = {
            "test_connectivity": self._handle_test_connectivity,
            "render_email":      self._handle_render_email,
        }
        handler = dispatch.get(action_id)
        if handler:
            return handler(param)
        self.save_progress("Unsupported action: {}".format(action_id))
        return phantom.APP_ERROR


# ----------------------------------------------------------------------
# Local testing: phenv python3 email_screenshot_connector.py input.json
# ----------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: phenv python3 email_screenshot_connector.py <input_json>")
        sys.exit(1)
    with open(sys.argv[1]) as fh:
        in_json = json.load(fh)
    print(json.dumps(in_json, indent=4))
    connector = EmailScreenshotConnector()
    connector.print_progress_message = True
    connector.run(json.dumps(in_json))
    print(json.dumps(json.loads(connector.get_status_message()), indent=4))


if __name__ == "__main__":
    main()
