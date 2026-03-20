export type LineDecision = 'accept' | 'reject';

export type DiffLineKind = 'equal' | 'add' | 'delete';

export type DiffLine = {
  id: string | null;
  kind: DiffLineKind;
  text: string;
  oldLineNumber: number | null;
  newLineNumber: number | null;
};

export type LineChange = {
  id: string;
  kind: 'add' | 'delete';
  text: string;
  oldLineNumber: number | null;
  newLineNumber: number | null;
};

export type LineDiffResult = {
  oldText: string;
  newText: string;
  oldHasTrailingNewline: boolean;
  newHasTrailingNewline: boolean;
  lines: DiffLine[];
  changes: LineChange[];
};

const MAX_DP_CELLS = 120_000;

type SplitLinesResult = {
  lines: string[];
  hasTrailingNewline: boolean;
};

function splitLines(text: string): SplitLinesResult {
  if (!text) return { lines: [], hasTrailingNewline: false };
  const hasTrailingNewline = text.endsWith('\n');
  const raw = text.split('\n');
  if (hasTrailingNewline) raw.pop();
  return { lines: raw, hasTrailingNewline };
}

function buildOpsWithLcs(oldLines: string[], newLines: string[]): DiffLineKind[] {
  const n = oldLines.length;
  const m = newLines.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array<number>(m + 1).fill(0));

  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  const ops: DiffLineKind[] = [];
  let i = 0;
  let j = 0;

  while (i < n && j < m) {
    if (oldLines[i] === newLines[j]) {
      ops.push('equal');
      i++;
      j++;
      continue;
    }
    if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push('delete');
      i++;
    } else {
      ops.push('add');
      j++;
    }
  }

  while (i < n) {
    ops.push('delete');
    i++;
  }
  while (j < m) {
    ops.push('add');
    j++;
  }

  return ops;
}

function buildOpsFallback(oldLines: string[], newLines: string[]): DiffLineKind[] {
  const ops: DiffLineKind[] = [];
  let i = 0;
  let j = 0;
  while (i < oldLines.length || j < newLines.length) {
    const hasOld = i < oldLines.length;
    const hasNew = j < newLines.length;
    if (hasOld && hasNew && oldLines[i] === newLines[j]) {
      ops.push('equal');
      i++;
      j++;
      continue;
    }
    if (hasOld) {
      ops.push('delete');
      i++;
    }
    if (hasNew) {
      ops.push('add');
      j++;
    }
  }
  return ops;
}

export function buildLineDiff(oldContent: string | null, newContent: string | null): LineDiffResult {
  const oldText = oldContent ?? '';
  const newText = newContent ?? '';
  const oldSplit = splitLines(oldText);
  const newSplit = splitLines(newText);

  const cells = (oldSplit.lines.length + 1) * (newSplit.lines.length + 1);
  const ops = cells <= MAX_DP_CELLS
    ? buildOpsWithLcs(oldSplit.lines, newSplit.lines)
    : buildOpsFallback(oldSplit.lines, newSplit.lines);

  const lines: DiffLine[] = [];
  const changes: LineChange[] = [];

  let oldIdx = 0;
  let newIdx = 0;
  let changeNo = 1;

  for (const kind of ops) {
    if (kind === 'equal') {
      const text = oldSplit.lines[oldIdx] ?? '';
      lines.push({
        id: null,
        kind,
        text,
        oldLineNumber: oldIdx + 1,
        newLineNumber: newIdx + 1,
      });
      oldIdx++;
      newIdx++;
      continue;
    }

    if (kind === 'delete') {
      const id = `chg-${changeNo++}`;
      const text = oldSplit.lines[oldIdx] ?? '';
      const line: DiffLine = {
        id,
        kind,
        text,
        oldLineNumber: oldIdx + 1,
        newLineNumber: null,
      };
      lines.push(line);
      changes.push({
        id,
        kind,
        text,
        oldLineNumber: line.oldLineNumber,
        newLineNumber: null,
      });
      oldIdx++;
      continue;
    }

    const id = `chg-${changeNo++}`;
    const text = newSplit.lines[newIdx] ?? '';
    const line: DiffLine = {
      id,
      kind: 'add',
      text,
      oldLineNumber: null,
      newLineNumber: newIdx + 1,
    };
    lines.push(line);
    changes.push({
      id,
      kind: 'add',
      text,
      oldLineNumber: null,
      newLineNumber: line.newLineNumber,
    });
    newIdx++;
  }

  return {
    oldText,
    newText,
    oldHasTrailingNewline: oldSplit.hasTrailingNewline,
    newHasTrailingNewline: newSplit.hasTrailingNewline,
    lines,
    changes,
  };
}

export function areAllChangesResolved(diff: LineDiffResult, decisions: Record<string, LineDecision>): boolean {
  if (diff.changes.length === 0) return true;
  return diff.changes.every((c) => decisions[c.id] === 'accept' || decisions[c.id] === 'reject');
}

export function summarizeDecisions(
  diff: LineDiffResult,
  decisions: Record<string, LineDecision>,
): { accepted: number; rejected: number } {
  let accepted = 0;
  let rejected = 0;
  for (const change of diff.changes) {
    const decision = decisions[change.id];
    if (decision === 'accept') accepted++;
    if (decision === 'reject') rejected++;
  }
  return { accepted, rejected };
}

export function buildResolvedContent(
  diff: LineDiffResult,
  decisions: Record<string, LineDecision>,
): string {
  if (diff.changes.length === 0) return diff.newText;

  const { accepted, rejected } = summarizeDecisions(diff, decisions);
  if (accepted === diff.changes.length && rejected === 0) return diff.newText;
  if (rejected === diff.changes.length && accepted === 0) return diff.oldText;

  const output: string[] = [];
  for (const line of diff.lines) {
    if (line.kind === 'equal') {
      output.push(line.text);
      continue;
    }
    if (!line.id) continue;
    const decision = decisions[line.id];
    if (line.kind === 'add' && decision === 'accept') output.push(line.text);
    if (line.kind === 'delete' && decision === 'reject') output.push(line.text);
  }

  const text = output.join('\n');
  const keepTrailingNewline = diff.newHasTrailingNewline || diff.oldHasTrailingNewline;
  if (keepTrailingNewline && text.length > 0) return `${text}\n`;
  return text;
}
