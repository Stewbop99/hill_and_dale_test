#!/usr/bin/env node
/**
 * Build script for head-to-head/index.html
 * Ensures the back navigation link persists across regenerations
 */

const fs = require('fs');
const path = require('path');

const h2hPath = path.join(__dirname, 'head-to-head', 'index.html');

/**
 * Injects the back navigation link into the head-to-head HTML
 * if it's missing, ensuring it persists across HTML regenerations.
 */
function ensureBackNavLink() {
  const backNavHTML = `<div style="max-width: 1600px; margin: 0 auto; padding: 2rem 2rem 0;">
  <a href="../index.html" style="font-size: 13px; color: #1D9E75; text-decoration: none; display: inline-block; margin-bottom: 8px;">&larr; All runners</a>
</div>`;

  let html = fs.readFileSync(h2hPath, 'utf8');

  // Check if back nav already exists
  if (html.includes('&larr; All runners')) {
    console.log('✓ Back navigation link already present');
    return;
  }

  // Insert after <body> tag
  const bodyRegex = /<body>\n<div class="page">/;
  if (bodyRegex.test(html)) {
    html = html.replace(bodyRegex, `<body>\n${backNavHTML}\n<div class="page">`);
    fs.writeFileSync(h2hPath, html, 'utf8');
    console.log('✓ Added back navigation link to head-to-head');
  } else {
    console.warn('⚠ Could not find expected HTML structure to inject back nav link');
  }
}

// Run if called directly
if (require.main === module) {
  ensureBackNavLink();
}

module.exports = { ensureBackNavLink };
