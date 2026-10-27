/** Hands a file the page made to the browser's downloads. */
export function saveFile(name: string, content: BlobPart, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.style.display = 'none';
  document.body.append(link);
  link.click();
  link.remove();
  // The download has started from the blob: it can go once the click is handled.
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
