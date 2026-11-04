// 커밋 가드 훅의 판정(scripts/lib/commit-guard.mjs) 테스트
// 판정과 대부분의 테스트는 jake-homepage(ADR-0006)에서 가져왔다. 거기서 막지 않아야 할 명령에는 실제로 잘못 막혔던 명령을,
// 막아야 할 명령에는 PR 리뷰가 찾은 우회 경로를 넣었다. push와 core.hooksPath 테스트는 이 저장소에서 더했다.

import assert from "node:assert/strict";
import { test } from "node:test";
import { findCommits, findGitCommands, overridesHooksPath, skipsHooks, skipsPushHooks } from "./commit-guard.mjs";

const blocks = (command) => findCommits(command).some(skipsHooks);

test("커밋이 아닌 명령의 -n과 파일 이름의 git-commit은 커밋으로 보지 않는다", () => {
  assert.deepEqual(findCommits("sed -n 1,40p scripts/hooks/guard-git-commit.mjs"), []);
  assert.deepEqual(findCommits("cat scripts/hooks/guard-git-commit.mjs; sed -n 1p x"), []);
  assert.deepEqual(findCommits("git log -n 5 --grep commit"), []);
  assert.deepEqual(findCommits('echo "git commit -n"'), []);
});

test("커밋과 같은 명령에 있는 다른 명령의 -n은 막지 않는다", () => {
  assert.deepEqual(findCommits("git add . && git commit -q -m x"), [["-q", "-m", "x"]]);
  assert.equal(blocks("git commit -m x && grep -n foo f"), false);
  assert.equal(blocks("git commit -q -m x 2>&1 | tail -n 3"), false);
});

test("메시지 값에 든 n과 -n은 옵션으로 보지 않는다", () => {
  assert.equal(blocks('git commit -m "-n 옵션 설명"'), false);
  assert.equal(blocks("git commit -mnew"), false);
  assert.equal(blocks("git commit -uno -m x"), false);
  assert.equal(blocks("git commit --message=-n"), false);
});

test("히어독 메시지 본문은 명령으로 보지 않는다", () => {
  const command = ["git commit -q -F - <<'EOF'", "fix: x", "", "git commit -n is never used", "EOF", "git log -1"].join("\n");
  assert.deepEqual(findCommits(command), [["-q", "-F", "-"]]);
  assert.equal(blocks(command), false);
});

test("훅을 건너뛰는 커밋은 막는다", () => {
  assert.equal(blocks("git commit -n -m x"), true);
  assert.equal(blocks("git commit --no-verify"), true);
  assert.equal(blocks("git commit --no-veri -m x"), true);
  assert.equal(blocks("git -C /tmp/r commit -nm x"), true);
  assert.equal(blocks("git add . && git commit -an -m x"), true);
});

test("감싸는 명령과 bash -c 안의 커밋도 찾는다", () => {
  assert.equal(blocks("rtk git commit -n"), true);
  assert.equal(blocks("GIT_EDITOR=true git commit -n"), true);
  assert.equal(blocks('bash -c "git commit --no-verify"'), true);
  assert.equal(blocks("zsh -lc 'cd x && git commit -n'"), true);
});

test("주석 속 따옴표와 구분자는 명령으로 보지 않는다", () => {
  assert.equal(blocks("# don't skip hooks\ngit commit -n -m x"), true);
  assert.equal(blocks("git add -A # it's fine\ngit commit --no-verify -m x"), true);
  assert.equal(blocks("# 예: a && git commit -n\nnpm test"), false);
  // $'…' 안의 \'는 따옴표를 닫지 않는다
  assert.equal(blocks("run $'# it\\'s fine\\ngit commit -n -m x'"), false);
});

test("셸 예약어와 감싸는 명령 뒤의 커밋도 찾는다", () => {
  assert.equal(blocks("if ! git diff --cached --quiet; then git commit -n -m x; fi"), true);
  assert.equal(blocks("{ git commit --no-verify; }"), true);
  assert.equal(blocks("! git commit -n"), true);
  assert.equal(blocks("for m in a b; do git commit -n -m $m; done"), true);
  assert.equal(blocks("timeout 60 git commit --no-verify -m x"), true);
  assert.equal(blocks("nice -n 10 git commit -n"), true);
  assert.equal(blocks("sudo git commit -n"), true);
  assert.equal(blocks("/usr/bin/env git commit -n"), true);
  assert.equal(blocks("env -i git commit -n"), true);
});

test("리다이렉트 모양이 달라도 커밋 인자를 잃지 않는다", () => {
  assert.equal(blocks("git commit &>/dev/null -n"), true);
  assert.equal(blocks("2>/dev/null git commit -n"), true);
  assert.equal(blocks("git commit -q -m x 2>&1 | tail -n 3"), false);
});

test("명령 치환, 히어독으로 넘긴 셸, eval 안의 커밋도 찾는다", () => {
  assert.equal(blocks("git commit -m $(cat msg.txt) -n"), true);
  assert.equal(blocks("echo `git commit -n -m x`"), true);
  assert.equal(blocks("cat <(git commit -n)"), true);
  assert.equal(blocks("bash <<EOF\ngit commit -n -m x\nEOF"), true);
  assert.equal(blocks('bash -norc -c "git commit -n"'), true);
  assert.equal(blocks('eval "git commit -n"'), true);
});

test("명령 치환 안의 따옴표와 히어독은 바깥 메시지를 깨뜨리지 않는다", () => {
  assert.equal(blocks(`git commit -m "$(printf '%s\\n' "a" "-n")"`), false);
  assert.equal(blocks(["git commit -q -m \"$(cat <<'EOF'", "fix -n", "EOF", ')"'].join("\n")), false);
});

const pushes = (command) => findGitCommands(command).filter((c) => c.sub === "push");

test("push도 찾고, 훅을 건너뛰는 push는 막는다", () => {
  assert.deepEqual(pushes("git push -u origin feat/x").map((c) => c.args), [["-u", "origin", "feat/x"]]);
  assert.equal(pushes("rtk git push --no-verify origin main").some((c) => skipsPushHooks(c.args)), true);
  assert.equal(pushes("git push --no-verif").some((c) => skipsPushHooks(c.args)), true);
});

test("push의 -n은 시험 실행(dry-run)이라 막지 않는다", () => {
  assert.equal(pushes("git push -n origin main").some((c) => skipsPushHooks(c.args)), false);
  assert.equal(pushes("git push origin --no-verify-branch-name").some((c) => skipsPushHooks(c.args)), false);
});

test("git 전역 옵션으로 훅 폴더를 바꾸는 커밋과 push를 찾는다", () => {
  const overrides = (command) => findGitCommands(command).some((c) => overridesHooksPath(c.globals));
  assert.equal(overrides("git -c core.hooksPath=/dev/null commit -m x"), true);
  assert.equal(overrides("git -c core.hookspath= push origin main"), true);
  assert.equal(overrides("git --config-env=core.hooksPath=EMPTY commit -m x"), true);
  assert.equal(overrides("git -c user.name=x commit -m x"), false);
  assert.equal(overrides("git -C /tmp/r commit -m x"), false);
});
