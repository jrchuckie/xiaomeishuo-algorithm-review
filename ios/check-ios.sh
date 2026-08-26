#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

xcodegen generate --spec project.yml >/dev/null

sdk_path="$(xcrun --sdk iphoneos --show-sdk-path)"
swift_files=()
while IFS= read -r -d '' swift_file; do
  swift_files+=("$swift_file")
done < <(find Xiaomeishuo -name '*.swift' -print0)

xcrun swiftc \
  -typecheck \
  -parse-as-library \
  -module-name Xiaomeishuo \
  -sdk "$sdk_path" \
  -target arm64-apple-ios17.0 \
  -enable-experimental-feature DebugDescriptionMacro \
  "${swift_files[@]}"

echo "iOS 源码类型检查通过。"
