import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.harborcompanion.app',
  appName: 'Harbor',
  webDir: '../web/dist',
  backgroundColor: '#111c2d',
  loggingBehavior: 'none',
  android: {
    allowMixedContent: false,
    webContentsDebuggingEnabled: false,
    backgroundColor: '#111c2d',
  },
  ios: {
    contentInset: 'never',
    preferredContentMode: 'mobile',
    webContentsDebuggingEnabled: false,
  },
  plugins: {
    SystemBars: { insetsHandling: 'css', style: 'DARK', hidden: false },
  },
  // Keep assets inside the binary. No server.url or permissive allowNavigation.
};

export default config;
