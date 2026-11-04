import { AlertTriangle } from "lucide-react";
import { Button, Modal } from "./ui";

/**
 * The blocking inventory-full error.  A purchase only uses the normal 80-slot
 * inventory, so the player has to free a slot in game before retrying here.
 */
export function InventoryFullDialog({
  itemName,
  onRetry,
  retrying = false,
  onClose,
}: {
  itemName?: string;
  onRetry?: () => void;
  retrying?: boolean;
  onClose: () => void;
}) {
  return (
    <Modal
      title="Inventory full"
      subtitle={
        itemName
          ? `${itemName} was not purchased — no gil was charged.`
          : "Nothing was purchased — no gil was charged."
      }
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          {onRetry && (
            <Button onClick={onRetry} loading={retrying}>
              Retry purchase
            </Button>
          )}
        </>
      }
    >
      <div className="inventory-full-dialog">
        <div className="inventory-full-callout">
          <AlertTriangle size={18} />
          <div>
            <strong>Free a slot, then retry.</strong>
            <p>
              Every purchase goes into the normal 80-slot inventory, and all 80 slots are
              taken. Your gil was not charged.
            </p>
          </div>
        </div>

        <p>In game, press <kbd>Enter</kbd> and run one of these:</p>
        <ul>
          <li>
            <code>//storage organize</code> — stows the current job&apos;s loose gear in the
            Mog Wardrobes.
          </li>
          <li>
            <code>//bags</code> — opens the Magic Bag HUD, where you can move one item out of
            the inventory.
          </li>
        </ul>
        <p>
          Then come back here and press <strong>Retry purchase</strong>.
        </p>
      </div>
    </Modal>
  );
}
