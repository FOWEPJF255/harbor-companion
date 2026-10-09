# Phone and desktop connection

## Delivery surfaces

- Desktop: browser app, with optional PWA installation where supported.
- Android: Capacitor native container with bundled UI. The generated project is buildable after Android/JDK tooling or the repository's cloud build is available; an Android project is not an APK by itself.
- iOS: reusable UI and Capacitor configuration only. Generating/signing an iOS app needs the documented macOS/Xcode workflow; no iOS binary is produced on this Windows machine.

See [app delivery](app-delivery.md) for packaging commands, platform requirements, and current evidence.

## Understand the address

`127.0.0.1:8765` on a phone refers to the phone, not the development PC. A native app needs a reachable HTTPS backend. The backend remains loopback-only by default. Responsive UI support does not imply a deployed server or cross-device identity/synchronization.

`VITE_API_BASE_URL` is a **public backend address** bundled into an optional mobile build. It is not a model endpoint/key. If unset, a native user can configure the address in “我的”. No tokens or model keys are compiled into the APK.

The connection form supports a backend address and a **demo access code**. They remain in sessionStorage for the current app/browser session. Closing the session may require entering the code again. Administrator tokens are held separately in memory. Model credentials remain server-side in `.env`.

In `local_demo`, this device keeps partitioned anonymous session handles. In `accounts`, the server lists sessions owned by the authenticated user with bounded pagination; the UI restores the same user's sessions on another device after login. These profiles are distinct. Cross-device behavior still requires a reachable shared backend and physical-device verification; it is not an offline synchronization service.

## Controlled HTTPS demo deployment

1. Complete the remaining [production-readiness gates](enterprise-readiness.md), initialize the separate administrator locally, and provision the owner's chosen adult user accounts. Set `HARBOR_AUTH_MODE=accounts`; remote hosts refuse the anonymous profile.
2. Put the backend behind a correctly configured HTTPS endpoint. Preserve the original Host, and do not expose an arbitrary reverse-proxy admin bootstrap.
3. Set exact backend hostnames in `HARBOR_ALLOWED_HOSTS` and exact HTTPS frontend origins in `HARBOR_ALLOWED_ORIGINS` (comma-separated, no paths or wildcards).
4. Set `HARBOR_CLIENT_TOKEN` to a long private random demo access code (at least 32 characters). Additional hosts without such a code make server startup fail closed.
5. Android's `https://localhost` and iOS's `capacitor://localhost` origins are recognized by the backend. They do not waive the access-code or administrator checks.
6. Enter the backend address and demo code on the phone, then sign in to the ordinary user account. Keep the actual model API key out of the app. Administrator login is a separate interface and token.
7. Use synthetic conversations until a deliberate consent and retention workflow is ready.

This is limited account-based demonstration access with one administrator and an additional shared access code. It is not organization tenancy, distributed abuse protection, or an already-deployed service. A public launch still needs data-lifecycle, ingress, recovery, load and operational acceptance.

## Offline behavior

The PWA can cache only public presentation assets. Network navigation uses the current online page or a dedicated offline explanation. API calls are never cached; offline messages are not generated or silently queued. Native apps already bundle the UI and require network access to the backend/model.
