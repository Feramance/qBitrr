/**
 * Copy text to clipboard
 * @param text Text to copy
 * @returns Promise that resolves to true if successful, false otherwise
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      // Modern async clipboard API
      await navigator.clipboard.writeText(text);
      return true;
    } else {
      // Fallback for older browsers or non-secure contexts
      const textArea = document.createElement("textarea");
      textArea.value = text;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      try {
        document.execCommand("copy");
        textArea.remove();
        return true;
      } catch (err) {
        console.error("Fallback: Could not copy text", err);
        textArea.remove();
        return false;
      }
    }
  } catch (err) {
    console.error("Failed to copy text", err);
    return false;
  }
}
