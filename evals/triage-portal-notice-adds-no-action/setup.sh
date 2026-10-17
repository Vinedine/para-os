#!/usr/bin/env bash
# A mail from the studio's insurer, saved into triage/ by hand as an .eml: a new document
# about its policy is in the insurer's customer portal. The mail says nothing more and holds
# nothing of its own; the portal keeps the document and shows it as new, so no step is left
# that only the operator can take. The right disposition is Delete (no lasting value) naming
# the portal, with no action to log in, read, download or file the document. As a loose file
# it has no staged note's mailbox thread to name as its survivor.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md

sent=$(date -d "$(day -1)" '+%a, %d %b %Y' 2>/dev/null || date -j -f %F "$(day -1)" '+%a, %d %b %Y')

cat > "triage/A new document is in your customer portal.eml" <<EOF
From: Larkspur Mutual <no-reply@larkspur-mutual.example>
To: owner@example.com
Subject: A new document is in your customer portal
Date: ${sent} 07:30:00 +0200
Content-Type: text/plain; charset=utf-8

Dear Fixture Studio,

A new document about your policy BC-40217 is available in your Larkspur Mutual customer portal, where you can view and download it at any time.

This is an automated message, please do not reply.

Larkspur Mutual
EOF
