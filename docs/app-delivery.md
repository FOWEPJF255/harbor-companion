# App delivery

## Product decision

Harbor shares a React interface across a desktop browser, a phone browser, and a Capacitor mobile container. The Android delivery uses a real Android application project with bundled assets and application ID `com.harborcompanion.app`. It is a hybrid APP, not an implementation in Kotlin or Swift.

A browser-installable PWA is a convenient secondary entry. It is not presented as an already-built native application. Recruiters asking for an APP should receive an installable APK and a phone demonstration once that artifact is actually built and checked.

## Current delivery boundary

| Deliverable | Current state | Required next step |
| --- | --- | --- |
| Responsive React interface | Shared frontend source | Continue device-specific interaction review |
| PWA manifest, original icons, installation guidance | Source implemented | Serve over HTTPS and check on actual supported devices |
| Public-asset service worker and offline explanation | Source implemented | Browser device review; no offline chat |
| Capacitor Android project | Generated with Capacitor 8.5.3; cloud compilation succeeded | Reachable HTTPS backend and phone review |
| Android APK | **v0.5 debug APK produced, downloaded and hash checked** by [cloud build](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897573260) | Configure backend/accounts, install, and review on a physical phone |
| Android store release | **Not published** | Release signing, privacy information, store review |
| iOS project / IPA | **Not generated / not produced** | macOS, Xcode, Apple signing, actual iPhone review |
| Real model conversations | Eight synthetic scenarios, ten actual official DeepSeek requests recorded | Human quality scoring and deeper romance/adversarial review |

`cap add android` generated and synchronized the original Android source project. The v0.2 packaging run compiled commit `8576f10`. The latest run compiles `930fff8` using Java 21 and Android SDK 36; no SDK was installed locally. Android compilation and [framework CI](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897562260) are separate checks. No emulator or physical-phone validation has been performed.

## Latest v0.5 APK, 2026-10-09

- Source: `930fff8d19182246226e4c75e5b260ed79b5df49`; version name `0.5.0`, version code `4`.
- Compiler: [Android run 37897573260](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897573260), successful; package job 07:11:08–07:12:52 UTC (1m44s).
- Local artifact: `data/releases/Harbor-0.5.0-debug.apk`, ignored by Git; **4,328,380 bytes**.
- SHA-256: `4de651923c9b1e4a6322b6fc7451278e7cc655699857519fdf79b526a0937d58`, matched the downloaded cloud checksum.
- Artifact: `harbor-android-debug-4`, GitHub ID `11601091838`, retention 14 days. Raw downloaded files are preserved under `data/releases/v0.5-cloud-37897573260`.
- Bundle adds bilingual account export/deletion controls and current-password confirmation to the existing account/memory/operations interface. Server lifecycle routes require the matching backend revision.
- No backend address or credentials were supplied to the compiler. An exact comparison across every APK ZIP entry found no copy of the actual locally configured provider secret; its value was not printed.
- [Cloud framework checks](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37897562260) passed: 321 tests in 53.51 seconds, one existing dependency warning, 50/50 synthetic evaluator and frontend build.
- Enter a phone-reachable HTTPS backend/access code and ordinary user credentials at runtime. No public backend was deployed. Native downloads, installation, keyboard/back behavior, rotation, reconnect and account switching still require physical-phone acceptance.

## Historical v0.4 APK, 2026-10-09

- Source: `9679f814e15ade67096512d0e306106edba5b2ff`; version name `0.4.0`, version code `3`.
- Compiler: [Android run 37875934424](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37875934424), successful; package job 02:43:48–02:45:19 UTC (1m31s).
- Local artifact: `data/releases/Harbor-0.4.0-debug.apk`, ignored by Git; **4,324,952 bytes**.
- SHA-256: `e7fdaec8d92d6b6efa492dd21323e3cdb46ae9c32c353ca081e3717bcca0a7fe`, matched the downloaded cloud checksum.
- Artifact: `harbor-android-debug-3`, GitHub ID `11592406601`, retention 14 days. The local downloaded copy is preserved.
- Bundle: account login/session pagination, explicit reviewer permission, repaired memory confirmation, bilingual studio/operations, and the existing synthetic DataAgent.
- No backend address, user/admin token, access code or provider key was supplied to this compiler. Every APK ZIP entry was also checked for the actual local provider secret; none contained it.
- A phone-reachable HTTPS backend is still required. Enter the backend/access code and ordinary user credentials at runtime; Python and the model key are not bundled.
- APK compilation/download is not current browser or physical-device acceptance, stable release signing, store publication, companion-quality scoring, or a production service. Preserve data before manually reinstalling debug builds.

## Historical v0.3 APK, 2026-10-09

