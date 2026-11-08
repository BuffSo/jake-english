import { useCallback, useEffect, useMemo, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { api } from "../api";
import type { Home, Said } from "../api/types";
import type { SoundQueue } from "../audio/player";
import { createHomeLoad, leaveHome } from "../flow/homeActions";
import { homeLines, homeSounds } from "../flow/homeLines";
import { Button } from "../ui/Button";
import { ChoiceCard } from "../ui/ChoiceCard";
import { keepWords } from "../ui/keepWords";
import { RyanPortrait } from "../ui/RyanFace";
import { colors, top } from "../ui/theme";
import { ErrorText, messageOf, styles as common } from "./common";

type Props = {
  sounds: SoundQueue;
  home: Home | null;
  setHome: (h: Home) => void;
  onRoleplay: () => void;
  onTalk: () => void;
  onReview: () => void;
};

export function HomeScreen({ sounds, home, setHome, onRoleplay, onTalk, onReview }: Props) {
  const [error, setError] = useState<string | null>(null);
  // App keeps `home` for as long as the app runs, so having it when this screen opens means Ryan has greeted
  // already and the learner came back, whichever way. Kept as it was at opening: `home` arriving from `load`
  // below must not count as coming back. Coming back, `/home` is not asked again: the fixed lines and their
  // sound names stay the same while the server runs and across restarts.
  const [opened] = useState(home);
  const returning = opened !== null;

  const say = useCallback(
    (lines: Said[]) => {
      sounds.clear();
      for (const l of lines) sounds.enqueue(api.audioSource(l.audio));
    },
    [sounds],
  );

  // one `/home?tip=1` at a time: a double tap on 「다시 시도」 must not use up the day's tip (`createHomeLoad`)
  const ask = useMemo(
    () =>
      createHomeLoad(
        () => api.getHome(),
        (h) => {
          setHome(h);
          say(homeSounds(h, false));
        },
        (e) => setError(messageOf(e)),
      ),
    [say, setHome],
  );
  const load = useCallback(() => {
    setError(null);
    return ask();
  }, [ask]);

  useEffect(() => {
    if (opened) say(homeSounds(opened, true));
    else load();
  }, [opened, say, load]);

  return (
    <View style={styles.wrap}>
      {/* the front picture stays after Ryan has spoken (2026-11-05 user; it used to turn to the listening one) */}
      {home && <RyanPortrait source={api.imageSource(home.images.front)} style={styles.face} />}
      {home && (
        <>
          {homeLines(home, returning).map((l) => (
            <Text key={l.audio} style={[common.body, styles.say]}>
              {keepWords(l.text)}
            </Text>
          ))}
          {/* new or again: two new ones (with a script, without) and one again (spec review-practice 1,
              free-talk-design 1); each says what it does in a line, and the three colours tell them apart (spec
              review-screens 1) */}
          <View style={styles.choices}>
            <ChoiceCard
              icon="💬"
              title="대화 연습하기"
              line="상황을 정하면 라이언과 영어로 주고받아요"
              color={colors.primary}
              onPress={() => leaveHome(sounds, onRoleplay)}
            />
            <View style={styles.gap} />
            <ChoiceCard
              icon="☕"
              title="자유 대화"
              line="대본 없이 라이언과 영어로 이야기해요"
              color={colors.free}
              onPress={() => leaveHome(sounds, onTalk)}
            />
            <View style={styles.gap} />
            <ChoiceCard
              icon="↻"
              iconSize={34}
              title="복습하기"
              line="지난 상황과 모아 둔 문장을 다시 말해 봐요"
              color={colors.review}
              onPress={() => leaveHome(sounds, onReview)}
            />
          </View>
        </>
      )}
      {error && (
        <>
          <ErrorText text={error} />
          <Button label="다시 시도" onPress={load} />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  // from the top: centring left a wide gap above the picture (2026-11-05, user)
  wrap: { flex: 1, paddingTop: top, paddingHorizontal: 20, paddingBottom: 20, backgroundColor: colors.bg },
  // The picture gives way to the three cards (spec free-talk-design 1). At full width it is 400 high on a 360dp
  // phone, and the lines and cards under it ran past the bottom: on the phone 「복습하기」 showed only its name, under
  // the gesture bar (2026-11-08). Only the picture shrinks (`flexShrink`; the lines and cards keep their size), and
  // it keeps its 4:5 shape, so it gets narrower and stays in the middle, framed as before. Where all fits it is as
  // wide as before. `minHeight`: Ryan stays in sight on a very short screen.
  face: { marginBottom: 16, flexShrink: 1, minHeight: 120, alignSelf: "center" },
  say: { marginBottom: 8 },
  choices: { marginTop: 14 },
  gap: { height: 12 },
});
