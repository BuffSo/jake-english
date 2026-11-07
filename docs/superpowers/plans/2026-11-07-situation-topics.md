# 상황 주제 고르기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상황 정하기에서 주제(외국인 관광객, 미국 여행, 그 밖의 상황)를 먼저 고르고, 주제 안에서 목록, 제이크 추천, 직접 쓰기로 상황을 정한다. 대본의 첫 말과 끝 말은 상황에 맞게 정한다.

**Architecture:** 맥 서버에 주제와 목록 데이터(`topics.py`)를 두고 `/home`으로 앱에 알린다. 추천과 대본 만들기는 주제 id(목록이면 목록 줄 id)를 받아 Claude에게 역할과 첫 사람을 넘긴다. 앱은 상황 화면의 단계 규칙을 순수 함수(`flow/situation.ts`)로 두고, 역할극에서 돌아올 곳은 앱 상태(`flow/state.ts`)에 둔다.

**Tech Stack:** Python 3 + FastAPI + pydantic(서버, `uv run pytest`), React Native + Expo + jest(앱).

**Spec:** `docs/superpowers/specs/2026-11-07-situation-topics-design.md`

## Global Constraints

- 주제 이름은 그대로 쓴다: 「외국인 관광객」, 「미국 여행」, 「그 밖의 상황」. 주제 id는 `tourist`, `usa`, `other`.
- 정하는 방법 버튼: 「목록에서 고르기」, 「제이크에게 추천받기」, 「직접 말하거나 쓰기」.
- 라이언의 새 말: `ask_topic` 「어떤 주제로 연습해 볼까요?」, `ask_how` 「어떻게 상황을 정할까요?」, `ask_pick` 「해 보고 싶은 상황을 골라 주세요.」, `ask_describe` 「어떤 상황인지 말하거나 써 주세요.」
- 내 대사는 정확히 3번(`USER_TURNS = (3, 3)`), 대사는 번갈아 나온다. 「외국인 관광객」은 라이언이 먼저.
- 실제 가게, 호텔, 메뉴, 장소 이름은 써도 되고, 실제 사람 이름은 쓰지 않는다.
- 새 의존성을 설치하지 않는다.
- 테스트와 문서의 예문은 지어낸 것이다. 지난 역할극 기록의 대사와 상황을 옮기지 않는다.
- git은 `/usr/bin/git`으로 부른다. 커밋은 `git commit -F - <<'EOF'`, Conventional Commits 영어, scope는 `server`, `app` 또는 생략. AI 서명 줄을 넣지 않는다. 본문 끝에 `Refs: docs/superpowers/specs/2026-11-07-situation-topics-design.md`.
- `git add`는 파일을 지정한다.
- 서버 테스트: `cd server && uv run pytest -q`. 앱 테스트: `cd app && npx jest && npx tsc --noEmit`.

## Review Focus

1. 주제가 없는 지난 `roleplay.json`을 읽으면 그대로 읽히고 「그 밖의 상황」의 최근 상황에 든다(Task 1 테스트).
2. 앱이 없는 주제, 없는 목록 줄, 다른 주제의 목록 줄, 상황과 목록 줄을 함께 또는 둘 다 없이 보내면 500이 아니라 422 `bad_request`다(Task 3 테스트).
3. 목록 줄의 첫 사람이 나인데 Claude가 라이언으로 시작하는 대본을 주면 문제를 적어 다시 만들게 한다(Task 2 테스트).
4. 내 대사로 시작하는 대본은 역할극 화면이 처음부터 내 차례이고, 내 대사로 끝나는 대본은 그 대사 뒤 끝 화면으로 간다(Task 5 테스트).
5. 주제 단계로 돌아가 다른 주제를 고르면 거절한 추천 목록이 비워져, 앞 주제에서 거절한 것이 새 주제 추천에 섞이지 않는다(Task 4 테스트).

---

### Task 1: 주제와 목록 데이터, 기록의 주제

**Files:**
- Create: `server/je_server/topics.py`
- Modify: `server/je_server/models.py` (`Roleplay`), `server/je_server/store.py:77-79` (`recent_situations`), `contract/roleplay.json`
- Test: `server/tests/test_topics.py`, `server/tests/test_store.py`

