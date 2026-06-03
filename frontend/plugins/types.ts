/**
 * Shared contract that every plugin config panel component must satisfy.
 *
 * The admin-plugins-tab fetches plugin data from the backend and passes it
 * down through this interface.  Plugin components must NOT talk to the API
 * directly — all persistence goes through onChange/onTest.
 */
export interface PluginConfigProps {
  /** Merged config (defaults overridden by saved values). */
  config: Record<string, unknown>;
  /** Called whenever the user changes a config field. Pass the full updated config. */
  onChange: (next: Record<string, unknown>) => void;
  /** Called when the user clicks "Send test". Resolves on success, throws on failure. */
  onTest: () => Promise<void>;
  /** True while a save or test request is in-flight. */
  saving: boolean;
  /**
   * Distinct custom_fields keys seen in recent notifications.
   * Plugin config UIs can use this to populate datalists / dropdowns.
   */
  availableCustomFields: string[];
}
