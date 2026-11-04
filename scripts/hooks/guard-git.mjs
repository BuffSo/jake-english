#!/usr/bin/env node
// Claude Code PreToolUse 훅 (CLAUDE.md 「커밋 전 자동 검사」)
// 에이전트가 git commit이나 git push를 실행하기 직전에 본다. git 훅을 건너뛰는 길(--no-verify, -n, 훅 폴더 바꾸기,
// 훅 폴더가 걸려 있지 않은 저장소)을 막고, 커밋이면 pre-commit 훅과 같은 공개 금지 검사를 미리 돌린다. AI 서명이 든 커밋 명령도 막는다.
// 종료 코드 2를 돌려주면 Claude Code가 명령을 실행하지 않고 stderr를 에이전트에게 전달한다.
// 명령 해석은 scripts/lib/commit-guard.mjs에 있다.

import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { findGitCommands, overridesHooksPath, skipsHooks, skipsPushHooks } from "../lib/commit-guard.mjs";
import { AI_SIGNATURE } from "../lib/commit-message.mjs";

let raw = "";
for await (const chunk of process.stdin) raw += chunk;

const input = JSON.parse(raw || "{}");
const command = input.tool_input?.command ?? "";
const cwd = input.cwd || process.env.CLAUDE_PROJECT_DIR || process.cwd();

function block(message) {
  console.error(message);
  process.exit(2);
}

const found = findGitCommands(command);
const commits = found.filter((c) => c.sub === "commit");
const pushes = found.filter((c) => c.sub === "push");

// 서명은 히어독 메시지 본문에도 있을 수 있어 명령 전체에서 찾는다.
// 명령을 해석하지 못한 커밋도 놓치지 않게, git과 commit이 한 구간에 보이면 찾는다.
const looksLikeCommit = commits.length > 0 || /\bgit\b[^;&|\n]*\bcommit\b/.test(command);
if (looksLikeCommit && AI_SIGNATURE.test(command)) {
  block("커밋 메시지에 AI 공동 작성자 줄이나 생성 도구 서명을 넣지 않습니다 (CLAUDE.md 「커밋 메시지」).");
}

if (commits.length === 0 && pushes.length === 0) process.exit(0);

if ([...commits, ...pushes].some((c) => overridesHooksPath(c.globals))) {
  block("git 전역 옵션으로 core.hooksPath를 바꾸면 git 훅이 모두 빠집니다. 허용하지 않습니다.");
}
if (commits.some((c) => skipsHooks(c.args))) {
  block("훅을 건너뛰는 커밋(--no-verify, -n)은 허용하지 않습니다. 훅에 걸린 원인을 고치세요.");
}
if (pushes.some((c) => skipsPushHooks(c.args))) {
  block("훅을 건너뛰는 push(--no-verify)는 허용하지 않습니다. pre-push 훅에 걸린 원인을 고치세요.");
}

let hooksPath = "";
try {
  hooksPath = execFileSync("git", ["config", "core.hooksPath"], { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
} catch {
  // 설정이 없으면 빈 값으로 둔다
}
if (hooksPath !== ".githooks") {
  block(
    `이 저장소에 git 훅이 걸려 있지 않습니다(core.hooksPath: ${hooksPath || "없음"}). ` +
      "저장소 폴더에서 `git config core.hooksPath .githooks`를 실행한 뒤 다시 하세요.",
  );
}

if (commits.length > 0) {
  const checker = fileURLToPath(new URL("../check-sensitive.mjs", import.meta.url));
  const result = spawnSync("node", [checker, "--staged"], { cwd, encoding: "utf8" });
  if (result.status !== 0) block(`${result.stdout}${result.stderr}`.trim());
}

process.exit(0);