**Interfaces:**
- Produces:
  - `topics.Pick` (frozen dataclass): `id: str`, `title_ko: str`, `situation: str`, `first: Speaker`
  - `topics.Topic` (frozen dataclass): `id: str`, `name_ko: str`, `roles_en: str`, `scenes_en: str`, `example_ko: str`, `placeholder_ko: str`, `first: Speaker | None`, `picks: tuple[Pick, ...]`
  - `topics.TOPICS: tuple[Topic, ...]` (순서: tourist, usa, other), `topics.OTHER = "other"`
  - `topics.get(topic_id: str) -> Topic` (없으면 `KeyError`), `topics.pick(topic_id: str, pick_id: str) -> Pick` (없거나 그 주제의 줄이 아니면 `KeyError`)
  - `topics.public() -> list[dict]`: `[{"id", "name_ko", "placeholder_ko", "picks": [{"id", "title_ko"}]}]` (앱에 보낼 것. `roles_en`, `situation`은 보내지 않는다)
  - `Roleplay.topic: str | None = None`
  - `Store.recent_situations(n: int = 10, topic: str = "other") -> list[str]`: `(rp.topic or "other") == topic`인 것만, 최신부터

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`test_topics.py`:
- `test_three_topics_in_order`: `[t.id for t in TOPICS] == ["tourist", "usa", "other"]`, 이름이 Global Constraints의 세 이름.
- `test_tourist_starts_with_ryan_and_is_strangers`: `get("tourist").first == "ryan"`, `"stranger" in roles_en.lower()`.
- `test_starting_lists`: tourist 3줄, usa 3줄, other 0줄. usa의 첫 사람 순서가 `["ryan", "user", "user"]`. tourist는 모두 `"ryan"`. 모든 `Pick.id`가 겹치지 않는다.
- `test_list_facts_checked_on_the_web` (스펙 3의 확인한 사실): 경복궁 줄 `situation`에 「5번 출구」, 교통카드 줄에 「현금」, 새우 트럭 줄에 「Giovanni's」와 「밥 두 스쿱」.
- `test_pick_must_belong_to_the_topic`: `pick("usa", <tourist 줄 id>)`가 `KeyError`, `get("nope")`가 `KeyError`.
- `test_public_leaves_out_prompt_text`: `public()`의 어느 값에도 `roles_en`이나 `situation` 키가 없다.

