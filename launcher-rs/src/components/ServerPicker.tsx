import { useState } from "react";

import { findPreset, SERVER_PRESETS } from "../lib/servers";
import { Select, TextInput } from "./ui";

/**
 * The server list, plus the free-text field for anyone running their own.
 *
 * The select shows the preset a value matches; picking "Custom URL…" reveals the input
 * without discarding what was there, so switching from a preset to a private server is one
 * edit rather than a retype.
 */
export function ServerPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const preset = findPreset(value);
  const [custom, setCustom] = useState(false);
  const showCustom = custom || !preset;

  return (
    <div className="server-picker">
      <Select
        value={preset?.url ?? "__custom__"}
        onChange={(event) => {
          const next = event.target.value;
          if (next === "__custom__") {
            setCustom(true);
            return;
          }
          setCustom(false);
          onChange(next);
        }}
      >
        {SERVER_PRESETS.map((server) => (
          <option key={server.id} value={server.url}>
            {server.label}
          </option>
        ))}
        <option value="__custom__">Custom URL…</option>
      </Select>
      {showCustom && (
        <TextInput
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="https://fanxi.example.com"
          spellCheck={false}
          autoCapitalize="off"
        />
      )}
    </div>
  );
}
