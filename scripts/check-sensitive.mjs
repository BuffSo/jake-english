#!/usr/bin/env node
// 커밋 전 공개 금지 검사 (AGENTS.md 「커밋 전 자동 검사」)
//   node scripts/check-sensitive.mjs --staged   스테이징한 내용과 커밋 작성자 주소를 검사한다 (pre-commit 훅, 커밋 가드)
//   node scripts/check-sensitive.mjs --all      추적 중이거나 새로 더할 파일 전체를 검사한다 (공개 전 점검)
// 규칙은 scripts/lib/sensitive-rules.mjs에 있다. 커밋 메시지 검사도 같은 규칙을 쓴다.

import { existsSync, readFileSync } from "node:fs";
import { git, loadPrivateTerms } from "./lib/git-context.mjs";
import { checkPath, looksLikeAudio, mask, scanText } from "./lib/sensitive-rules.mjs";

const staged = process.argv.includes("--staged");

const HINTS = {
  "commit-email":
    "커밋 주소는 저장소 설정의 GitHub noreply 주소를 씁니다(AGENTS.md 「커밋 이메일」). git config user.email로 고치고, --author나 GIT_*_EMAIL로 바꾸지 않습니다.",
  "private-folder": "docs/private/는 git에 넣지 않습니다. git rm --cached로 스테이징에서 빼세요.",
  "env-file": "환경 변수 파일은 git에 넣지 않습니다. 넣을 것은 .env.example에 값 없이 씁니다.",
  recording: "녹음과 음성 파일은 사용자 목소리라 git에 넣지 않습니다.",
  audio: "파일 머리가 소리 파일입니다. 녹음과 음성 파일은 확장자를 바꿔도 git에 넣지 않습니다.",
};

function run() {
  process.chdir(git(["rev-parse", "--show-toplevel"]).trim());
  const { terms, personalEmails } = loadPrivateTerms();
  const findings = [];

  if (staged) {
    for (const [who, label] of [
      ["GIT_AUTHOR_IDENT", "작성자"],
      ["GIT_COMMITTER_IDENT", "커미터"],
    ]) {
      const email = git(["var", who]).match(/<([^>]*)>/)?.[1] ?? "";
      if (!/@users\.noreply\.github\.com$/i.test(email)) findings.push({ at: label, id: "commit-email", shown: mask(email) });
    }
  }

  const listed = staged
    ? git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    : git(["ls-files", "-z", "--cached", "--others", "--exclude-standard"]);
  const files = listed.split("\0").filter(Boolean);

  for (const file of files) {
    for (const id of checkPath(file)) findings.push({ at: file, id, shown: "" });

    const content = staged ? git(["show", `:${file}`], { buffer: true }) : existsSync(file) ? readFileSync(file) : null;
    if (content == null) continue;
    if (looksLikeAudio(content)) findings.push({ at: file, id: "audio", shown: "" });
    if (content.includes(0)) continue;

    for (const { line, id, shown } of scanText(content.toString("utf8"), terms, personalEmails)) {
      findings.push({ at: `${file}:${line}`, id, shown });
    }
  }

  const scope = staged ? "스테이징한 파일" : "전체 파일";
  if (findings.length === 0) {
    console.log(`공개 금지 검사 통과: ${scope} ${files.length}개, 금지어 ${terms.length}개`);
    return 0;
  }

  console.error(`공개 금지 검사 실패: ${scope} ${files.length}개에서 ${findings.length}건`);
  for (const f of findings) console.error(`  ${f.at}  [${f.id}]  ${f.shown}`.trimEnd());
  for (const id of new Set(findings.map((f) => f.id))) if (HINTS[id]) console.error(`- ${HINTS[id]}`);
  console.error("값을 지운 뒤 다시 하세요. 규칙을 끄거나 예외를 늘리거나 --no-verify로 넘기지 않습니다 (AGENTS.md 「커밋 전 자동 검사」).");
  return 1;
}

try {
  process.exit(run());
} catch (error) {
  // 검사를 끝내지 못했으면 통과시키지 않는다
  console.error(`공개 금지 검사를 끝내지 못했습니다: ${error.message}`);
  process.exit(1);
}