`test_store.py`:
- `test_recent_situations_by_topic`: tourist 하나, usa 하나, `topic=None` 하나를 저장하면 `recent_situations(topic="usa")`는 usa 것만, `recent_situations()`는 None 것만.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd server && uv run pytest tests/test_topics.py tests/test_store.py -q`
Expected: FAIL (`ModuleNotFoundError: je_server.topics`)

- [ ] **Step 3: `topics.py`를 쓰고 `Roleplay.topic`, `recent_situations`를 고친다**

목록 줄은 스펙 「3. 목록」의 표 그대로(카드 이름, 설명, 먼저). 줄 id는 `t-gyeongbokgung`, `t-tmoney`, `t-samgyeopsal`, `u-shrimp-truck`, `u-hotel-checkin`, `u-sneaker-size`. 주제의 영어 글:
- tourist `roles_en`: Ryan is a foreign tourist visiting Korea, a stranger to the learner; the learner is a Korean local who helps in English; never coworkers or friends. `scenes_en`: asking the way, using the subway, where to eat, with real places in Korea.
- usa `roles_en`: the learner is a Korean traveler in the United States; Ryan is someone there (shop or restaurant worker, hotel staff, passerby). `scenes_en`: cafes and fast food, hotel check-in, asking the way, shopping malls, with real places, shops and menus (New York, Hawaii).
- other `roles_en`: Ryan plays the other person in the situation. `scenes_en`: any real moment where the learner must speak English, other than helping a tourist in Korea or traveling in the US.
- `example_ko`: tourist 「인사동에서 외국인 관광객이 한복 빌리는 곳을 묻는 상황으로 연습해 보면 어때요?」, usa 「뉴욕 지하철역에서 역무원에게 표 사는 법을 묻는 상황으로 연습해 보면 어때요?」, other 「외국 회사에 전화해서 주문한 물건이 언제 오는지 묻는 상황으로 연습해 보면 어때요?」
- `placeholder_ko`: tourist 「예: 외국인이 명동에서 환전소를 묻는 상황」, usa 「예: 공항에서 짐이 안 나와 직원에게 묻는 상황」, other 「예: 외국 회사에 전화해 주문을 확인하는 상황」

`contract/roleplay.json`에 `"topic": "tourist"`를 더한다(`test_contract.py`가 모델과 같은지 본다).

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

`feat(server): add situation topics and their starting lists`

---

### Task 2: Claude에 주제와 첫 사람 넘기기

**Files:**
- Modify: `server/je_server/prompts.py` (`SCRIPT_SYSTEM`, `RECOMMEND_SYSTEM`, `CONTINUE_SYSTEM`), `server/je_server/claude.py` (`script_problems`, `make_script`, `recommend`, `continue_script`), `server/tests/fakes.py` (`FakeClaude.make_script`, `FakeClaude.recommend`, `script_lines`)
- Test: `server/tests/test_claude.py`

**Interfaces:**
- Consumes: `topics.Topic`, `topics.get`
- Produces:
  - `Claude.script_problems(draft: Draft, first: Speaker | None = None) -> list[str]`
  - `Claude.make_script(situation: str, topic: Topic, first: Speaker | None = None) -> tuple[Frame, Draft]`. 실제 첫 사람은 `first or topic.first`.
  - `Claude.recommend(recent: list[str], turned_down: Sequence[str], topic: Topic) -> str`
  - `continue_script`의 모양 검사: 학습자로 시작, 끝은 누구든.
  - `fakes.script_lines(user_turns: int, first: str = "ryan", last: str = "ryan") -> list[dict]`, `FakeClaude.make_script(situation, topic, first=None)`은 `first or topic.first or "ryan"`으로 시작하는 대본을 주고 `calls`에 `("make_script", (situation, topic.id, first))`, `FakeClaude.recommend(recent, turned_down, topic)`은 `("recommend", (recent, list(turned_down), topic.id))`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

- `test_make_script_sends_the_topic_roles_and_first`: `make_script("호텔 체크인", get("usa"), first="user")`의 요청 메시지에 usa `roles_en`과 「The learner speaks first」가 있다. 응답은 `script_lines(3, first="user")`.
- `test_make_script_retries_when_the_first_speaker_is_wrong`: tourist에 라이언이 아닌 학습자로 시작하는 대본, 그다음 맞는 대본을 주면 요청이 2번이고 두 번째 메시지에 「Ryan must speak first」.
- `test_script_may_start_and_end_with_either`: `script_problems`가 `first=None`일 때 U R U R U(5줄)와 R U R U R U(6줄)를 받아들이고, 번갈아 나오지 않거나 내 대사가 3이 아니면 막는다.
- `test_script_prompt_allows_real_places_but_not_people`: `SCRIPT_SYSTEM`에 「Ryan speaks first and Ryan speaks last」가 없고, real shops 허용과 real people 금지, 출구 번호, 주소, 영업시간을 지어내지 말라는 줄이 있다.
- `test_recommend_stays_in_the_topic`: `recommend(["…"], [], get("tourist"))` 메시지에 tourist `scenes_en`, `example_ko`, 그리고 tourist 목록의 세 `title_ko`(「목록에 있는 상황」 아래)가 있다. `RECOMMEND_SYSTEM`에 「연습해 보면 어때요?」가 그대로 있다.
- `test_continue_script_may_end_with_the_learner`: `[user, ryan, user]` 모양(학습자 2줄 요청)을 받아들인다. 라이언으로 시작하면 다시 요청한다.
- 기존 `recommend` 테스트 둘은 `topic=get("other")`를 넘기도록 고친다.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd server && uv run pytest tests/test_claude.py -q`
Expected: FAIL (`make_script() takes 2 positional arguments`)

- [ ] **Step 3: 프롬프트와 검사를 고친다**

