/**
 * FORTIMOVE Sourcing - Background Service Worker
 */

// 페이지 로드 시 아이콘 배지 업데이트
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'page_ready' && sender.tab) {
        const platform = msg.platform;
        if (platform && platform !== 'unknown') {
            chrome.action.setBadgeText({ text: '●', tabId: sender.tab.id });
            chrome.action.setBadgeBackgroundColor({ color: '#e94560', tabId: sender.tab.id });
        } else {
            chrome.action.setBadgeText({ text: '', tabId: sender.tab.id });
        }
    }
});

// 설치 시 환영 페이지
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        chrome.tabs.create({ url: 'http://localhost:8051/workbench' });
    }
});
