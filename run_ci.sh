#!/usr/bin/env bash
# ziping-app CI 本地运行器：一键跑「确定性」测试套件（与 GitHub Actions 同源）。
# 排除需 GPU/网络/外部技能的重度测试：test_ocr_parallel / test_bing_regression / test_skill_crosscheck。
set -uo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python}"
PASS=0
FAIL=0
FAILED_LIST=""

# 确定性、可离线、CI 安全的测试
TESTS=(
  test_regression
  test_full_regression
  test_late_zishi_regression
  test_chengu_online_diff
  test_chengu_lunar
  test_external_crosscheck
  test_ziwei
)

for t in "${TESTS[@]}"; do
  echo "================ $t ================"
  if "$PY" "tests/$t.py"; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
    FAILED_LIST="$FAILED_LIST $t"
  fi
done

echo ""
echo "================ CI 汇总 ================"
echo "PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -ne 0 ]; then
  echo "失败用例:$FAILED_LIST"
  exit 1
fi
echo "全部通过 ✅"
