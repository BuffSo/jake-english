#!/usr/bin/env node
// 커밋 메시지 검사 (commit-msg 훅, AGENTS.md 「커밋 메시지」와 「커밋 전 자동 검사」)
//   node scripts/check-commit-msg.mjs <메시지 파일>
// 규칙은 scripts/lib/commit-message.mjs에 있다.

import { readFileSync } from "node:fs";
import { checkCommitMessage } from "./lib/commit-message.mjs";
import { loadPrivateTerms } from "./lib/git-context.mjs";

try {
  const problems = checkCommitMessage(readFileSync(process.argv[2], "utf8"), loadPrivateTerms());
  if (problems.length > 0) {
    console.error("커밋 메시지 검사 실패");
    for (const p of problems) console.error(`  - ${p}`);
    console.error("메시지를 고쳐 다시 커밋하세요. --no-verify로 넘기지 않습니다 (AGENTS.md 「커밋 메시지」).");
    process.exit(1);
  }
} catch (error) {
  console.error(`커밋 메시지 검사를 끝내지 못했습니다: ${error.message}`);
  process.exit(1);
}
