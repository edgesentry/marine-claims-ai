#!/usr/bin/env bash
# Regenerate image-only synthetic repair PDF for Issue #94 Web OCR demos.
# Requires ImageMagick (`magick` or `convert`) + a Japanese font.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="$ROOT/tests/fixtures/ocr_scan_synthetic"
mkdir -p "$OUTDIR"

FONT="${OCR_JA_FONT:-/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc}"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Hiragino Sans GB.ttc"
fi

MAGICK=(magick)
if ! command -v magick >/dev/null 2>&1; then
  MAGICK=(convert)
fi

PNG="$OUTDIR/repair_scan.png"
PDF="$OUTDIR/repair_scan_image_only.pdf"

"${MAGICK[@]}" -size 1400x1800 xc:white \
  -font "$FONT" -pointsize 44 -fill black \
  -annotate +60+100 '修繕仕様書（合成スキャン）' \
  -pointsize 36 \
  -annotate +60+240 '甲板部 外板補修工事（球状船首） 1200000円' \
  -annotate +60+340 '甲板部 塗装工事 850000円' \
  -annotate +60+440 '機関部 ピストン抜出し整備 3500000円' \
  -annotate +60+540 '共通 入渠料 日額 860000円' \
  -annotate +60+640 '共通 ドック総額 4300000円' \
  "$PNG"

"${MAGICK[@]}" "$PNG" "$PDF"
echo "Wrote $PDF (pdftotext chars: $(pdftotext "$PDF" - 2>/dev/null | wc -c | tr -d ' '))"
