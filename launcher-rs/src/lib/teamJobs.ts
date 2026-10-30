import type { Character, InstanceView, SessionView, TeamView } from "../types";
import {
  characterJobPair,
  inWorld,
  instanceJobPair,
  orphanedSession,
  type JobPair,
} from "./format";

export type TeamJobStatus =
  | "in-game"
  | "sleeping"
  | "orphaned"
  | "logged-out"
  | "offline"
  | "suspended"
  | "no-character";

/** One team slot (the main account or a box) with the jobs it brings to the party. */
export interface TeamJobEntry {
  key: string;
  account: string;
  name: string;
  /** "Main" or "Box 2" — the same label the tenant bar and Team page use. */
  slotLabel: string;
  kind: "main" | "sub";
  character: Character | null;
  characterId: number | null;
  instance: InstanceView | null;
  job: JobPair;
  /** True only when the server and the client agree this character is in the world. */
  live: boolean;
  status: TeamJobStatus;
  statusLabel: string;
  isTenant: boolean;
}

const MAX_JOB = 22;

function sameCharacter(
  left: number | null | undefined,
  right: number | null | undefined,
): boolean {
  if (left === null || left === undefined) return false;
  if (right === null || right === undefined) return false;
  return Number(left) === Number(right);
}

function knownJob(value?: number): number {
  const job = Number(value ?? 0);
  return Number.isInteger(job) && job >= 1 && job <= MAX_JOB ? job : 0;
}

interface SlotInput {
  key: string;
  account: string;
  name: string;
  slotLabel: string;
  kind: "main" | "sub";
  character: Character | null;
  instance: InstanceView | null;
  suspended: boolean;
  isTenant: boolean;
}

function slotEntry(input: SlotInput): TeamJobEntry {
  const { character, instance } = input;
  const matched = instance !== null && sameCharacter(instance.character?.id, character?.id);
  const slotInstance = matched ? instance : null;
  // The live control state is the truth while the client runs; the saved row covers offline
  // boxes and older addons that do not report a support job yet.
  const job = slotInstance ? instanceJobPair(slotInstance) : characterJobPair(character);
  const live = Boolean(slotInstance && inWorld(slotInstance));

  let status: TeamJobStatus;
  let statusLabel: string;
  if (!character) {
    status = "no-character";
    statusLabel = "No character";
  } else if (input.suspended) {
    status = "suspended";
    statusLabel = "Suspended";
  } else if (slotInstance && live) {
    status = "in-game";
    statusLabel = slotInstance.headless ? "In game · headless" : "In game";
  } else if (slotInstance?.sleeping) {
    status = "sleeping";
    statusLabel = slotInstance.headless ? "Sleeping · headless" : "Sleeping";
  } else if (orphanedSession(slotInstance)) {
    status = "orphaned";
    statusLabel = "Orphaned session";
  } else if (slotInstance) {
    status = "logged-out";
    statusLabel = "Logged out";
  } else {
    status = "offline";
    statusLabel = "Offline";
  }

  return {
    ...input,
    characterId: character ? Number(character.id) : null,
    instance: slotInstance,
    job,
    live,
    status,
    statusLabel,
  };
}

/**
 * Every slot on the team — the main account's active character and each sub-account box — with
 * the main/support job it is on. Slots are stable while boxes are added, removed or suspended,
 * so the Team and Control pages can show the whole party's jobs in one list.
 */
export function buildTeamJobEntries({
  session,
  team,
  activeCharacter,
  instances,
  tenantCharacterId,
}: {
  session: SessionView;
  team: TeamView | null;
  activeCharacter: Character | null;
  instances: InstanceView[];
  tenantCharacterId: number | null;
}): TeamJobEntry[] {
  const runningByAccount = new Map<string, InstanceView>();
  for (const instance of instances) {
    if (!instance.alive) continue;
    const key = instance.account.toLowerCase();
    if (!runningByAccount.has(key)) runningByAccount.set(key, instance);
  }

  const mainAccount = session.account.username;
  const entries: TeamJobEntry[] = [
    slotEntry({
      key: `main-${mainAccount}`,
      account: mainAccount,
      name: activeCharacter?.name ?? "No character",
      slotLabel: "Main",
      kind: "main",
      character: activeCharacter,
      instance: runningByAccount.get(mainAccount.toLowerCase()) ?? null,
      suspended: false,
      isTenant: sameCharacter(tenantCharacterId, activeCharacter?.id),
    }),
  ];

  for (const [index, sub] of (team?.subs ?? []).entries()) {
    entries.push(
      slotEntry({
        key: `sub-${sub.id}`,
        account: sub.username,
        name: sub.character?.name ?? "No character",
        slotLabel: `Box ${index + 2}`,
        kind: "sub",
        character: sub.character,
        instance: runningByAccount.get(sub.username.toLowerCase()) ?? null,
        suspended: sub.status !== "active",
        isTenant: sameCharacter(tenantCharacterId, sub.character?.id),
      }),
    );
  }

  return entries;
}

/** The distinct jobs the team covers, with how many members bring each one. */
export function coveredTeamJobs(entries: TeamJobEntry[]): Array<{ job: number; count: number }> {
  const counts = new Map<number, number>();
  for (const entry of entries) {
    for (const value of [entry.job.main, entry.job.sub]) {
      const job = knownJob(value);
      if (!job) continue;
      counts.set(job, (counts.get(job) ?? 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort(([left], [right]) => left - right)
    .map(([job, count]) => ({ job, count }));
}
