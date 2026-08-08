#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0

if find . -type f \
  \( -name '.env' -o -name 'Cloud.xcconfig' -o -name '*.p8' -o -name '*.p12' \
     -o -name '*.mobileprovision' -o -name 'GoogleService-Info.plist' \) \
  -not -path './.git/*' | grep -q .; then
  echo "Blocked: local credentials or signing files are present."
  fail=1
fi

if rg -n --hidden \
  --glob '!.git/**' \
  --glob '!scripts/security_scan.sh' \
  --glob '!.env.example' \
  'sk-(proj-)?[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN ([A-Z ]+ )?PRIVATE KEY-----'; then
  echo "Blocked: possible credential detected."
  fail=1
fi

if rg -n -i --hidden \
  --glob '!.git/**' \
  --glob '!scripts/security_scan.sh' \
  'Decrypted-Userinfo|db\.properties|ai\.properties|Cowork Runway|xhsshare|appuid=|share_id=|xiaohongshu\.(net|internal)|xhscdn|edith|red\.ws'; then
  echo "Blocked: possible internal Xiaohongshu/Cowork dependency detected."
  fail=1
fi

if rg -n --hidden \
  --glob '!.git/**' \
  --glob '!scripts/security_scan.sh' \
  '5DQ8C5GP43|com\.yudideng|xiaomeishuo-api-[A-Za-z0-9-]+\.a\.run\.app'; then
  echo "Blocked: owner or production deployment identifier detected."
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "Security scan passed."
