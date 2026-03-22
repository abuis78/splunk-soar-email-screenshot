#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email Screenshot Utils
Generates Outlook-style HTML wrappers for email body rendering.

Key design decisions:
  - overflow: visible (never hidden) everywhere — no scrollbars in screenshot
  - html, body: width fixed, height auto — Chromium crops to content
  - html2image size=(width, 8000) — large enough canvas, cropped by content
"""

import html as html_lib
import re


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_initials(sender: str) -> str:
    name_part = sender.split("<")[0].strip().strip('"')
    if not name_part:
        parts = sender.replace("@", " ").replace(".", " ").split()
    else:
        parts = name_part.split()
    initials = "".join(p[0].upper() for p in parts if p)[:2]
    return initials if initials else "?"


def _avatar_color(sender: str) -> str:
    colours = [
        "#0078d4", "#107c10", "#d83b01", "#5c2d91",
        "#008272", "#004b50", "#a4262c", "#ca5010",
    ]
    idx = sum(ord(c) for c in sender) % len(colours)
    return colours[idx]


# ---------------------------------------------------------------------------
# Core HTML builder
# ---------------------------------------------------------------------------

def _build_wrapper_html(
    body_inner: str,
    subject: str,
    sender: str,
    recipient: str,
    date_str: str,
    width: int,
    is_html: bool,
) -> str:
    """
    Wrap email content in Outlook-style chrome.

    Critical rendering rules to avoid scrollbars:
      - html, body: overflow visible, height auto
      - All container divs: overflow visible
      - The outer window div has a fixed pixel width but auto height
    """
    initials  = _extract_initials(sender)
    avatar_bg = _avatar_color(sender)

    subject_esc   = html_lib.escape(subject or "(No Subject)")
    sender_esc    = html_lib.escape(sender or "")
    recipient_esc = html_lib.escape(recipient or "")
    date_esc      = html_lib.escape(date_str or "")

    # Monospace style only for plain-text
    body_style = (
        "font-family:'Courier New',Courier,monospace;"
        "font-size:13px;line-height:1.6;color:#201f1e;"
        "white-space:pre-wrap;word-break:break-word;"
    ) if not is_html else (
        "font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;"
        "font-size:13px;line-height:1.5;color:#201f1e;"
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
/* ── Reset — NO overflow restrictions anywhere ── */
*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}
html, body {{
  width: {width}px;
  height: auto;
  overflow: visible;
  background: #f3f2f1;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}}

/* ── Outer window ── */
.ow {{
  width: {width}px;
  background: #ffffff;
  border: 1px solid #c8c8c8;
  border-radius: 4px 4px 0 0;
  overflow: visible;  /* NEVER clip content */
}}

/* ── Title bar ── */
.tb {{
  background: #0078d4;
  padding: 0 10px;
  height: 32px;
  display: flex;
  align-items: center;
  border-radius: 4px 4px 0 0;
  gap: 8px;
}}
.tb-icon {{
  width: 16px; height: 16px;
  flex-shrink: 0;
}}
.tb-title {{
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.tb-btns {{ display: flex; gap: 6px; }}
.tb-btn {{
  width: 12px; height: 12px;
  border-radius: 50%;
  display: inline-block;
}}
.tb-close  {{ background: #ff5f57; }}
.tb-min    {{ background: #febc2e; }}
.tb-max    {{ background: #28c840; }}

/* ── Toolbar ── */
.tbar {{
  background: #f8f8f8;
  border-bottom: 1px solid #e1e1e1;
  padding: 5px 12px;
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}}
.tbar-btn {{
  padding: 3px 9px;
  background: #fff;
  border: 1px solid #d1d1d1;
  border-radius: 2px;
  font-size: 11px;
  color: #333;
  font-family: 'Segoe UI', sans-serif;
}}
.tbar-btn.primary {{
  background: #0078d4;
  color: #fff;
  border-color: #0078d4;
}}

/* ── Email header ── */
.eh {{
  padding: 14px 16px 12px;
  border-bottom: 1px solid #edebe9;
  overflow: visible;
}}
.eh-subject {{
  font-size: 17px;
  font-weight: 600;
  color: #201f1e;
  margin-bottom: 10px;
  line-height: 1.3;
  word-break: break-word;
}}
.eh-sender-row {{
  display: flex;
  align-items: flex-start;
  gap: 10px;
  overflow: visible;
}}
.avatar {{
  width: 40px; height: 40px;
  border-radius: 50%;
  background: {avatar_bg};
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
.eh-meta {{ flex: 1; min-width: 0; }}
.eh-name {{
  font-size: 13px;
  font-weight: 600;
  color: #201f1e;
  word-break: break-all;
}}
.eh-to {{
  font-size: 12px;
  color: #605e5c;
  margin-top: 1px;
  word-break: break-all;
}}
.eh-date {{
  font-size: 12px;
  color: #605e5c;
  text-align: right;
  flex-shrink: 0;
  white-space: nowrap;
}}

/* ── Email body ── */
.eb {{
  padding: 16px;
  background: #fff;
  overflow: visible;  /* critical — no scroll */
}}
.eb-inner {{
  {body_style}
  overflow: visible;
  word-break: break-word;
}}
/* Reset any overflow from the embedded HTML email */
.eb-inner * {{
  max-width: 100%;
}}
.eb-inner table {{
  max-width: 100%;
  table-layout: auto;
}}
</style>
</head>
<body>
<div class="ow">

  <!-- Title bar -->
  <div class="tb">
    <svg class="tb-icon" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="16" height="16" rx="2" fill="#005a9e"/>
      <path d="M2 5h12L8 10 2 5z" fill="white"/>
      <path d="M2 5v7h12V5" stroke="white" stroke-width="0.8" fill="none"/>
    </svg>
    <span class="tb-title">{subject_esc} – Outlook</span>
    <div class="tb-btns">
      <span class="tb-btn tb-close"></span>
      <span class="tb-btn tb-min"></span>
      <span class="tb-btn tb-max"></span>
    </div>
  </div>

  <!-- Toolbar -->
  <div class="tbar">
    <button class="tbar-btn primary">↩ Antworten</button>
    <button class="tbar-btn">↩↩ Allen antworten</button>
    <button class="tbar-btn">→ Weiterleiten</button>
    <button class="tbar-btn">🗑 Löschen</button>
    <button class="tbar-btn">📁 Archiv</button>
  </div>

  <!-- Email header -->
  <div class="eh">
    <div class="eh-subject">{subject_esc}</div>
    <div class="eh-sender-row">
      <div class="avatar">{initials}</div>
      <div class="eh-meta">
        <div class="eh-name">{sender_esc}</div>
        <div class="eh-to">An: {recipient_esc}</div>
      </div>
      <div class="eh-date">{date_esc}</div>
    </div>
  </div>

  <!-- Email body -->
  <div class="eb">
    <div class="eb-inner">
{body_inner}
    </div>
  </div>

</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_html_email(
    email_body: str,
    subject: str = "",
    sender: str = "",
    recipient: str = "",
    date_str: str = "",
    width: int = 900,
) -> str:
    """Wrap an HTML email body in Outlook-style chrome. No scrollbars."""

    # Strip outer HTML skeleton — keep only the inner body content
    body = email_body
    body = re.sub(r"(?is)<!doctype[^>]*>", "", body)
    body = re.sub(r"(?is)<html[^>]*>|</html>", "", body)
    body = re.sub(r"(?is)<head[^>]*>.*?</head>", "", body)
    body = re.sub(r"(?is)<body[^>]*>|</body>", "", body)
    body = body.strip()

    # Neutralise any scroll / overflow rules inside the email
    body = re.sub(
        r"(?i)(overflow\s*:\s*)(scroll|auto|hidden)",
        r"\1visible",
        body,
    )
    # Remove fixed heights that would cause scrollbars
    body = re.sub(
        r"(?i)(height\s*:\s*)\d+px",
        r"\1auto",
        body,
    )

    return _build_wrapper_html(body, subject, sender, recipient, date_str, width, is_html=True)


def render_plain_email(
    email_body: str,
    subject: str = "",
    sender: str = "",
    recipient: str = "",
    date_str: str = "",
    width: int = 900,
) -> str:
    """Wrap a plain-text email body in Outlook-style chrome. No scrollbars."""
    escaped = html_lib.escape(email_body)
    return _build_wrapper_html(
        escaped, subject, sender, recipient, date_str, width, is_html=False
    )
