#!/usr/bin/env python3
"""
Build script for head-to-head/index.html
Ensures the back navigation link persists across regenerations
"""

import re
import os

def ensure_back_nav_link(h2h_path='head-to-head/index.html'):
    """
    Injects the back navigation link into the head-to-head HTML
    if it's missing, ensuring it persists across HTML regenerations.
    """

    back_nav_html = '''<div style="max-width: 1600px; margin: 0 auto; padding: 2rem 2rem 0;">
  <a href="../index.html" style="font-size: 13px; color: #1D9E75; text-decoration: none; display: inline-block; margin-bottom: 8px;">&larr; All runners</a>
</div>'''

    with open(h2h_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Check if back nav already exists
    if '&larr; All runners' in html:
        print('✓ Back navigation link already present')
        return

    # Insert after <body> tag, before <div class="page">
    pattern = r'(<body>)\n(<div class="page">)'
    replacement = rf'\1\n{back_nav_html}\n\2'

    if re.search(pattern, html):
        html = re.sub(pattern, replacement, html)
        with open(h2h_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print('✓ Added back navigation link to head-to-head')
    else:
        print('⚠ Could not find expected HTML structure to inject back nav link')

if __name__ == '__main__':
    ensure_back_nav_link()
