// 공개 금지 검사 규칙(scripts/lib/sensitive-rules.mjs) 테스트
// 검사에 걸리는 값이 이 파일에 그대로 있으면 이 파일도 커밋 전 검사에 걸리므로, 값은 실행할 때 조립한다.

import assert from "node:assert/strict";
import { test } from "node:test";
import { checkPath, looksLikeAudio, mask, scanText } from "./sensitive-rules.mjs";

const ids = (findings) => findings.map((f) => f.id);

const HOME_PATH = ["", "Users", "someone", "Developer", "x"].join("/");
const LAN_IPS = [
  ["192", "168", "0", "12"],
  ["10", "0", "0", "5"],
  ["172", "20", "1", "1"],
].map((parts) => parts.join("."));
const PRIVATE_EMAIL = ["someone", "private.org"].join("@");

test("홈 폴더 절대 경로는 걸리고, 찾은 값은 가려서 돌려준다", () => {
  const findings = scanText(`첫 줄\nopen ${HOME_PATH}/a.txt`);
  assert.deepEqual(findings, [{ line: 2, id: "local-path", shown: mask(["", "Users", "someone"].join("/")) }]);
  assert.ok(!findings[0].shown.includes("someone"));
});

test("집 와이파이 같은 내부 주소는 걸리고, 루프백과 문서용 주소와 버전 번호는 통과한다", () => {
  for (const ip of LAN_IPS) assert.deepEqual(ids(scanText(`http://${ip}:8790/`)), ["private-ip"], ip);
  assert.deepEqual(scanText("http://127.0.0.1:8790/ and 192.0.2.10 and 172.32.0.1"), []);
  assert.deepEqual(scanText("Windows SDK 10.0.19041.0"), []);
});

test("키와 토큰 형식은 걸린다", () => {
  const keys = {
    "anthropic-key": "sk-ant-" + "a".repeat(30),
    "openai-key": "sk-proj-" + "b".repeat(40),
    "github-token": "ghp_" + "c".repeat(36),
    "huggingface-token": "hf_" + "d".repeat(34),
    "private-key": "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
  };
  for (const [id, value] of Object.entries(keys)) assert.deepEqual(ids(scanText(`x = ${value}`)), [id], id);
});

test("키 모양이 낱말 가운데에 들어 있으면 키로 보지 않는다", () => {
  assert.deepEqual(scanText("expo-task-manager-with-a-very-long-package-name-here"), []);
});

test("noreply와 예시 이메일만 통과하고, 그 밖의 이메일은 걸린다", () => {
  assert.deepEqual(scanText("12345+someone@users.noreply.github.com a@example.com"), []);
  assert.deepEqual(ids(scanText(`mail ${PRIVATE_EMAIL}`)), ["email"]);
});

test("비공개 금지어는 대소문자를 가리지 않고 찾고, 무엇이 걸렸는지는 출력하지 않는다", () => {
  assert.deepEqual(scanText("첫 줄\nAcme Corp 메모", ["acme"]), [
    { line: 2, id: "private-term#1", shown: "(비공개 목록)" },
  ]);
});

test("re:로 시작하는 금지어는 정규식이라, 짧은 낱말을 다른 낱말 속에서 찾지 않는다", () => {
  const terms = ["acme", "re:\\bART\\b"];
  assert.deepEqual(ids(scanText("the ART tool", terms)), ["private-term#2"]);
  assert.deepEqual(scanText("start the party, art club", terms), []);
});

test("잘못된 정규식 금지어는 검사를 통과시키지 않고 오류를 낸다", () => {
  assert.throws(() => scanText("anything", ["acme", "re:("]), /2번째 금지어의 정규식이 잘못됐습니다/);
});

test("비공개 폴더, 환경 변수 파일, 녹음 파일은 경로만으로 걸린다", () => {
  assert.deepEqual(checkPath("docs/private/notes.md"), ["private-folder"]);
  assert.deepEqual(checkPath("app/docs/private/x.md"), ["private-folder"]);
  assert.deepEqual(checkPath(".env"), ["env-file"]);
  assert.deepEqual(checkPath("server/.env.local"), ["env-file"]);
  assert.deepEqual(checkPath("recordings/take1.txt"), ["recording"]);
  assert.deepEqual(checkPath("voice/take1.WAV"), ["recording"]);
  assert.deepEqual(checkPath("assets/clip.m4a"), ["recording"]);
});

test("예시 환경 변수 파일과 이름만 비슷한 문서는 통과한다", () => {
  assert.deepEqual(checkPath(".env.example"), []);
  assert.deepEqual(checkPath("docs/privatenote.md"), []);
  assert.deepEqual(checkPath("docs/guide/README.md"), []);
});

test("확장자를 바꾼 녹음도 파일 머리로 알아본다", () => {
  const wav = Buffer.concat([Buffer.from("RIFF"), Buffer.alloc(4), Buffer.from("WAVEfmt ")]);
  const m4a = Buffer.concat([Buffer.alloc(4), Buffer.from("ftypM4A "), Buffer.alloc(4)]);
  const heic = Buffer.concat([Buffer.alloc(4), Buffer.from("ftypheic"), Buffer.alloc(4)]);
  const png = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]);
  const utf16 = Buffer.from([0xff, 0xfe, 0x41, 0x00, 0x42, 0x00, 0x43, 0x00, 0x44, 0x00, 0x45, 0x00]);
  assert.equal(looksLikeAudio(wav), true);
  assert.equal(looksLikeAudio(m4a), true);
  assert.equal(looksLikeAudio(heic), false);
  assert.equal(looksLikeAudio(png), false);
  assert.equal(looksLikeAudio(utf16), false);
  assert.equal(looksLikeAudio(Buffer.from("plain text file\n")), false);
});
