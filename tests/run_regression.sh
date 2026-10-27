#!/bin/bash
# 회귀 시험 12종을(공개판에서는 비교 출처 문항을 다루는 test_variants·test_replace13 제외) 웹·standalone(http)·standalone(file://) 세 환경에서 돌린다.
# 사용법(저장소 루트 어디서든):  bash tests/run_regression.sh [web] [sa_http] [sa_file]
#   인자를 생략하면 세 환경 모두. 결과 요약: tests/_logs/summary_<환경>.txt
# 준비물: python3, playwright(python) + chromium. 포트 9881을 쓴다.
# 공개판에는 문제 데이터(jcb_restored/raw, jcb_cbt/site/data.json·img)가 없으므로, 비공개 저장소의 데이터를 같은 위치에 두어야 돈다.
# 주의: test_enter_merge / test_output_similar / test_blank_expl_typo 는 수정 전 백업
#       (jcb_restored/backup_before_*)과 비교하므로, 백업 압축(3of3)을 저장소 안에 풀어 두어야 통과한다.
set -u
T="$(cd "$(dirname "$0")" && pwd)"          # tests 폴더(절대 경로로 바꿔 둠)
REPO="$(dirname "$T")"
cd "$T"
python3 prepare_srv.py || exit 1
python3 mockdb_server.py 9881 "$T/_srv" > "$T/_mockdb.log" 2>&1 &
SRVPID=$!
trap 'kill $SRVPID 2>/dev/null' EXIT
sleep 1
mkdir -p "$T/_logs"
TESTS="test_memo_editor test_memomark test_sync_memo test_enter_merge test_output_similar test_blank_expl_typo test_dups test_save_feature test_recfile test_autofocus test_copy_button test_jcb_flow_regress"
ENVS="${*:-web sa_http sa_file}"
for TAG in $ENVS; do
  case $TAG in
    web)     URL="http://localhost:9881/index.html" ;;
    sa_http) URL="http://localhost:9881/standalone.html" ;;
    sa_file) URL="file://$REPO/jcb_cbt/standalone/jcb_cbt.html" ;;
    *) echo "unknown env $TAG"; continue ;;
  esac
  SUM="$T/_logs/summary_$TAG.txt"; : > "$SUM"
  for t in $TESTS; do
    if [ "$TAG" = "sa_file" ] && [ "$t" = "test_sync_memo" ]; then continue; fi   # 동기화는 http에서만
    timeout 1500 python3 "$t.py" "$URL" "$TAG" > "$T/_logs/${t}_$TAG.log" 2>&1
    echo "$t $TAG exit=$? $(grep -h 'PASS [0-9]* / FAIL' "$T/_logs/${t}_$TAG.log" | tail -1)" >> "$SUM"
  done
  echo DONE >> "$SUM"
  cat "$SUM"
done
