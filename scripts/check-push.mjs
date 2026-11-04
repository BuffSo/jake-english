#!/usr/bin/env node
// push 전 검사 (pre-push 훅, CLAUDE.md 「작은 문서 커밋은 main에 바로 올린다」)
//   git이 표준 입력으로 「<로컬 ref> <로컬 sha> <원격 ref> <원격 sha>」 줄을 넘긴다.
// - main으로 가는 push에는 작은 문서 커밋만 둔다. superpowers는 스펙과 계획을 지금 브랜치(대개 로컬 main)에 먼저 커밋하므로,
//   작은 문서 커밋을 올리다가 PR을 기다리는 스펙과 계획이 같이 올라갈 수 있다.
// - 원격에 main이 아직 없으면(처음 준비 커밋) 통과시킨다.
// - force push와 원격 브랜치 지우기는 어느 브랜치든 막는다.

import { execFileSync } from "node:child_process";

const ZERO = /^0+$/;
// 작은 문서 커밋이 고칠 수 있는 파일. PRD, ADR, 스펙, 계획, CLAUDE.md, REVIEW.md는 PR로 올린다.
const SMALL_DOC_FILE = /^docs\/(todo|devlog|guide)\/.+\.md$/;
const DOCS_SUBJECT = /^docs(\([a-z0-9-]+\))?!?: /;

const git = (args) => execFileSync("git", args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
const succeeds = (args) => {
  try {
    git(args);
    return true;
  } catch {
    return false;
  }
};

function checkUpdate(line) {
  const [, localSha, remoteRef, remoteSha] = line.split(" ");
  const branch = remoteRef.replace(/^refs\/heads\//, "");

  if (ZERO.test(localSha)) return [`${branch}: 원격 브랜치를 지우지 않습니다. 지울 일이 있으면 사용자에게 맡깁니다.`];
  if (!ZERO.test(remoteSha)) {
    if (!succeeds(["cat-file", "-e", `${remoteSha}^{commit}`])) {
      return [`${branch}: 원격에 이 저장소에 없는 커밋이 있습니다. git fetch로 받은 뒤 다시 하세요.`];
    }
    if (!succeeds(["merge-base", "--is-ancestor", remoteSha, localSha])) {
      return [`${branch}: force push는 하지 않습니다. 원격 브랜치를 덮어쓰지 말고 새 커밋을 더하세요.`];
    }
  }
  if (remoteRef !== "refs/heads/main" || ZERO.test(remoteSha)) return [];

  const problems = [];
  for (const sha of git(["rev-list", "--reverse", `${remoteSha}..${localSha}`]).split("\n").filter(Boolean)) {
    const parents = git(["rev-list", "--parents", "-n", "1", sha]).trim().split(" ").slice(1);
    const subject = git(["log", "-1", "--format=%s", sha]).trim();
    const label = `main ${sha.slice(0, 7)} 「${subject}」`;
    if (parents.length > 1) {
      problems.push(`${label}: merge 커밋은 main에 바로 올리지 않습니다. 작은 문서 커밋이면 git pull --rebase로 줄을 세우세요.`);
      continue;
    }
    const files = git(["diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha]).split("\n").filter(Boolean);
    const others = files.filter((f) => !SMALL_DOC_FILE.test(f));
    if (others.length > 0) problems.push(`${label}: 작은 문서 파일이 아닌 것이 있습니다 (${others.join(", ")}).`);
    else if (!DOCS_SUBJECT.test(subject)) problems.push(`${label}: 작은 문서 커밋은 docs 커밋이어야 합니다.`);
  }
  return problems;
}

let input = "";
for await (const chunk of process.stdin) input += chunk;

try {
  const problems = input.split("\n").filter(Boolean).flatMap(checkUpdate);
  if (problems.length > 0) {
    console.error("push를 막았습니다.");
    for (const p of problems) console.error(`  - ${p}`);
    console.error(
      "main에는 작은 문서 커밋(docs 커밋이고 docs/todo, docs/devlog, docs/guide의 .md만 고친 것)만 바로 올립니다. " +
        "나머지는 기능 브랜치를 push하고 PR로 합칩니다. --no-verify로 넘기지 않습니다 (CLAUDE.md).",
    );
    process.exit(1);
  }
} catch (error) {
  console.error(`push 전 검사를 끝내지 못했습니다: ${error.message}`);
  process.exit(1);
}
