// git 훅(.githooks)과 Claude Code 커밋 가드(scripts/hooks/guard-git.mjs)를 실제 git 저장소에서 돌려 보는 테스트
// 임시 저장소에 이 저장소의 .githooks와 scripts를 복사하고 core.hooksPath를 건다. 새로 클론한 저장소와 같은 모양이다.
// 사용자의 전역 git 설정을 읽지 않도록 GIT_CONFIG_GLOBAL을 임시 파일로 바꾼다.
// 걸리는 값이 이 파일에 그대로 있으면 이 파일도 검사에 걸리므로, 값은 실행할 때 조립한다.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { after, test } from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const NOREPLY = "12345+someone@users.noreply.github.com";
const TERM = ["acme", "private"].join("");
const HOME_PATH = ["", "Users", "someone", "notes"].join("/");
const OTHER_EMAIL = ["someone", "private.org"].join("@");
const AI_TRAILER = `Co-Authored-By: Claude Opus <${["noreply", "anthropic.com"].join("@")}>`;

const temps = [];
after(() => temps.forEach((d) => rmSync(d, { recursive: true, force: true })));

function tempDir() {
  const dir = mkdtempSync(join(tmpdir(), "je-hooks-"));
  temps.push(dir);
  return dir;
}

function gitEnv(globalEmail) {
  const config = join(tempDir(), "gitconfig");
  writeFileSync(config, `[user]\n\temail = ${globalEmail}\n\tname = Tester\n`);
  // 훅 안에서 테스트를 돌려도 바깥 저장소를 건드리지 않게, 물려받은 GIT_ 변수는 뺀다
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith("GIT_")));
  return { ...env, GIT_CONFIG_GLOBAL: config, GIT_CONFIG_NOSYSTEM: "1" };
}

const ENV = gitEnv(OTHER_EMAIL);

function git(cwd, args, { input, env = {} } = {}) {
  const r = spawnSync("git", args, { cwd, input, env: { ...ENV, ...env }, encoding: "utf8" });
  return { status: r.status, out: `${r.stdout}${r.stderr}` };
}

function makeRepo({ terms = true } = {}) {
  const dir = tempDir();
  cpSync(join(ROOT, ".githooks"), join(dir, ".githooks"), { recursive: true });
  cpSync(join(ROOT, "scripts"), join(dir, "scripts"), { recursive: true });
  git(dir, ["init", "-q", "-b", "main"]);
  git(dir, ["config", "user.email", NOREPLY]);
  git(dir, ["config", "user.name", "Tester"]);
  git(dir, ["config", "core.hooksPath", ".githooks"]);
  if (terms) {
    mkdirSync(join(dir, "docs/private"), { recursive: true });
    writeFileSync(join(dir, "docs/private/sensitive-terms.txt"), `# 시험용 금지어\n${TERM}\n`);
  }
  return dir;
}

function write(dir, path, content) {
  mkdirSync(dirname(join(dir, path)), { recursive: true });
  writeFileSync(join(dir, path), content);
}

/** 파일 하나를 쓰고 커밋한다. 메시지는 표준 입력으로 넘긴다(-F -). */
function commitFile(dir, path, content, message = "test: add file", args = [], env = {}) {
  write(dir, path, content);
  git(dir, ["add", "-f", path]);
  return git(dir, ["commit", "-q", ...args, "-F", "-"], { input: message, env });
}

function expectBlocked(result, ...needles) {
  assert.notEqual(result.status, 0, `막혀야 하는데 통과했다:\n${result.out}`);
  for (const needle of needles) assert.ok(result.out.includes(needle), `출력에 「${needle}」가 없다:\n${result.out}`);
}

function expectPassed(result) {
  assert.equal(result.status, 0, `통과해야 하는데 막혔다:\n${result.out}`);
}

// --- pre-commit ---

test("pre-commit: 깨끗한 파일과 noreply 주소면 커밋된다", () => {
  expectPassed(commitFile(makeRepo(), "src/a.txt", "hello\n"));
});

test("pre-commit: 비공개 금지어가 든 파일은 막히고, 걸린 낱말은 출력에 나오지 않는다", () => {
  const result = commitFile(makeRepo(), "src/a.txt", `memo ${TERM.toUpperCase()}\n`);
  expectBlocked(result, "src/a.txt:1", "private-term#1");
  assert.ok(!result.out.toLowerCase().includes(TERM));
});

test("pre-commit: 홈 폴더 절대 경로가 든 파일은 막힌다", () => {
  expectBlocked(commitFile(makeRepo(), "src/a.txt", `see ${HOME_PATH}\n`), "local-path");
});

test("pre-commit: 전역 git 이메일은 금지어 목록에 적지 않아도, 공개 주소 모양이어도 막힌다", () => {
  const globalEmail = "someone@example.com";
  const dir = makeRepo();
  write(dir, "src/a.txt", `contact ${globalEmail}\n`);
  git(dir, ["add", "src/a.txt"]);
  const result = git(dir, ["commit", "-q", "-m", "test: add file"], { env: gitEnv(globalEmail) });
  expectBlocked(result, "personal-email");
});