- `make_script`의 메시지: `상황: …`, `Roles: <roles_en>`, 첫 사람이 정해졌으면 `Ryan speaks first.` 또는 `The learner speaks first.`, 아니면 `Whoever would naturally speak first in this situation speaks first.`
- `SCRIPT_SYSTEM` 규칙: 번갈아, 내 대사 정확히 3, 끝은 그 자리에서 자연스럽게 끝인사할 사람(학습자도 된다, 예 "Thanks, you too!"). 실제 가게, 호텔, 메뉴, 장소는 써도 되고 실제 사람은 안 된다. 상황 설명의 사실을 따르고, 설명에 없는 출구 번호, 주소, 영업시간, 확실하지 않은 메뉴와 값은 지어내지 않고 길 안내는 노선과 역 이름 정도로 한다. 주문 금액 같은 작은 값은 지어내도 된다.
- `script_problems`: 「Ryan must speak first and last」를 빼고, `first`가 있으면 `draft[0][0] != first`일 때 `"Ryan must speak first"` 또는 `"the learner must speak first"`.
- `recommend` 메시지: `주제: <scenes_en>`, `예: <example_ko>`, 최근 상황, 방금 거절한 상황(있을 때), `목록에 있는 상황:`(그 주제 목록의 `title_ko`, 있을 때). `RECOMMEND_SYSTEM`: 그 주제 안에서, 목록과 최근 상황과 다른 것, 실제 장소와 가게 이름 허용, 문장 모양은 지금 그대로.
- `CONTINUE_SYSTEM`과 검사: 학습자로 시작, 끝은 자연스럽게. 사실 규칙은 `SCRIPT_SYSTEM`과 같은 줄.

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: `test_claude.py` PASS. `test_engine.py`와 `test_api.py`는 Task 3에서 고칠 호출 때문에 실패해도 된다. 실패한 이름을 적어 Task 3에서 확인한다.

- [ ] **Step 5: 커밋**

`feat(server): give Claude the topic and let either speaker start or end`

---

### Task 3: 엔진과 API, 라이언의 새 말

**Files:**
- Modify: `server/je_server/engine.py` (`create`, `copy`, `recommend`), `server/je_server/app.py` (`NewRoleplay`, `Recommend`, `/home`, `/recommend`, `/roleplays`), `server/je_server/phrases.py`
- Test: `server/tests/test_engine.py`, `server/tests/test_api.py`, `server/tests/test_phrases.py`

**Interfaces:**
- Consumes: Task 1의 `topics.get`, `topics.pick`, `topics.public`, Task 2의 `Claude.make_script`, `Claude.recommend`
- Produces:
  - `Engine.create(situation: str, topic: str = "other", first: Speaker | None = None) -> Roleplay` (기록에 `topic`)
  - `Engine.copy`가 `topic=old.topic`을 그대로 둔다
  - `Engine.recommend(turned_down: Sequence[str] = (), topic: str = "other") -> Said`
  - `GET /home`: `lines`에 `ask_topic`, `ask_how`, `ask_pick`, `ask_describe`를 더한다(`ask_situation`은 옛 앱을 위해 남긴다). `topics: topics.public()`.
  - `POST /recommend`: `{skip: list[str], topic: str = "other"}`
  - `POST /roleplays`: `{situation?: str (1~300자), pick?: str (40자 이하), topic: str = "other"}`. 둘 중 하나만. `pick`이면 맥이 설명과 첫 사람을 찾는다. 없는 주제나 줄, 다른 주제의 줄, 둘 다 있거나 둘 다 없으면 422 `bad_request`.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

