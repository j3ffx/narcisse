// Narcisse's own window (the browser's `--app=` window) has no tabs and no back button: a link
// that opened in it would strand the user on the site. That window is opened with `?fenetre=1`;
// it remembers it for its lifetime, and hands every link leaving Narcisse to the server, which
// opens it in the user's own browser. In an ordinary tab, links behave as usual.
import { post } from './api';

const FLAG = 'narcisse-fenetre';

/** Whether this page is Narcisse's own window (and drops the marker from the address). */
export function isAppWindow(): boolean {
  const url = new URL(window.location.href);
  if (url.searchParams.has('fenetre')) {
    try {
      sessionStorage.setItem(FLAG, '1');
    } catch {
      // Storage refused: this page load still knows, from the address.
    }
    url.searchParams.delete('fenetre');
    window.history.replaceState(window.history.state, '', url);
    return true;
  }
  try {
    return sessionStorage.getItem(FLAG) === '1';
  } catch {
    return false;
  }
}

/** The address a link leaves Narcisse for, or null when it stays (or isn't a web page). */
export function leavesNarcisse(href: string, origin: string): string | null {
  const url = new URL(href, origin);
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null; // mailto: and the like
  return url.origin === origin ? null : url.href;
}

export function sendExternalLinksToTheBrowser(): void {
  if (!isAppWindow()) return;
  document.addEventListener(
    'click',
    (event) => {
      if (event.defaultPrevented || event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
      if (!(link instanceof HTMLAnchorElement)) return;
      const url = leavesNarcisse(link.href, window.location.origin);
      if (!url) return;
      event.preventDefault();
      post('/open-external', { url }).catch(() => window.open(url, '_blank', 'noopener'));
    },
    true,
  );
}
