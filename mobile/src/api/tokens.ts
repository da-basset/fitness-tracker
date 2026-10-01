import * as SecureStore from 'expo-secure-store';

const REFRESH_KEY = 'auth.refresh';

// The access token is short-lived (15 min) so it only lives in memory; the
// refresh token survives restarts in the keychain.
let accessToken: string | null = null;

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getRefreshToken() {
  return SecureStore.getItemAsync(REFRESH_KEY);
}

export async function setRefreshToken(token: string | null) {
  if (token) {
    await SecureStore.setItemAsync(REFRESH_KEY, token, {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
  } else {
    await SecureStore.deleteItemAsync(REFRESH_KEY);
  }
}

export async function clearTokens() {
  accessToken = null;
  await setRefreshToken(null);
}