- `test_engine.py`: `test_create_keeps_the_topic`(`create("길 묻기", "tourist")`의 기록 `topic == "tourist"`, fake `calls`에 `("make_script", ("길 묻기", "tourist", None))`). `test_copy_keeps_the_topic`. `test_recommend_avoids_recent_of_the_same_topic`(usa 하나와 tourist 하나를 만든 뒤 `recommend([], "usa")`의 recent가 usa 상황만). 기존 `test_recommend_passes_turned_down`은 `"other"`로 고친다.
- `test_api.py`:
  - `test_home_lists_fixed_lines`의 기대 집합에 새 말 넷을 더한다.
  - `test_home_lists_topics`: `[t["id"] for t in j["topics"]] == ["tourist", "usa", "other"]`, tourist의 `picks` 3개에 `id`와 `title_ko`만 있다.
  - `test_create_from_a_pick`: `post("/roleplays", json={"topic": "usa", "pick": "u-hotel-checkin"})` 200, fake `calls`의 situation이 그 줄의 설명이고 first가 `"user"`, 응답 `topic == "usa"`.
  - `test_create_rejects_bad_topic_or_pick`: `{"topic": "nope", "situation": "x"}`, `{"topic": "usa", "pick": "t-tmoney"}`, `{"topic": "usa", "pick": "u-none"}`, `{"topic": "usa"}`, `{"topic": "usa", "situation": "x", "pick": "u-hotel-checkin"}` 모두 422 `bad_request`.
  - `test_create_without_topic_is_other`: `{"situation": "길 묻기"}`(옛 앱)이면 `topic == "other"`.
  - `test_recommend_route_takes_the_topic`: `{"skip": [], "topic": "tourist"}`이면 fake의 topic이 `"tourist"`. `{"topic": "nope"}`이면 422.
- `test_phrases.py`: `test_topic_steps_have_ryans_lines`: 새 말 넷이 Global Constraints의 글 그대로다.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd server && uv run pytest -q`
Expected: FAIL (위 새 테스트와 Task 2에서 적어 둔 것)

- [ ] **Step 3: 엔진, API, 말을 고친다**

`NewRoleplay`에 pydantic `model_validator(mode="after")`로 「situation과 pick 중 하나만」과 주제, 줄 확인을 넣어 `RequestValidationError`(422 `bad_request`)로 떨어지게 한다. 주제 id는 `topics.TOPICS`의 id로 확인한다.

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd server && uv run pytest -q`
Expected: 모두 PASS

- [ ] **Step 5: 커밋**

`feat(server): take the topic and list pick in recommend and roleplay creation`

---

### Task 4: 앱의 API와 상황 화면 단계 규칙

**Files:**
- Create: `app/src/flow/situation.ts`
- Modify: `app/src/api/types.ts` (`Home`, `Roleplay`, 새 `Topic`), `app/src/api/client.ts` (`recommend`, `createRoleplay`), `app/src/ui/faces.ts` (`Step` → `SituationStep`)
- Test: `app/src/flow/situation.test.ts`, `app/src/api/client.test.ts`, `app/src/ui/faces.test.ts`

**Interfaces:**
- Produces:
  - `types.Topic = { id: string; name_ko: string; placeholder_ko: string; picks: { id: string; title_ko: string }[] }`
  - `Home.topics: Topic[]`, `Home.lines`에 `ask_topic`, `ask_how`, `ask_pick`, `ask_describe: Said`, `Roleplay.topic?: string | null`
  - `api.recommend(skip: string[], topic: string): Promise<Said>` → body `{ skip, topic }`
  - `api.createRoleplay(choice: { situation: string } | { pick: string }, topic: string): Promise<Roleplay>` → body `{ ...choice, topic }`
  - `situation.ts`:
    - `type SituationStep = "topic" | "how" | "list" | "describe" | "askRecommend" | "working" | "confirm"`
    - `type Origin = "how" | "list" | "describe"` (상황을 고른 단계, 뒤로와 역할극에서 돌아올 곳)
    - `type SituationStart = { topic: string; step: Origin }`
    - `type HowChoice = "list" | "jake" | "describe"`
    - `howChoices(t: Topic): HowChoice[]` (목록이 비면 `"list"`를 뺀다)
    - `backFrom(step: SituationStep, origin: Origin): SituationStep | null` (topic→null, how→"topic", list와 describe→"how", askRecommend→"describe", working과 confirm→origin)
    - `startStep(start: SituationStart | null): SituationStep` (null이면 "topic")
    - `lineFor(step: SituationStep): keyof Home["lines"] | null` (topic→ask_topic, how→ask_how, list→ask_pick, describe→ask_describe, askRecommend→ask_recommend, 나머지 null)
    - `HOW_LABEL: Record<HowChoice, string>` (Global Constraints의 버튼 이름)
  - `faces.circleFace(step: SituationStep, before: Face, jake: boolean): Face` (동작은 지금과 같다)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

