import type { SessionView, TeamView, Tenant } from "../types";

/**
 * The tenant list is the player's whole team: every character owned by the main account, then
 * one entry per sub-account box. Characters are the unit because gear, data and warps are all
 * per character, and a box has exactly one character. The order matches the Team page so the
 * tenant bar reads left to right like the roster.
 */
export function buildTenants(
  session: SessionView | null,
  team: TeamView | null,
): Tenant[] {
  if (!session) return [];
  const output: Tenant[] = [];
  const seen = new Set<number>();

  const mainAccount = session.account.username;
  for (const character of session.characters) {
    const id = Number(character.id);
    if (!Number.isFinite(id) || seen.has(id)) continue;
    seen.add(id);
    output.push({
      character,
      account: mainAccount,
      kind: "main",
      label: "Main",
      sub: null,
    });
  }

  for (const [index, sub] of (team?.subs ?? []).entries()) {
    if (!sub.character) continue;
    const id = Number(sub.character.id);
    if (!Number.isFinite(id) || seen.has(id)) continue;
    seen.add(id);
    output.push({
      character: sub.character,
      account: sub.username,
      kind: "sub",
      label: `Box ${index + 2}`,
      sub,
    });
  }

  return output;
}

/**
 * Resolve the tenant to show. A stored tenant wins while it still exists; otherwise the main
 * account's active character is the fallback, and finally the first character in the roster.
 * This keeps a stale `tenantCharacterId` (a deleted box, a different account) harmless.
 */
export function resolveTenant(
  tenants: Tenant[],
  storedId: number | null,
  activeId: number | null,
): Tenant | null {
  const wanted = (value: number | null | undefined) =>
    tenants.find((tenant) => Number(tenant.character.id) === Number(value)) ?? null;
  return wanted(storedId) ?? wanted(activeId) ?? tenants[0] ?? null;
}
