"""Things Ryan always says the same way. Made once in Ryan's Korean voice when the server starts."""

PHRASES: dict[str, str] = {
    "greeting": "안녕하세요, 라이언입니다. 오늘도 만나서 반가워요.",
    "ask_mode": "오늘은 무엇을 연습해 볼까요?",
    # coming back to the first screen: greeting and ask_mode play once, when the app starts (2026-11-06 user)
    "ask_again": "이번에는 무엇을 연습해 볼까요?",
    "ask_situation": "어떤 상황으로 연습해 볼까요? 말하거나 써 주세요. 정하기 어려우면 제이크가 추천해 줄 거예요.",
    "ask_recommend": "제이크에게 상황을 하나 추천받아 볼까요?",
    # the situation screen's steps (spec situation-topics 2, 6). ask_situation stays for an app from before topics.
    "ask_topic": "어떤 주제로 연습해 볼까요?",
    "ask_how": "어떻게 상황을 정할까요?",
    "ask_pick": "해 보고 싶은 상황을 골라 주세요.",
    "ask_describe": "어떤 상황인지 말하거나 써 주세요.",
    "closing_retry": "대화 끝! 수고했어요. 고칠 것이 남았던 대사를 다시 해 볼까요?",
    "closing_clean": "대화 끝! 수고했어요. 오늘 정말 잘했어요.",
    # no line was said inside the roleplay (all skipped, or only words to teacher Ryan): nothing heard to praise
    # (spec record-cancel-skip 3)
    "closing_plain": "대화 끝! 수고했어요.",
    "no_speech": "잘 안 들렸어요. 한 번 더 말해 줄래요?",
    "retry_offscript": "이번에는 대사를 그대로 따라 말해 볼까요?",
    "claude_down": "지금은 제가 대답할 수 없어요. 맥의 인터넷 연결을 확인해 주세요.",
    "too_long": "녹음이 너무 길어요. 한 문장씩 짧게 말해 볼까요?",
}
