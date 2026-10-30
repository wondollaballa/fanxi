import { useEffect, useState } from "react";
import { Package } from "lucide-react";

/** BG Wiki stores each item's 32x32 icon next to its page, as <name>_icon.png.
 * Special:FilePath resolves the file name without us having to reproduce the
 * wiki's MD5 directory split. */
export function bgwikiIcon(name: string): string {
  const file = `${name.trim().replace(/\s+/g, "_")}_icon.png`;
  return `https://www.bg-wiki.com/ffxi/Special:FilePath/${encodeURIComponent(file)}`;
}

/** The item's BG Wiki icon, falling back to a package glyph when the wiki has no
 * file (many non-equipment items do not have an icon page). */
export function ItemIcon({ name, size = 32 }: { name: string; size?: number }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setFailed(false);
  }, [name]);
  if (failed) {
    return (
      <span
        className="armory-art armory-art-empty"
        style={{ width: size, height: size }}
        aria-hidden="true"
      >
        <Package size={Math.max(14, Math.round(size * 0.45))} />
      </span>
    );
  }
  return (
    <img
      className="armory-art"
      src={bgwikiIcon(name)}
      width={size}
      height={size}
      alt=""
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
    />
  );
}
