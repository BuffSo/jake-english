// Splits a stream of newline-delimited JSON into objects, across chunk boundaries.
export class NdjsonSplitter {
  private buf = "";

  push(chunk: string): unknown[] {
    this.buf += chunk;
    const lines = this.buf.split("\n");
    this.buf = lines.pop() ?? "";
    return lines.filter((l) => l.trim() !== "").map((l) => JSON.parse(l));
  }

  flush(): unknown[] {
    const rest = this.buf.trim();
    this.buf = "";
    return rest ? [JSON.parse(rest)] : [];
  }
}
