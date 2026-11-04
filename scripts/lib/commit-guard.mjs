// 커밋 가드 훅의 판정 (scripts/hooks/guard-git.mjs, CLAUDE.md 「커밋 전 자동 검사」)
// jake-homepage(ADR-0006)의 판정을 가져와, commit만 찾던 것을 git 하위 명령 전체(commit, push)로 넓혔다.
// 명령 문자열에서 실제로 git을 실행하는 자리만 찾고, 훅을 건너뛰는 옵션은 그 인자에서만 찾는다.
// 명령 전체에서 git-commit과 -n을 따로 찾으면, sed -n이나 grep -n이 같은 명령에 있을 때 커밋이 아니어도 막는다.
// 셸 문법을 모두 다루지는 않는다. 따옴표, 주석, 구간 구분자, 리다이렉트, 명령 치환, 히어독,
// 예약어와 감싸는 명령, bash -c와 eval을 본다. 함수와 별칭은 보지 않는다.

// 구간 앞에 올 수 있는 셸 예약어
const KEYWORDS = new Set(["if", "then", "else", "elif", "do", "while", "until", "!", "{", "time"]);
// 구간 앞에서 건너뛰는 명령. 뒤에 붙는 옵션과 숫자 인자(timeout 60, nice -n 10)도 건너뛴다.
// RTK 훅이 git을 rtk git으로 바꾸므로 rtk도 넣는다.
const WRAPPERS = new Set(["rtk", "proxy", "command", "env", "exec", "nohup", "sudo", "timeout", "nice", "xargs"]);
const SHELLS = new Set(["bash", "sh", "zsh"]);
// 값을 다음 낱말로 받는 git 전역 옵션
const GIT_VALUE_OPTIONS = new Set(["-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"]);
// git commit에서 값을 받는 짧은 옵션. 같은 낱말의 뒤 글자나 다음 낱말이 값이다.
const COMMIT_VALUE_SHORT = new Set(["m", "F", "c", "C", "t"]);
// 값을 붙여서만 받는 짧은 옵션 (-uno, -Skey)
const COMMIT_ATTACHED_SHORT = new Set(["u", "S"]);
const COMMIT_VALUE_LONG = new Set([
  "--message",
  "--file",
  "--reuse-message",
  "--reedit-message",
  "--template",
  "--author",
  "--date",
  "--fixup",
  "--squash",
  "--cleanup",
  "--trailer",
  "--pathspec-from-file",
]);

const OPERATORS = ["&&", "||", ";", "|", "&", "(", ")"];

/** `$(`나 `<(`의 여는 괄호 다음 자리부터 짝이 맞는 닫는 괄호의 자리를 찾는다. 따옴표 안의 괄호는 세지 않는다. */
function closeParen(input, start) {
  let depth = 1;
  let i = start;
  while (i < input.length) {
    const c = input[i];
    if (c === "\\") i += 2;
    else if (c === "'") i = closeQuote(input, i, "'") + 1;
    else if (c === '"') i = closeDouble(input, i + 1).end + 1;
    else if (c === "`") i = closeQuote(input, i, "`") + 1;
    else {
      if (c === "(") depth++;
      if (c === ")" && --depth === 0) return i;
      i++;
    }
  }
  return input.length;
}

function closeQuote(input, start, quote) {
  const end = input.indexOf(quote, start + 1);
  return end < 0 ? input.length : end;
}

/** 큰따옴표 안을 읽는다. 안에 든 명령 치환은 따로 모은다. */
function closeDouble(input, start) {
  let i = start;
  let text = "";
  const substs = [];
  while (i < input.length && input[i] !== '"') {
    if (input[i] === "\\" && i + 1 < input.length) {
      text += input[i + 1];
      i += 2;
    } else if (input.startsWith("$(", i)) {
      const end = closeParen(input, i + 2);
      substs.push(input.slice(i + 2, end));
      text += "$()";
      i = end + 1;
    } else if (input[i] === "`") {
      const end = closeQuote(input, i, "`");
      substs.push(input.slice(i + 1, end));
      text += "``";
      i = end + 1;
    } else {
      text += input[i++];
    }
  }
  return { end: i, text, substs };
}

