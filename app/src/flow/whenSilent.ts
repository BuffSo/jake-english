// Holds a result until the sound queue has finished what it is playing. The next screen clears the
// queue to play its own line, so moving on early cuts the current speaker off (2026-11-05, Jake's
// recommended situation was cut when the script came back first). A failure is not held.
type Idle = { onIdle(cb: () => void): void };

export async function whenSilent<T>(sounds: Idle, work: Promise<T>): Promise<T> {
  const silent = new Promise<void>((resolve) => sounds.onIdle(resolve));
  const [value] = await Promise.all([work, silent]);
  return value;
}
