import { useEffect } from "react";

/**
 * Warn before leaving a form with unsaved edits.
 *
 * Covers a browser reload, a tab close and a back navigation. It cannot cover
 * everything a single-page router does, so screens that navigate away
 * themselves still confirm before doing so.
 */
export function useUnsavedChanges(dirty: boolean): void {
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      // Browsers show their own wording; assigning returnValue is what triggers it.
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);
}

/** Ask before discarding edits when the screen navigates away on its own. */
export function confirmDiscard(dirty: boolean): boolean {
  if (!dirty) return true;
  return window.confirm("You have unsaved changes. Leave this page and discard them?");
}