test("pre-commit: docs/private 아래 파일은 강제로 add해도 막힌다", () => {
  expectBlocked(commitFile(makeRepo(), "docs/private/notes.md", "memo\n"), "private-folder");
});

test("pre-commit: 녹음 확장자 파일은 막힌다", () => {
  expectBlocked(commitFile(makeRepo(), "voice/take1.m4a", "not really audio\n"), "recording");
});

test("pre-commit: 확장자를 바꾼 녹음 파일도 파일 머리로 막힌다", () => {
  const wav = Buffer.concat([Buffer.from("RIFF"), Buffer.alloc(4), Buffer.from("WAVEfmt "), Buffer.alloc(32)]);
  expectBlocked(commitFile(makeRepo(), "fixtures/sample.bin", wav), "audio");
});

test("pre-commit: 작성자나 커미터 주소가 noreply가 아니면 막힌다", () => {
  const dir = makeRepo();
  expectBlocked(commitFile(dir, "a.txt", "a\n", "test: a", ["--author", `Other <${OTHER_EMAIL}>`]), "commit-email");
  expectBlocked(commitFile(dir, "b.txt", "b\n", "test: b", [], { GIT_COMMITTER_EMAIL: OTHER_EMAIL }), "commit-email");
});

test("pre-commit: 금지어 목록이 없으면 검사하지 않은 채 통과시키지 않고 막는다", () => {
  expectBlocked(commitFile(makeRepo({ terms: false }), "src/a.txt", "hello\n"), "sensitive-terms.txt");
});

test("pre-commit: 다른 worktree에서도 원래 폴더의 금지어 목록으로 검사한다", () => {
  const dir = makeRepo();
  git(dir, ["add", ".githooks", "scripts"]);
  expectPassed(git(dir, ["commit", "-q", "-m", "chore: add hooks"]));
  const worktree = join(tempDir(), "wt");
  git(dir, ["worktree", "add", "-q", "-b", "feat/x", worktree]);
  expectBlocked(commitFile(worktree, "src/a.txt", `memo ${TERM}\n`), "private-term#1");
});

// --- commit-msg ---

test("commit-msg: AI 공동 작성자 줄이 든 메시지는 막힌다", () => {
  const message = `test: add file\n\n${AI_TRAILER}\n`;
  expectBlocked(commitFile(makeRepo(), "a.txt", "a\n", message), "AI");
});

test("commit-msg: Conventional Commits 형식이 아니거나, 끝에 마침표가 있거나, 72자를 넘으면 막힌다", () => {
  const dir = makeRepo();
  expectBlocked(commitFile(dir, "a.txt", "a\n", "Update stuff"), "<type>");
  expectBlocked(commitFile(dir, "b.txt", "b\n", "test: add file."), "마침표");
  expectBlocked(commitFile(dir, "c.txt", "c\n", `test: ${"a".repeat(70)}`), "72");
});

test("commit-msg: 메시지에 든 금지어와 홈 폴더 경로도 막는다", () => {
  const message = `docs: add note\n\nfound in ${HOME_PATH}, about ${TERM}\n`;
  expectBlocked(commitFile(makeRepo(), "a.txt", "a\n", message), "local-path", "private-term#1");
});

test("commit-msg: git이 만드는 Revert 메시지는 형식 검사를 건너뛴다", () => {
  expectPassed(commitFile(makeRepo(), "a.txt", "a\n", 'Revert "test: add file"\n'));
});

// --- pre-push ---

function repoWithRemote() {
  const dir = makeRepo();
  const remote = tempDir();
  git(remote, ["init", "-q", "--bare"]);
  git(dir, ["remote", "add", "origin", remote]);
  expectPassed(commitFile(dir, "README.txt", "start\n", "chore: start project"));
  return dir;
}

test("pre-push: 처음 준비 커밋은 main에 바로 올라간다", () => {
  expectPassed(git(repoWithRemote(), ["push", "-q", "origin", "main"]));
});

test("pre-push: main에 기능 커밋을 바로 올리면 막힌다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  commitFile(dir, "src/a.js", "export {};\n", "feat: add a");
  expectBlocked(git(dir, ["push", "-q", "origin", "main"]), "feat: add a");
});

test("pre-push: docs/todo, docs/devlog, docs/guide만 고친 docs 커밋은 main에 올라간다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  commitFile(dir, "docs/todo/20260101_01_todo_x.md", "# TODO\n", "docs: mark todo as done");
  commitFile(dir, "docs/guide/README.md", "# guide\n", "docs(guide): fix typo");
  expectPassed(git(dir, ["push", "-q", "origin", "main"]));
});

