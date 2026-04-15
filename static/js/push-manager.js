/**
 * PWA Push Notification Manager
 * VAPID 기반 웹 푸시 구독/해제 관리
 */

function getCSRFToken() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
}

async function subscribePush() {
    try {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            alert('알림 권한이 거부되었습니다. 브라우저 설정에서 허용해주세요.');
            return false;
        }

        const reg = await navigator.serviceWorker.ready;

        // VAPID public key (서버 설정에서 가져옴)
        let vapidKey = document.querySelector('meta[name="vapid-public-key"]');
        if (!vapidKey) {
            console.warn('VAPID public key not found, using placeholder');
            return false;
        }

        const subscription = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey.content),
        });

        // 서버에 구독 정보 전송
        const response = await fetch('/push/subscribe/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(subscription.toJSON()),
        });

        const result = await response.json();
        return result.success;
    } catch (err) {
        console.error('Push subscription failed:', err);
        return false;
    }
}

async function unsubscribePush(subscription) {
    try {
        if (!subscription) {
            const reg = await navigator.serviceWorker.ready;
            subscription = await reg.pushManager.getSubscription();
        }

        if (subscription) {
            // 서버에 해제 알림
            await fetch('/push/unsubscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                },
                body: JSON.stringify({ endpoint: subscription.endpoint }),
            });

            await subscription.unsubscribe();
        }
        return true;
    } catch (err) {
        console.error('Push unsubscribe failed:', err);
        return false;
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}
