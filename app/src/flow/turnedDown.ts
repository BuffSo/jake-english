// Jake's suggestions the learner turned down with 「다른 걸로요」 on the situation screen (2026-11-06). They go
// with the next request so the same one does not come back. The server takes at most this many
// (server/je_server/app.py `Recommend`), so only the last ones are kept.
export const TURNED_DOWN_MAX = 10;

export function turnDown(list: readonly string[], text: string): string[] {
  return [...list.filter((t) => t !== text), text].slice(-TURNED_DOWN_MAX);
}
