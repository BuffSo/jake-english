// 검사 스크립트가 함께 쓰는 git 도우미 (CLAUDE.md 「커밋 전 자동 검사」)

import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { PRIVATE_TERMS_PATH, readTermsFile } from "./sensitive-rules.mjs";

/** git을 실행해 출력을 돌려준다. buffer가 참이면 Buffer로 돌려준다(녹음 같은 바이너리를 읽을 때). */
export function git(args, { buffer = false } = {}) {
  return execFileSync("git", args, {
    encoding: buffer ? undefined : "utf8",
    maxBuffer: 256 * 1024 * 1024,
    stdio: ["ignore", "pipe", "pipe"],
  });
}

/** 원래 폴더(git worktree list의 첫 줄). worktree는 git에 든 파일만 펼쳐 docs/private/가 없거나 옛 복사본이다. */
export function mainWorktreeRoot() {
  return dirname(git(["rev-parse", "--path-format=absolute", "--git-common-dir"]).trim());
}

/**
 * 원래 폴더의 금지어 목록과 전역 git 이메일을 읽는다.
 * 목록이 없으면 오류를 낸다. 없는 채로 통과시키면 금지어 검사를 한 번도 하지 않은 커밋이 생긴다.
 */
export function loadPrivateTerms() {
  const terms = readTermsFile(join(mainWorktreeRoot(), PRIVATE_TERMS_PATH));
  if (terms === null) {
    throw new Error(
      `금지어 목록(${PRIVATE_TERMS_PATH})이 원래 폴더(git worktree list의 첫 줄)에 없어 검사할 수 없습니다. ` +
        "그 파일을 만든 뒤 다시 커밋하세요. 목록은 민감 정보라 git에 넣지 않습니다.",
    );
  }
  let email = "";
  try {
    email = git(["config", "--global", "user.email"]).trim();
  } catch {
    // 전역 이메일이 없으면 막을 것도 없다
  }
  return { terms, personalEmails: email ? [email] : [] };
}
