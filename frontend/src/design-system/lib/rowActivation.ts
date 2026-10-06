/** Canonical detection of independent controls inside an activatable table row. */

const ROW_INTERACTIVE_SELECTOR = [
  "a",
  "button",
  "input",
  "select",
  "textarea",
  "option",
  "summary",
  "label",
  "[role='button']",
  "[role='link']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='option']",
  "[role='checkbox']",
  "[role='radio']",
  "[role='switch']",
  "[role='combobox']",
  "[role='listbox']",
  "[role='menu']",
  "[role='menubar']",
  "[role='tab']",
  "[role='slider']",
  "[role='spinbutton']",
  "[role='searchbox']",
  "[role='textbox']",
  "[contenteditable='true']",
  "[data-ds-row-interactive]",
  ".ds-icon-hit",
].join(",");

const DISABLED_INTERACTIVE_SELECTOR = [
  "button:disabled",
  "input:disabled",
  "select:disabled",
  "textarea:disabled",
  "option:disabled",
  "[disabled]",
  "[aria-disabled='true']",
].join(",");

export function isInteractiveRowTarget(
  target: EventTarget | null,
  row: EventTarget,
): boolean {
  if (!(row instanceof Element)) return false;
  // Portaled overlays (menus, popovers, dialogs) bubble React events through the row.
  if (target instanceof Node && !row.contains(target)) return true;
  if (!(target instanceof Element)) return false;
  const found = target.closest(ROW_INTERACTIVE_SELECTOR);
  return Boolean(found && row.contains(found) && found !== row);
}

export function hasNonCollapsedTextSelection(row: EventTarget): boolean {
  if (!(row instanceof Element)) return false;
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.toString().trim()) {
    return false;
  }
  if (selection.rangeCount === 0) return false;
  return row.contains(selection.getRangeAt(0).commonAncestorContainer);
}

export function isDisabledInteractiveAtPoint(
  event: Pick<MouseEvent, "clientX" | "clientY">,
  row: EventTarget,
): boolean {
  if (!(row instanceof Element)) return false;
  const stack = document.elementsFromPoint(event.clientX, event.clientY);
  for (const el of stack) {
    if (!row.contains(el)) break;
    const disabled = el.closest(DISABLED_INTERACTIVE_SELECTOR);
    if (disabled && row.contains(disabled) && disabled !== row) return true;
  }
  return false;
}

export function shouldIgnoreRowActivation(
  event: { target: EventTarget | null; currentTarget: EventTarget },
  pointer?: Pick<MouseEvent, "clientX" | "clientY">,
): boolean {
  if (isInteractiveRowTarget(event.target, event.currentTarget)) return true;
  if (hasNonCollapsedTextSelection(event.currentTarget)) return true;
  if (pointer && isDisabledInteractiveAtPoint(pointer, event.currentTarget)) {
    return true;
  }
  return false;
}
