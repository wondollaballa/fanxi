import { LauncherError } from "./api";

/** The server refuses a purchase when the 80-slot normal inventory has no room. */
export function isInventoryFull(error: unknown): boolean {
  return error instanceof LauncherError && error.code === "inventory_full";
}

/** Short form for the toast that accompanies the blocking dialog. */
export const INVENTORY_FULL_TOAST =
  "Inventory full — free a slot in game with //storage organize or //bags, then retry.";

/** Long form for the page banner when the failure has no purchase card to return to. */
export const INVENTORY_FULL_MESSAGE =
  "Inventory full — every purchase goes into the normal 80-slot inventory. " +
  "Free a slot in game (press Enter, run //storage organize, or open //bags and move one " +
  "item out), then try again. No gil was charged.";
