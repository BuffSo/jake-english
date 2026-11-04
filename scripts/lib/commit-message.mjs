// 커밋 메시지 규칙 (CLAUDE.md 「커밋 메시지」)
// commit-msg 훅(scripts/check-commit-msg.mjs)과 커밋 가드(scripts/hooks/guard-git.mjs)가 함께 쓴다.

import { scanText } from "./sensitive-rules.mjs";

// AI 공동 작성자 줄과 생성 도구 서명. 가드는 커밋 명령 전체에서 찾으므로 줄 맨 앞에 묶지 않는다.
export const AI_SIGNATURE =
  /co-authored-by:[^\n]*\b(claude|anthropic|openai|chatgpt|codex|gemini|copilot|cursor)\b|generated (with|by) \[?(claude|chatgpt|codex|gemini|copilot|cursor)\b/i;

const SUBJECT = /^(feat|fix|docs|refactor|test|chore|build|ci|perf|style)(\([a-z0-9-]+\))?!?: [a-z0-9]/;
// git이 만드는 메시지는 형식 검사를 건너뛴다
const GENERATED = /^(Merge |Revert |fixup! |squash! |amend! )/;

/** 커밋 메시지를 검사해 문제 목록(글)을 돌려준다. 비어 있으면 통과다. */
export function checkCommitMessage(raw, { terms = [], personalEmails = [] } = {}) {
  // git commit -v가 붙이는 diff는 커밋되지 않는다. 가위 줄 아래는 보지 않는다.
  const scissors = raw.search(/^# -+ >8 -+$/m);
  const message = scissors >= 0 ? raw.slice(0, scissors) : raw;
  const problems = [];

  if (AI_SIGNATURE.test(message)) problems.push("AI 공동 작성자 줄이나 생성 도구 서명이 있습니다. 지우세요.");

  const subject = message.split("\n").find((line) => line.trim() && !line.startsWith("#")) ?? "";
  if (!GENERATED.test(subject)) {
    if (!SUBJECT.test(subject)) {
      problems.push("첫 줄은 <type>(<scope>): <summary> 형식이고, summary는 영어 소문자나 숫자로 시작합니다.");
    }
    if (subject.endsWith(".")) problems.push("첫 줄 끝에 마침표를 찍지 않습니다.");
    const length = [...subject].length;
    if (length > 72) problems.push(`첫 줄은 72자 이내로 씁니다. 지금 ${length}자입니다.`);
  }

  // 커밋 메시지도 공개된다. 파일과 같은 공개 금지 검사를 한다.
  for (const { line, id, shown } of scanText(message, terms, personalEmails)) {
    problems.push(`${line}번째 줄 [${id}] ${shown} 공개하면 안 되는 값입니다.`);
  }

  return problems;
}
