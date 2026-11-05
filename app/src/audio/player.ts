// Plays sounds one after another on a single player. Ryan's feedback arrives sentence by sentence,
// so sentences are queued and played in order.
import { createAudioPlayer, type AudioSource } from "expo-audio";

const STUCK_MS = 30_000; // a sound that never finishes (bad file, lost connection) must not block the queue

export class SoundQueue {
  private player = createAudioPlayer(null);
  private queue: AudioSource[] = [];
  private playing = false;
  private idle: (() => void)[] = [];
  private watchdog: ReturnType<typeof setTimeout> | undefined;

  constructor() {
    this.player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) this.next();
    });
  }

  enqueue(src: AudioSource): void {
    this.queue.push(src);
    if (!this.playing) this.next();
  }

  clear(): void {
    this.queue = [];
    this.idle = [];
    clearTimeout(this.watchdog);
    this.player.pause();
    this.playing = false;
  }

  onIdle(cb: () => void): void {
    if (this.playing) this.idle.push(cb);
    else cb();
  }

  private next(): void {
    clearTimeout(this.watchdog);
    const src = this.queue.shift();
    if (!src) {
      this.playing = false;
      const cbs = this.idle;
      this.idle = [];
      cbs.forEach((cb) => cb());
      return;
    }
    this.playing = true;
    this.player.replace(src);
    this.player.play();
    this.watchdog = setTimeout(() => this.next(), STUCK_MS);
  }
}
