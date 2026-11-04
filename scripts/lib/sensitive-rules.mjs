// 공개 금지 검사 규칙 (AGENTS.md 「커밋 전 자동 검사」)
// 커밋 전 검사(scripts/check-sensitive.mjs)와 커밋 메시지 검사(scripts/check-commit-msg.mjs)가 함께 쓴다.
// 형식으로 찾는 검사라 문맥상의 노출은 다 잡지 못한다. 그건 리뷰(REVIEW.md)가 본다.

import { existsSync, readFileSync } from "node:fs";

// 비공개 금지어 목록. 목록 자체가 민감 정보라 git에서 뺀 docs/private/에 둔다.
// 한 줄에 하나. #으로 시작하면 주석이다. re:로 시작하면 정규식(대소문자 구분)이고, 나머지는 대소문자를 가리지 않는 부분 일치다.
export const PRIVATE_TERMS_PATH = "docs/private/sensitive-terms.txt";

// 공개해도 되는 이메일: GitHub noreply, 예시 도메인, git 원격 주소
const ALLOWED_EMAILS = [/@users\.noreply\.github\.com$/i, /@example\.(com|org|net)$/i, /^git@github\.com$/i];

// 키 모양 값은 앞에 글자나 숫자가 붙어 있으면 키로 보지 않는다. 긴 패키지 이름 속의 sk- 같은 것을 거르려는 것이다.
const NOT_IN_WORD = "(?<![A-Za-z0-9])";

