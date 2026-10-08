import { useEffect, useState } from 'react';

type InstallPrompt = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
};
type CapacitorBridge = { isNativePlatform?: () => boolean; getPlatform?: () => string };

export function isNativeApp(): boolean {
  const bridge = (window as Window & { Capacitor?: CapacitorBridge }).Capacitor;
  return bridge?.isNativePlatform?.() === true;
}

/** Register the browser shell only. Native apps already bundle presentation assets. */
export async function registerAppShell(): Promise<void> {
  if (import.meta.env.DEV || isNativeApp() || !window.isSecureContext || !('serviceWorker' in navigator)) return;
  try {
    const registration = await navigator.serviceWorker.register('/app-shell-sw.js', {
      scope: '/', updateViaCache: 'none',
    });
    await registration.update();
  } catch {
    // Installation support is optional. Never affect the online conversation flow.
  }
}

/** Chromium can provide an install event; other browsers receive explicit menu guidance. */
export function AppInstall() {
  const [prompt, setPrompt] = useState<InstallPrompt | null>(null);
  const [standalone, setStandalone] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [notice, setNotice] = useState('');
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  useEffect(() => {
    const media = window.matchMedia('(display-mode: standalone)');
    const syncInstalled = () => setStandalone(media.matches
      || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
    const onPrompt = (event: Event) => { event.preventDefault(); setPrompt(event as InstallPrompt); };
    const onInstalled = () => { setPrompt(null); setStandalone(true); setNotice('已添加到设备。'); };
    const online = () => setOffline(false);
    const disconnected = () => setOffline(true);
    syncInstalled();
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    window.addEventListener('online', online);
    window.addEventListener('offline', disconnected);
    media.addEventListener('change', syncInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
      window.removeEventListener('online', online);
      window.removeEventListener('offline', disconnected);
      media.removeEventListener('change', syncInstalled);
    };
  }, []);

  async function install() {
    if (!prompt) return;
    try {
      await prompt.prompt();
      const choice = await prompt.userChoice;
      setNotice(choice.outcome === 'accepted' ? '已提交安装请求，请按设备提示完成。' : '可稍后从浏览器菜单添加。');
    } catch {
      setNotice('当前浏览器未完成安装，请使用浏览器菜单。');
    } finally { setPrompt(null); }
  }

  if (isNativeApp()) return offline
    ? <p className="connection-notice" role="status">当前离线，请恢复网络后继续聊天；不会离线生成或排队发送消息。</p>
    : null;

  return <div className="app-install">
    {offline && <p className="connection-notice" role="status">当前离线，请恢复网络后继续聊天。</p>}
    {!standalone && (prompt
      ? <button type="button" className="quiet" onClick={install}>添加港湾到设备</button>
      : <details className="install-guide">
        <summary>添加到手机 / 电脑</summary>
        <p>{isIOS
          ? 'iPhone / iPad：请在 Safari 打开，点击分享，再选择“添加到主屏幕”。'
          : 'Chrome / Edge：可查看地址栏安装图标或浏览器菜单中的“安装应用 / 添加到主屏幕”。其他浏览器支持情况不同。'}</p>
        {!window.isSecureContext && <p>安装支持需要公开 HTTPS 地址；手机访问电脑的普通 HTTP 局域网地址通常不能安装。</p>}
        <small>这是浏览器可安装版。Android APP 使用独立安装包；两者交付方式不同。</small>
      </details>)}
    {notice && <p role="status">{notice}</p>}
  </div>;
}