- Source: `398bfb0`; Android version name `0.3.0`, version code `2`.
- Compiler: [Android debug run 37843054056](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37843054056), successful (5m1s package job).
- Local artifact: `data/releases/Harbor-0.3.0-debug.apk`, ignored by Git.
- APK size: **4,307,956 bytes**.
- SHA-256: `6269d588116243cab7fe3467f6c3b3c56b4eaeb1806cb3bbaa3d36d8fa2c3791`; locally computed hash matched the cloud checksum.
- Artifact: `harbor-android-debug-2`, GitHub ID `11577759407`, retention 14 days. The downloaded local copy is preserved separately.
- The bundle includes the updated bilingual UI, explicit memory sharing/correction and DataAgent interface. These features need the matching backend; the Python server is not bundled into Android.
- No backend URL, model key, demo code or owner token was supplied to the compiler. Enter a phone-reachable HTTPS backend and demo code at runtime.
- Packaging is not installation, native UX verification, release signing, store publication or real-model evidence. Cloud debug signing does not establish a stable release identity or guarantee an in-place upgrade from every earlier debug build; preserve session handles before any manual reinstall.

## Historical v0.2 APK

- Source: `8576f10` (app/management iteration).
- Compiler evidence: [Android debug APK run](https://github.com/FOWEPJF255/harbor-companion/actions/runs/37818826647), successful.
- Local artifact: `data/releases/Harbor-0.2.0-debug.apk`, ignored by Git.
- APK size: 4,296,748 bytes.
- SHA-256: `7fe91fd083e1b2f310b6917ebfa8c6c51491e4df6b41bd0ab4976bf6bdb99e51`, matched the cloud-produced checksum after download.
- Public backend URL: not compiled in; configure the reachable HTTPS backend in the app at runtime.
- Signing: development/debug only. No store release, iOS IPA, installation on a phone, or real-model quality result is implied.
- The GitHub artifact is retained for 14 days; the downloaded local copy is preserved separately. Re-run the packaging workflow to regenerate it.

A 390px browser preview reviewed the mobile layout and administration initialization surface. It is not a physical-device or native-runtime review. The desktop browser layout was also opened.

## Layout, keyboard, and safe areas

- The HTML viewport includes `viewport-fit=cover` and `interactive-widget=resizes-content`.
- Android declares `windowSoftInputMode="adjustResize"`. This is the initial keyboard layout behavior, not evidence that every keyboard/device combination has passed review.
- Capacitor SystemBars injects `--safe-area-inset-*` variables on Android. The shared styles should use them with `env(safe-area-inset-*, 0px)` fallback.
- Keep the composer outside fixed-size scroll traps. Prefer `100dvh` and bounded message-area scrolling; review keyboard-open, rotation, long text, and bottom gesture navigation on a real device.
- Do not lock orientation in the Android manifest. Tablets and desktop browsers can use the wider layout.
- The shared web application is bundled with the native project. Its contents need a fresh web build and `cap sync` whenever frontend code changes.

## Backend contract

The mobile client needs an API reachable from the phone. A desktop loopback address does not refer to the desktop when used on a phone.

The frontend build variable `VITE_API_BASE_URL` is a **public backend base address**, for example `https://api.example.invalid`. It is not a model-provider URL, API key, or compiled client token. The shared API client appends `/api/...` paths to that base. Do not add `/api` twice.

The native build intentionally does not configure `server.url`, a permissive `allowNavigation`, cleartext traffic, or mixed content. Its presentation assets are packaged locally and its authenticated API calls use HTTPS. CORS and server-origin configuration must explicitly permit the intended client origin (`https://localhost` for default Android, `capacitor://localhost` for default iOS), with authentication remaining required. These are separate concerns: CORS is not authentication.

Configure provider credentials only on the backend. Users connect using the application authentication flow. Never put an administrator credential or provider key into `VITE_*`, a manifest, a native config, or committed files. The backend's local-only default must not be replaced by a public anonymous service merely to make a demo load on a phone.

## PWA privacy and offline behavior

`web/public/app-shell-sw.js` has a narrow cache scope:

- Same-origin, public icons, manifest, offline page, existing favicon, and Vite's hashed JS/CSS only.
- No `/api` request, cross-origin request, non-GET request, request with an `Authorization` header, or query-bearing public-asset URL is stored.
- Responses declaring `private` or `no-store` are not added to the asset cache.
- Navigations use the network and never store HTML. A network failure returns the dedicated offline explanation, not old chat UI pretending to work.
- No conversation, memory, user token, background send queue, or simulated offline reply is placed into Cache Storage.
- Registration is disabled in the Vite development server and in Capacitor. Native apps already include presentation assets.

This is a deliberate online conversation product. Public assets can remain available, but conversation and memory operations require the backend. Already-open interfaces show an offline notice; reconnection does not secretly send drafts.

PWA installation normally requires HTTPS; localhost is useful for desktop development, while an ordinary HTTP LAN address is insufficient for phone installation. Desktop/Android Chromium may provide `beforeinstallprompt`; the component only opens a prompt after receiving that event. iOS uses browser menu guidance rather than claiming programmatic installation. Browser names and installation support vary. See [web.dev installation](https://web.dev/learn/pwa/installation) and [service-worker serving strategies](https://web.dev/learn/pwa/serving).

## Frontend integration

`web/src/AppInstall.tsx` exports `AppInstall`, `registerAppShell`, and `isNativeApp`.

```tsx
import { AppInstall, registerAppShell } from './AppInstall';

void registerAppShell();

// Render in a settings / app-entry section, not in each chat message:
<AppInstall />
```

The component uses `.app-install`, `.install-guide`, and `.connection-notice` classes so the shared interface can style it. It hides installation controls in a native container or a detected standalone window. It does not authenticate users or call the model.

The assets currently assume hosting at the domain root. A future deployment under a subpath requires coordinated manifest paths, worker scope, registration path, and Vite base configuration.

## Android preparation and packaging

Official Capacitor 8 requirements are Node 22+, Android Studio 2025.2.1+, and an Android SDK. The generated project currently uses minimum SDK 24, compile/target SDK 36, Java 21 source compatibility, Android Gradle Plugin 8.13.0, and Gradle 8.14.3. The IDE's bundled JDK is the preferred starting point. See [Capacitor environment setup](https://capacitorjs.com/docs/getting-started/environment-setup).

At the local implementation check, `java` was not available on PATH and neither the default Android Studio folder nor the default user Android SDK folder was found. This is a limited local check; it does not prove that no alternative installation exists.

Once an authenticated HTTPS backend is available:

```powershell
cd C:\1AAAProject\AI\Project\HarborCompanion
# Build frontend assets and synchronize the Android project; does not compile an APK.
.\scripts\android.ps1 -BackendUrl 'https://api.example.invalid' -Mode prepare

# Open the generated project in Android Studio.
.\scripts\android.ps1 -BackendUrl 'https://api.example.invalid' -Mode open

# With the required JDK/SDK configured, explicitly build a development APK.
.\scripts\android.ps1 -BackendUrl 'https://api.example.invalid' -Mode debug
```

The example domain is a placeholder and must be replaced. The script rejects loopback and non-HTTPS backend addresses and restores the previous build variable afterward. It does not install an SDK, configure cloud hosting, create a signing key, or run tests. The expected debug artifact is `mobile/android/app/build/outputs/apk/debug/app-debug.apk`. A debug APK is a development demonstration artifact, not a store-signed release.

For direct CLI use after setting the public backend URL:

```powershell
cd mobile
npm ci
npm run prepare:android
```

Review the packed frontend's backend configuration before distributing an artifact. `web/dist` and copied native web assets are ignored generated outputs and must be rebuilt from source.

## iOS path

Capacitor 8 requires macOS and Xcode 26+. The Windows task did not generate an iOS project or claim an IPA exists. On a Mac, start with a compatible pinned platform package:

```bash
cd mobile
npm install @capacitor/ios@8.5.3
npx cap add ios
npx cap sync ios
npx cap open ios
```

Build the shared frontend with the intended HTTPS backend before syncing. Configure signing and review the actual phone layout, keyboard, safe areas, storage lifecycle, and authentication. App-store distribution requires its own release process.

## Release readiness checklist

1. Host an authenticated HTTPS backend; verify the intended user and administrator boundaries.
2. Provide real provider credentials on the server and assess conversation quality with evidence.
3. Install the compiled APK and document the actual device/version; compilation alone does not verify its runtime.
4. Confirm keyboard/composer behavior, memory controls, deletion, provider errors, and offline recovery.
5. Decide distribution, retention policy, privacy notices, signing, and updates before a wider release.

These are outstanding delivery tasks, not claims of completed product quality.

## Maintainer references

- [Capacitor configuration](https://capacitorjs.com/docs/config): bundled `webDir`, platform settings, and limits of development `server.url`.
- [Capacitor SystemBars](https://capacitorjs.com/docs/apis/system-bars): modern edge-to-edge behavior and injected safe-area CSS variables.
- [Capacitor with React](https://capacitorjs.com/solution/react): native platform projects are part of the application and belong in source control.

Versions were checked against the official documentation and npm package registry on 2026-10-09. Original lighthouse icons are rendered from local geometric code in `mobile/scripts/generate_icons.py`; there are no external portraits or recruiter screenshots in these assets.