const RULES = [
  { id: "phone-mobile", re: /(?<!\d)01[016789][-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)/g },
  { id: "phone-landline", re: /(?<!\d)0(?:2|[3-6][1-5])[-.\s]\d{3,4}[-.\s]\d{4}(?!\d)/g },
  { id: "resident-number", re: /(?<!\d)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])-[1-4]\d{6}(?!\d)/g },
  { id: "local-path", re: /\/Users\/[^/\s"'`)]+|\/home\/[a-z_][a-z0-9_-]*\/|[A-Za-z]:\\Users\\/g },
  // 집 와이파이 안의 맥 주소 같은 내부 주소. 루프백(127.x)과 문서용 주소(192.0.2.x)는 통과한다.
  {
    id: "private-ip",
    re: /(?<![\d.])(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}(?![\d]|\.\d)/g,
  },
  { id: "anthropic-key", re: new RegExp(`${NOT_IN_WORD}sk-ant-[A-Za-z0-9_-]{20,}`, "g") },
  { id: "openai-key", re: new RegExp(`${NOT_IN_WORD}sk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}`, "g") },
  { id: "aws-access-key", re: new RegExp(`${NOT_IN_WORD}(?:AKIA|ASIA)[0-9A-Z]{16}`, "g") },
  { id: "github-token", re: new RegExp(`${NOT_IN_WORD}(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})`, "g") },
  { id: "google-api-key", re: new RegExp(`(?<![A-Za-z0-9+/])AIza[0-9A-Za-z_-]{35}`, "g") },
  { id: "huggingface-token", re: new RegExp(`${NOT_IN_WORD}hf_[A-Za-z0-9]{30,}`, "g") },
  { id: "slack-token", re: new RegExp(`${NOT_IN_WORD}xox[abprs]-[A-Za-z0-9-]{10,}`, "g") },
  { id: "private-key", re: /-----BEGIN [A-Z ]*PRIVATE KEY-----/g },
  { id: "secret-assignment", re: /\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*["'][^"'\s]{12,}["']/gi },
];

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

// 녹음과 음성 파일. 사용자 목소리라 민감 정보다. 동영상도 소리가 들어 있을 수 있어 막는다.
const RECORDING_EXT = /\.(wav|m4a|mp3|aac|ogg|oga|opus|flac|caf|aif|aiff|amr|3gp|wma|webm|mp4|mov|mkv)$/i;

/** 금지어 파일을 읽는다. 파일이 없으면 null이다. 없는 것과 비어 있는 것을 부르는 쪽이 구분하게 하려는 것이다. */
export function readTermsFile(file) {
  if (!existsSync(file)) return null;
  return readFileSync(file, "utf8")
    .split("\n")
    .map((s) => s.trim())
    .filter((s) => s && !s.startsWith("#"));
}

// 찾은 값은 가려서 출력한다. 검사 결과 로그가 또 다른 노출 경로가 되지 않게 하려는 것이다.
export function mask(value) {
  const v = value.trim();
  return v.length <= 4 ? "****" : `${v.slice(0, 2)}${"*".repeat(Math.min(v.length - 2, 8))}`;
}

function compileTerms(terms) {
  return terms.map((term, n) => {
    if (!term.startsWith("re:")) {
      const lower = term.toLowerCase();
      return (text) => text.toLowerCase().includes(lower);
    }
    let re;
    try {
      re = new RegExp(term.slice(3));
    } catch {
      // 잘못 쓴 줄을 건너뛰면 그 금지어는 검사되지 않은 채 통과한다. 그래서 검사를 멈춘다.
      throw new Error(`${PRIVATE_TERMS_PATH}의 ${n + 1}번째 금지어의 정규식이 잘못됐습니다(주석 줄은 세지 않음). 그 줄을 고치세요.`);
    }
    return (text) => re.test(text);
  });
}

/**
 * 글 하나를 검사해 { line, id, shown } 목록을 돌려준다. line은 1부터 센다.
 * personalEmails는 공개 주소 모양이어도 막을 개인 이메일이다(전역 git 이메일). 금지어 목록에 적지 않아도 막히게 하려는 것이다.
 */
export function scanText(content, terms = [], personalEmails = []) {
  const matchers = compileTerms(terms);
  const findings = [];

  content.split("\n").forEach((text, i) => {
    const line = i + 1;

    for (const { id, re } of RULES) {
      for (const m of text.matchAll(re)) findings.push({ line, id, shown: mask(m[0]) });
    }

    for (const m of text.matchAll(EMAIL_RE)) {
      if (!ALLOWED_EMAILS.some((re) => re.test(m[0]))) findings.push({ line, id: "email", shown: mask(m[0]) });
    }

    matchers.forEach((matches, n) => {
      if (matches(text)) findings.push({ line, id: `private-term#${n + 1}`, shown: "(비공개 목록)" });
    });

    const lower = text.toLowerCase();
    for (const email of personalEmails) {
      if (lower.includes(email.toLowerCase())) findings.push({ line, id: "personal-email", shown: "(전역 git 이메일)" });
    }
  });

  return findings;
}

/** 경로만 보고 커밋하면 안 되는 파일인지 판단해 걸린 규칙 이름 목록을 돌려준다 */
export function checkPath(path) {
  const found = [];
  if (/(^|\/)docs\/private\//.test(path)) found.push("private-folder");
  const name = path.split("/").at(-1);
  if (/^\.env(\..+)?$/.test(name) && name !== ".env.example") found.push("env-file");
  if (/(^|\/)recordings\//.test(path) || RECORDING_EXT.test(name)) found.push("recording");
  return found;
}

// ftyp 상자를 쓰는 사진 형식. 이것만 녹음으로 보지 않는다.
const IMAGE_BRANDS = new Set(["heic", "heix", "hevc", "heim", "heis", "mif1", "msf1", "avif", "avis"]);
// MP3 프레임과 AAC(ADTS)의 둘째 바이트. 0xFE(UTF-16 BOM)와 0xD8(JPEG)은 넣지 않는다.
const MPEG_SYNC = new Set([0xfb, 0xfa, 0xf3, 0xf2, 0xe3, 0xe2, 0xf1, 0xf9]);

/** 파일 머리를 보고 소리 파일인지 판단한다. 확장자를 바꾼 녹음을 잡으려는 것이다. */
export function looksLikeAudio(buf) {
  if (buf.length < 12) return false;
  const at = (start, end) => buf.subarray(start, end).toString("latin1");
  if (at(0, 4) === "RIFF" && at(8, 12) === "WAVE") return true;
  if (at(0, 4) === "FORM" && ["AIFF", "AIFC"].includes(at(8, 12))) return true;
  if (["ID3", "#!A"].includes(at(0, 3))) return true;
  if (["fLaC", "OggS", "caff"].includes(at(0, 4))) return true;
  if (buf[0] === 0x1a && buf[1] === 0x45 && buf[2] === 0xdf && buf[3] === 0xa3) return true;
  if (at(4, 8) === "ftyp") return !IMAGE_BRANDS.has(at(8, 12).trim().toLowerCase());
  return buf[0] === 0xff && MPEG_SYNC.has(buf[1]);
}