- `situation.test.ts`: `howChoices`가 picks 없는 주제에서 `["jake", "describe"]`, 있는 주제에서 `["list", "jake", "describe"]`. `backFrom`의 각 줄(위 표). `backFrom("confirm", "how") === "how"`, `backFrom("working", "list") === "list"`, `backFrom("topic", "how") === null`. `startStep(null) === "topic"`, `startStep({ topic: "usa", step: "list" }) === "list"`. `lineFor`의 각 줄.
- 거절 목록이 주제 단계에서 비워지는 것(Review Focus 5): `situation.ts`에 `clearsTurnedDown(next: SituationStep): boolean`(next가 "topic"일 때 true)을 두고 테스트한다.
- `client.test.ts`: `recommend(skip, "tourist")`의 body가 `{ skip, topic: "tourist" }`. `createRoleplay({ pick: "u-hotel-checkin" }, "usa")`의 body가 `{ pick: "u-hotel-checkin", topic: "usa" }`. 기존 `createRoleplay("길 묻기")` 테스트는 `({ situation: "길 묻기" }, "other")`로 고친다.
- `faces.test.ts`: 기존 테스트가 새 `SituationStep`으로 돈다. `circleFace("list", "listening", true) === "listening"`.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd app && npx jest src/flow/situation.test.ts src/api/client.test.ts src/ui/faces.test.ts`
Expected: FAIL (`Cannot find module './situation'`)

- [ ] **Step 3: 구현한다**

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd app && npx jest src/flow src/api src/ui`
Expected: PASS. `npx tsc --noEmit`은 `SituationScreen.tsx`의 옛 호출 때문에 실패해도 된다(Task 5에서 고친다).

- [ ] **Step 5: 커밋**

`feat(app): add situation topic steps and send the topic to the server`

---

### Task 5: 상황 화면과 역할극에서 돌아오기

**Files:**
- Modify: `app/src/screens/SituationScreen.tsx`, `app/src/flow/state.ts` (`State.situationFrom`, `created`, `back`, `restarted`), `app/App.tsx`
- Test: `app/src/flow/state.test.ts`

**Interfaces:**
- Consumes: Task 4의 `situation.ts` 전부, `api.recommend`, `api.createRoleplay`, `Home.topics`
- Produces:
  - `State.situationFrom: SituationStart | null` (`initial`은 null)
  - `Action` `{ type: "created"; roleplay: Roleplay; jake?: Said | null; from?: SituationStart }`
  - `SituationScreen` props에 `start: SituationStart | null`, `onCreated(rp: Roleplay, jake: Said | null, from: SituationStart)`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`state.test.ts`:
- `test("back from a roleplay returns to the step the situation came from")`: `created`에 `from: { topic: "usa", step: "list" }` → 역할극에서 `back` → `screen === "situation"`, `situationFrom`이 같다. 끝 화면에서 `back`도 같다.
- `test("restarting keeps where back leads")`: 끝 화면에서 `restarted` 뒤 `back`이 같은 `situationFrom`으로 간다.
- `test("choosing roleplay from home starts at the topic")`: `chooseRoleplay` 뒤 `situationFrom === null`.
- `test("a script that starts with my line starts on my turn")`: 첫 줄이 user인 roleplay로 `created` → `lineLoaded`(user 줄) → `phase === "ready"`, `history`가 비어 있다.
- `test("a script that ends with my line ends after it")`: 마지막 user 줄에서 `done`(`next` = 그 줄 + 1) → `next` → `lineMissing` → `screen === "end"`.

- [ ] **Step 2: 돌려서 실패를 본다**

Run: `cd app && npx jest src/flow/state.test.ts`
Expected: FAIL (`situationFrom` 없음). 처음 말과 끝 말 테스트는 지금도 통과할 수 있다. 통과하면 그대로 둔다(동작을 묶어 두는 테스트다).

- [ ] **Step 3: 상태와 화면을 고친다**

