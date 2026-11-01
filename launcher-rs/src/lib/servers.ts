/** The servers the launcher offers in its picker.
 *
 * Add an entry here to ship a new hosted server with the launcher. `url` is the base the
 * launcher appends `/api/v1` to; anyone can still type their own under "Custom URL".
 */
export interface ServerPreset {
  id: string;
  label: string;
  url: string;
}

export const SERVER_PRESETS: ServerPreset[] = [
  { id: "hosted", label: "Fanxi — hosted (US)", url: "https://172.236.103.193.sslip.io" },
  { id: "local", label: "Local (this machine)", url: "http://127.0.0.1:8080" },
];

/** The preset a URL matches, ignoring trailing slashes. */
export function findPreset(url: string): ServerPreset | undefined {
  const normalized = url.trim().replace(/\/+$/, "");
  return SERVER_PRESETS.find((preset) => preset.url === normalized);
}
