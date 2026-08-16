/** Browser-session credential storage.
 *
 * The token is deliberately not a Vite environment variable: those values are
 * embedded into the public GitHub Pages bundle.  Users enter it after opening
 * the app and it disappears when the browser session ends.
 */
const ACCESS_TOKEN_KEY = 'ai-chatbot.access-token';

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  sessionStorage.setItem(ACCESS_TOKEN_KEY, token.trim());
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}

export function accessHeaders(): HeadersInit {
  const token = getAccessToken();
  return token ? { 'X-API-Token': token } : {};
}