test("pre-push: PRD를 고친 커밋은 docs여도 main에 바로 올리지 못한다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  commitFile(dir, "docs/PRD.md", "# PRD\n", "docs: fix typo in prd");
  expectBlocked(git(dir, ["push", "-q", "origin", "main"]), "docs/PRD.md");
});

test("pre-push: 작은 문서 파일만 고쳐도 docs가 아닌 커밋은 main에 바로 올리지 못한다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  commitFile(dir, "docs/todo/20260101_01_todo_x.md", "# TODO\n", "chore: add todo");
  expectBlocked(git(dir, ["push", "-q", "origin", "main"]), "chore: add todo");
});

test("pre-push: main에 merge 커밋을 바로 올리면 막힌다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  git(dir, ["switch", "-q", "-c", "docs/x"]);
  commitFile(dir, "docs/todo/20260101_01_todo_x.md", "# TODO\n", "docs: add todo");
  git(dir, ["switch", "-q", "main"]);
  git(dir, ["merge", "-q", "--no-ff", "-m", "Merge branch 'docs/x'", "docs/x"]);
  expectBlocked(git(dir, ["push", "-q", "origin", "main"]), "merge");
});

test("pre-push: 기능 브랜치는 무엇이든 올라간다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  git(dir, ["switch", "-q", "-c", "feat/x"]);
  commitFile(dir, "src/a.js", "export {};\n", "feat: add a");
  expectPassed(git(dir, ["push", "-q", "-u", "origin", "feat/x"]));
});

test("pre-push: force push와 원격 브랜치 지우기는 막힌다", () => {
  const dir = repoWithRemote();
  git(dir, ["push", "-q", "origin", "main"]);
  git(dir, ["switch", "-q", "-c", "feat/x"]);
  commitFile(dir, "src/a.js", "export {};\n", "feat: add a");
  git(dir, ["push", "-q", "-u", "origin", "feat/x"]);
  git(dir, ["commit", "-q", "--amend", "-m", "feat: add a again"]);
  expectBlocked(git(dir, ["push", "-q", "--force", "origin", "feat/x"]), "force push");
  expectBlocked(git(dir, ["push", "-q", "origin", "--delete", "feat/x"]), "지우");
});

// --- Claude Code 커밋 가드 ---

function guard(dir, command) {
  const input = JSON.stringify({ tool_name: "Bash", tool_input: { command }, cwd: dir });
  const r = spawnSync("node", [join(dir, "scripts/hooks/guard-git.mjs")], {
    cwd: dir,
    input,
    env: { ...ENV, CLAUDE_PROJECT_DIR: dir },
    encoding: "utf8",
  });
  return { status: r.status, out: `${r.stdout}${r.stderr}` };
}

test("가드: 훅을 건너뛰는 커밋과 push는 종료 코드 2로 막는다", () => {
  const dir = makeRepo();
  assert.equal(guard(dir, "git commit --no-verify -m 'test: x'").status, 2);
  assert.equal(guard(dir, "git push --no-verify origin main").status, 2);
});

test("가드: git 전역 옵션으로 훅 폴더를 바꾸는 명령은 막는다", () => {
  assert.equal(guard(makeRepo(), "git -c core.hooksPath=/dev/null commit -m 'test: x'").status, 2);
});

test("가드: core.hooksPath가 걸려 있지 않으면 커밋과 push를 막고 거는 방법을 알려 준다", () => {
  const dir = makeRepo();
  git(dir, ["config", "--unset", "core.hooksPath"]);
  const result = guard(dir, "git commit -m 'test: x'");
  assert.equal(result.status, 2);
  assert.ok(result.out.includes("git config core.hooksPath .githooks"), result.out);
  assert.equal(guard(dir, "git push origin feat/x").status, 2);
});

test("가드: AI 서명이 든 커밋 명령은 막는다", () => {
  const command = ["git commit -q -F - <<'EOF'", "fix: x", "", AI_TRAILER, "EOF"];
  assert.equal(guard(makeRepo(), command.join("\n")).status, 2);
});

test("가드: 스테이징한 내용에 금지어가 있으면 커밋 명령을 막는다", () => {
  const dir = makeRepo();
  write(dir, "src/a.txt", `memo ${TERM}\n`);
  git(dir, ["add", "src/a.txt"]);
  const result = guard(dir, "git commit -m 'test: x'");
  assert.equal(result.status, 2);
  assert.ok(result.out.includes("private-term#1"), result.out);
});

test("가드: 평범한 커밋과 git이 아닌 명령은 통과시킨다", () => {
  const dir = makeRepo();
  write(dir, "src/a.txt", "hello\n");
  git(dir, ["add", "src/a.txt"]);
  assert.equal(guard(dir, "git commit -q -m 'test: x' && git log -1").status, 0);
  assert.equal(guard(dir, "sed -n 1,5p scripts/lib/commit-guard.mjs").status, 0);
});