- `state.ts`: `back`에서 역할극과 끝 화면(`returnTo`도 `past`도 없을 때)은 `{ ...initial, screen: "situation", situationFrom: s.situationFrom }`. `created`는 `situationFrom: a.from ?? null`. `restarted`는 `returnTo`가 없을 때 `situationFrom`을 그대로 둔다.
- `SituationScreen.tsx`: 단계는 `startStep(start)`에서 시작하고, 주제는 `start?.topic`. 단계에 들어갈 때 `lineFor(step)`의 말을 한 번 들려준다. 뒤로는 `backFrom`(null이면 지금처럼 녹음을 버리고 `onBack`). `clearsTurnedDown`이면 거절 목록을 비운다. 각 단계의 화면은 스펙 「2. 화면」대로다:
  - 주제: 듣는 얼굴, `ask_topic` 글, `home.topics`마다 버튼(「그 밖의 상황」은 `kind="plain"`).
  - 정하는 방법: 주제 이름(작게), `ask_how` 글, `howChoices(topic)`마다 버튼(첫 버튼만 기본 색).
  - 목록: 얼굴 없음, `ask_pick` 글, `ScrollView` 안에 카드(연회색 둥근 칸, 오른쪽에 「›」). 누르면 `create({ pick }, "list")`.
  - 제이크 추천: `ask_recommend`를 거치지 않고 바로 `recommend()`. origin은 "how".
  - 직접 쓰기: `ask_describe` 글, 입력 칸(보기 글은 `topic.placeholder_ko`), 「🎤 말로 하기」, 「시작」. 「추천해 줘」 버튼은 없다. 빈 칸이나 「모르겠어」, 「추천」이면 `askRecommend` 단계(origin "describe").
  - `create`와 `recommend`는 `api.createRoleplay(choice, topic.id)`, `api.recommend(turnedDown, topic.id)`. 만들어지면 `onCreated(rp, jake, { topic: topic.id, step: origin })`.
  - 기다림, 제이크 확인, 오류 표시는 지금과 같다. 단계가 늘었을 뿐 `gen`, `gate`, `choice` 래치는 그대로 쓴다.
- `App.tsx`: `start={state.situationFrom}`, `onCreated={(roleplay, jake, from) => dispatch({ type: "created", roleplay, jake, from })}`.

- [ ] **Step 4: 돌려서 통과를 본다**

Run: `cd app && npx jest && npx tsc --noEmit`
Expected: 모두 PASS, 타입 오류 없음

- [ ] **Step 5: 커밋**

`feat(app): pick a topic, then a list entry, Jake's idea or my own on the situation screen`

---

### Task 6: 문서 마무리와 전체 확인

**Files:**
- Modify: `docs/superpowers/specs/2026-11-05-speaking-practice-design.md` (머리의 「고침」 줄), `docs/PRD.md`(구현하며 바뀐 것이 있으면)
- Create: `docs/todo/20261107_03_todo_situation_topics.md` (원래 폴더의 파일을 복사해 상태를 고친다)

- [ ] **Step 1: 말하기 스펙에 「고침」 줄을 더한다**

「2026-11-07 「상황 정하기(역할극)」 앞에 주제 고르기와 목록에서 고르기가 생기고, 대본의 처음과 끝 사람을 상황에 맞게 바꿨다(`docs/superpowers/specs/2026-11-07-situation-topics-design.md`). 이 문서의 「라이언이 먼저 말하고 끝낸다」는 그 스펙이 대신한다.」

- [ ] **Step 2: 할 일 파일을 완료로 고쳐 넣는다**

원래 폴더(`git worktree list`의 첫 줄)의 `docs/todo/20261107_03_todo_situation_topics.md`를 이 worktree의 같은 자리에 복사하고, 상태 줄을 `> 상태: **완료** (2026-11-07 situation-topics 카드, 스펙 docs/superpowers/specs/2026-11-07-situation-topics-design.md)`로 고친다. 원래 폴더의 파일은 머지 뒤 fast-forward로 같아지니 지우지 않는다.

- [ ] **Step 3: 전체 테스트를 돌린다**

Run: `cd server && uv run pytest -q` 그리고 `cd app && npx jest && npx tsc --noEmit` 그리고 `node --test 'scripts/**/*.test.mjs'`
Expected: 모두 PASS. 통과 개수를 PR 테스트 체크리스트에 적는다.

- [ ] **Step 4: 커밋**

`docs: mark situation topics done and point the speaking spec at it`
