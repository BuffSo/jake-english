// Plays sounds one after another on a single player. Ryan's feedback arrives sentence by sentence,
// so sentences are queued and played in order.
import { createAudioPlayer, type AudioSource } from "expo-audio";

const STUCK_MS = 30_000; // a sound that never finishes (bad file, lost connection) must not block the queue

// a sound, or a stretch of quiet between two (the first and this run's recording, spec review-practice 4). `tag` names
// the button that asked for it, whose 🔊 bounces while it plays (spec play-button-feedback 1); sounds the app plays by
// itself (Ryan, a practice's model) have none.
type Item = ({ src: AudioSource } | { pause: number }) & { tag?: string };

// the tag of what plays now and since when (ms), for the button's 🔊 and its tap rule (`playTap`)
export type NowTag = { tag: string | null; since: number };

export class SoundQueue {
  private player = createAudioPlayer(null);
  private queue: Item[] = [];
  private playing = false;
  // a sound plays now, not a pause between two: only a sound's progress may hold the watchdog off
  private sounding = false;
  private idle: (() => void)[] = [];
  private watchdog: ReturnType<typeof setTimeout> | undefined;
  // screens that wait for quiet before offering a button that would cut a speaker off (spec roleplay-practice 9)
  private listeners = new Set<(playing: boolean) => void>();
  private now: NowTag = { tag: null, since: 0 };
  private tagListeners = new Set<(now: NowTag) => void>();

  constructor() {
    this.player.addListener("playbackStatusUpdate", (status) => {
      // still playing: not stuck, however long it is. A recording runs up to 55 s, and at 30 s the watchdog passed it
      // while it played on, so its 🔊 stopped bouncing (phone check, spec play-button-feedback 1)
      if (status.playing && this.sounding && !status.didJustFinish) this.arm();
      if (status.didJustFinish) this.next();
    });
  }

  enqueue(src: AudioSource, tag?: string): void {
    this.add({ src, tag });
  }

  // quiet for `ms` before what is queued next; it counts as playing, so nothing cuts in, and clear() drops it. A pair
  // gives its pause the same tag, so the 🔊 keeps bouncing through it.
  enqueuePause(ms: number, tag?: string): void {
    this.add({ pause: ms, tag });
  }

  nowTag(): NowTag {
    return this.now;
  }

  // called only when the tag changes; the returned function stops it
  subscribeTag(cb: (now: NowTag) => void): () => void {
    this.tagListeners.add(cb);
    return () => {
      this.tagListeners.delete(cb);
    };
  }

  private setTag(tag: string | null): void {
    if (this.now.tag === tag) return;
    this.now = { tag, since: tag === null ? 0 : Date.now() };
    this.tagListeners.forEach((cb) => cb(this.now));
  }

  private add(item: Item): void {
    this.queue.push(item);
    if (!this.playing) this.next();
  }

  clear(): void {
    this.queue = [];
    this.idle = [];
    clearTimeout(this.watchdog);
    this.player.pause();
    this.sounding = false;
    this.setPlaying(false);
    this.setTag(null);
  }

  onIdle(cb: () => void): void {
    if (this.playing) this.idle.push(cb);
    else cb();
  }

  isPlaying(): boolean {
    return this.playing;
  }

  // called only when playing turns on or off; the returned function stops it
  subscribe(cb: (playing: boolean) => void): () => void {
    this.listeners.add(cb);
    return () => {
      this.listeners.delete(cb);
    };
  }

  private setPlaying(v: boolean): void {
    if (this.playing === v) return;
    this.playing = v;
    this.listeners.forEach((cb) => cb(v));
  }

  // a sound that never reports its end, nor any progress, is passed after STUCK_MS
  private arm(): void {
    clearTimeout(this.watchdog);
    this.watchdog = setTimeout(() => this.next(), STUCK_MS);
  }

  private next(): void {
    clearTimeout(this.watchdog);
    const item = this.queue.shift();
    this.sounding = item !== undefined && "src" in item;
    this.setTag(item?.tag ?? null);
    if (!item) {
      this.setPlaying(false);
      const cbs = this.idle;
      this.idle = [];
      cbs.forEach((cb) => cb());
      return;
    }
    this.setPlaying(true);
    if ("pause" in item) {
      this.watchdog = setTimeout(() => this.next(), item.pause);
      return;
    }
    this.player.replace(item.src);
    this.player.play();
    this.arm();
  }
}
