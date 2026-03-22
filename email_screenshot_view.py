#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Email Screenshot Custom View
Provides context data for the Django HTML template.
Referenced in app JSON as: "view": "email_screenshot_view.display_email"
"""


def display_email(provides, all_app_runs, context):
    """
    Build context dictionary for the email screenshot widget template.

    :param provides:      Action identifier string (e.g. "render_email")
    :param all_app_runs:  List of (summary, action_results) tuples for all runs
    :param context:       Mutable dict passed to the Django template
    """
    context['results'] = results = []

    for summary, action_results in all_app_runs:
        for result in action_results:
            ctx_result = get_ctx_result(result)
            if ctx_result:
                results.append(ctx_result)

    # Pass the action identifier so the template can use it
    context['action_name'] = provides

    return 'email_screenshot_view.html'


def get_ctx_result(result):
    """
    Convert a single ActionResult into a flat dict for the template.
    Returns None if the result has no usable data.
    """
    ctx = {}

    # Status
    ctx['status']  = result.get_status()
    ctx['message'] = result.get_message() or ''

    # Parameters used when calling the action
    param = result.get_param()
    ctx['subject']       = param.get('subject', '')
    ctx['sender']        = param.get('sender', '')
    ctx['recipient']     = param.get('recipient', '')
    ctx['date']          = param.get('date', '')
    ctx['content_type']  = param.get('content_type', 'text/html')

    # Output data – take the first data item
    data = result.get_data()
    if data:
        item = data[0]
        ctx['vault_id']        = item.get('vault_id', '')
        ctx['artifact_id']     = item.get('artifact_id', '')
        ctx['file_name']       = item.get('file_name', '')
        ctx['base64_data']     = item.get('base64_data', '')
        ctx['file_size_bytes'] = item.get('file_size_bytes', 0)
        ctx['subject']         = item.get('subject', ctx['subject'])
        ctx['sender']          = item.get('sender', ctx['sender'])
        ctx['content_type']    = item.get('content_type_rendered', ctx['content_type'])
    else:
        ctx['vault_id']        = ''
        ctx['artifact_id']     = ''
        ctx['file_name']       = ''
        ctx['base64_data']     = ''
        ctx['file_size_bytes'] = 0

    # Only include entries that actually have an image
    if not ctx.get('base64_data'):
        return None

    return ctx