/** 낱말, 구간 구분자, 리다이렉트, 히어독 본문, 명령 치환으로 나눈다 */
function lex(input) {
  const tokens = [];
  const pending = [];
  let word = null;
  const flush = () => {
    if (word !== null) tokens.push({ type: "word", value: word });
    word = null;
  };
  const subst = (body) => tokens.push({ type: "subst", value: body });

  let i = 0;
  while (i < input.length) {
    const c = input[i];
    if (c === "#" && word === null) {
      // 주석은 줄 끝까지 건너뛴다. 주석 속 따옴표나 구분자가 다음 줄을 흐트러뜨리지 않게 한다.
      const end = input.indexOf("\n", i);
      i = end < 0 ? input.length : end;
    } else if (input.startsWith("$'", i)) {
      // $'…'(ANSI-C 따옴표) 안에서는 \'가 따옴표를 닫지 않는다
      let j = i + 2;
      let text = "";
      while (j < input.length && input[j] !== "'") {
        if (input[j] === "\\") {
          text += input[j + 1] === "n" ? "\n" : (input[j + 1] ?? "");
          j += 2;
        } else {
          text += input[j++];
        }
      }
      word = (word ?? "") + text;
      i = j + 1;
    } else if (c === "'") {
      const end = closeQuote(input, i, "'");
      word = (word ?? "") + input.slice(i + 1, end);
      i = end + 1;
    } else if (c === '"') {
      const { end, text, substs } = closeDouble(input, i + 1);
      substs.forEach(subst);
      word = (word ?? "") + text;
      i = end + 1;
    } else if (c === "\\") {
      if (input[i + 1] !== "\n") word = (word ?? "") + (input[i + 1] ?? "");
      i += 2;
    } else if (input.startsWith("$(", i) || input.startsWith("<(", i) || input.startsWith(">(", i)) {
      const end = closeParen(input, i + 2);
      subst(input.slice(i + 2, end));
      word = (word ?? "") + "$()";
      i = end + 1;
    } else if (c === "`") {
      const end = closeQuote(input, i, "`");
      subst(input.slice(i + 1, end));
      word = (word ?? "") + "``";
      i = end + 1;
    } else if (c === " " || c === "\t") {
      flush();
      i++;
    } else if (c === "\n") {
      flush();
      const { next, bodies } = readHeredocs(input, i + 1, pending.splice(0));
      for (const body of bodies) tokens.push({ type: "heredoc", value: body });
      tokens.push({ type: "op", value: "\n" });
      i = next;
    } else if (input.startsWith("<<", i) && !input.startsWith("<<<", i)) {
      flush();
      const strip = input[i + 2] === "-";
      let j = i + (strip ? 3 : 2);
      while (input[j] === " " || input[j] === "\t") j++;
      let k = j;
      while (k < input.length && !/[\s;&|()<>]/.test(input[k])) k++;
      pending.push({ end: input.slice(j, k).replace(/['"\\]/g, ""), strip });
      i = k;
    } else if (c === ">" || c === "<" || input.startsWith("&>", i)) {
      // 2>/dev/null의 2처럼 리다이렉트 앞의 숫자는 파일 번호라 낱말로 남기지 않는다
      if (word !== null && /^\d+$/.test(word)) word = null;
      flush();
      let j = i + 1;
      while (j < input.length && /[<>&|]/.test(input[j])) j++;
      tokens.push({ type: "redirect", value: input.slice(i, j) });
      i = j;
    } else {
      const op = OPERATORS.find((o) => input.startsWith(o, i));
      if (op) {
        flush();
        tokens.push({ type: "op", value: op });
        i += op.length;
      } else {
        word = (word ?? "") + c;
        i++;
      }
    }
  }
  flush();
  return tokens;
}

/** 히어독 본문을 끝 표시 줄까지 읽고, 다음 명령이 시작하는 자리를 돌려준다 */
function readHeredocs(input, start, heredocs) {
  let i = start;
  const bodies = [];
  for (const { end, strip } of heredocs) {
    const lines = [];
    while (i < input.length) {
      const lineEnd = input.indexOf("\n", i) < 0 ? input.length : input.indexOf("\n", i);
      const line = input.slice(i, lineEnd);
      i = lineEnd + 1;
      if ((strip ? line.replace(/^\t+/, "") : line) === end) break;
      lines.push(line);
    }
    bodies.push(lines.join("\n"));
  }
  return { next: i, bodies };
}

/** 구간마다 낱말과 히어독 본문. 리다이렉트와 그 대상은 낱말에서 뺀다. 명령 치환은 따로 모은다. */
function parse(command) {
  const segments = [{ words: [], heredocs: [] }];
  const substs = [];
  let skipNext = false;
  for (const token of lex(command)) {
    const current = segments.at(-1);
    if (token.type === "op") {
      segments.push({ words: [], heredocs: [] });
      skipNext = false;
    } else if (token.type === "redirect") {
      skipNext = true;
    } else if (token.type === "heredoc") {
      current.heredocs.push(token.value);
    } else if (token.type === "subst") {
      substs.push(token.value);
    } else if (skipNext) {
      skipNext = false;
    } else {
      current.words.push(token.value);
    }
  }
  return { segments: segments.filter((s) => s.words.length > 0), substs };
}

const baseName = (word) => word?.split("/").at(-1);

/** 셸에 넘긴 명령 문자열 (bash -c "…", bash -lc '…') */
function shellScript(words, from) {
  let flag = words.indexOf("-c", from);
  if (flag < 0) flag = words.findIndex((word, j) => j >= from && /^-[a-z]{1,3}$/.test(word) && word.includes("c"));
  return flag < 0 ? undefined : words[flag + 1];
}

/** 명령에서 git을 실행하는 자리마다 { sub: 하위 명령, args: 그 뒤 인자, globals: git과 하위 명령 사이의 전역 옵션 }을 돌려준다 */
export function findGitCommands(command) {
  const { segments, substs } = parse(command);
  const found = substs.flatMap(findGitCommands);
  for (const { words, heredocs } of segments) {
    let i = 0;
    while (i < words.length) {
      if (KEYWORDS.has(words[i]) || /^[A-Za-z_]\w*=/.test(words[i])) {
        i++;
      } else if (WRAPPERS.has(baseName(words[i]))) {
        i++;
        while (i < words.length && (words[i].startsWith("-") || /^\d+(\.\d+)?[smhd]?$/.test(words[i]))) i++;
      } else {
        break;
      }
    }
    const name = baseName(words[i]);
    if (SHELLS.has(name)) {
      // bash -c "…"의 문자열, 또는 bash <<EOF로 넘긴 본문을 다시 검사한다
      const script = shellScript(words, i + 1);
      const scripts = script === undefined ? heredocs : [script];
      found.push(...scripts.flatMap(findGitCommands));
      continue;
    }
    if (name === "eval") {
      found.push(...findGitCommands(words.slice(i + 1).join(" ")));
      continue;
    }
    if (name !== "git") continue;
    i++;
    const globals = [];
    while (i < words.length && words[i].startsWith("-")) {
      const width = GIT_VALUE_OPTIONS.has(words[i]) ? 2 : 1;
      globals.push(...words.slice(i, i + width));
      i += width;
    }
    if (i < words.length) found.push({ sub: words[i], args: words.slice(i + 1), globals });
  }
  return found;
}

/** 명령에서 git commit을 실행하는 자리마다 commit 뒤의 인자 목록을 돌려준다 */
export function findCommits(command) {
  return findGitCommands(command)
    .filter((c) => c.sub === "commit")
    .map((c) => c.args);
}

/** git 전역 옵션(-c, --config-env)으로 core.hooksPath를 바꾸는지. 훅 폴더를 바꾸면 git 훅이 모두 빠진다. */
export function overridesHooksPath(globals) {
  const hooksPath = /^core\.hookspath(=|$)/i;
  return globals.some((word, i) => {
    if (word === "-c" || word === "--config-env") return hooksPath.test(globals[i + 1] ?? "");
    return word.startsWith("--config-env=") && hooksPath.test(word.slice("--config-env=".length));
  });
}

/** git push 인자에 훅을 건너뛰는 옵션(--no-verify)이 있는지. push의 -n은 시험 실행이라 보지 않는다. */
export function skipsPushHooks(args) {
  for (const arg of args) {
    if (arg === "--") return false;
    if (arg.length >= "--no-veri".length && "--no-verify".startsWith(arg)) return true;
  }
  return false;
}

/** git commit 인자에 훅을 건너뛰는 옵션(--no-verify, -n)이 있는지 */
export function skipsHooks(args) {
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg === "--") return false;
    // git은 긴 옵션의 줄임도 받는다. --no-ver까지는 --no-verbose와 겹쳐 git이 거부한다.
    if (arg.length >= "--no-veri".length && "--no-verify".startsWith(arg)) return true;
    if (arg.startsWith("--")) {
      if (COMMIT_VALUE_LONG.has(arg)) i++;
      continue;
    }
    if (!arg.startsWith("-") || arg === "-") continue;
    for (let k = 1; k < arg.length; k++) {
      const flag = arg[k];
      if (flag === "n") return true;
      if (COMMIT_ATTACHED_SHORT.has(flag)) break;
      if (COMMIT_VALUE_SHORT.has(flag)) {
        if (k === arg.length - 1) i++;
        break;
      }
    }
  }
  return false;
}
