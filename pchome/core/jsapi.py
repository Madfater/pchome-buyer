"""在瀏覽器端執行的 JS 片段

PChome 的 prod/button、cart modify 皆為 JSONP-only 端點（跨域無 CORS），
必須用 <script> 注入呼叫，不能用 fetch；snapup 與 datetime 有 CORS，用 fetch。
"""

# 共用 JSONP helper：url 中的 {CB} 會被替換成一次性的 callback 名稱。
JSONP_JS = """
(url) => new Promise((resolve, reject) => {
    const cb = '_jsonp_' + Date.now() + '_' + Math.floor(Math.random() * 1e6);
    let timer;
    const cleanup = (s) => { delete window[cb]; clearTimeout(timer); s.remove(); };
    window[cb] = (data) => { cleanup(s); resolve(data); };
    const s = document.createElement('script');
    s.src = url.split('{CB}').join(cb);
    s.onerror = () => { cleanup(s); reject(new Error('JSONP failed')); };
    timer = setTimeout(() => { cleanup(s); reject(new Error('JSONP timeout')); }, 10000);
    document.head.appendChild(s);
})
"""

# 批次加入購物車：snapup fetch 並行取得所有 MAC（效期 15 秒），
# 但 cart modify 必須「逐一序列」執行 —— PChome 的購物車寫入是整車覆蓋
# （last-write-wins），並行 modify 會互相蓋掉，只有最後一個商品留在車上。
ADD_TO_CART_JS = (
    """
(args) => {
    const jsonp = %s;
    return (async () => {
        const snaps = await Promise.all(args.items.map(async (item) => {
            try {
                return { item, snap: await fetch(item.snapupUrl).then(r => r.json()) };
            } catch (e) {
                return { item, error: String(e) };
            }
        }));
        const results = [];
        for (const { item, snap, error } of snaps) {
            if (error) {
                results.push({ pid: item.pid, ok: false, stage: 'error', error });
                continue;
            }
            if (snap.Status !== 'OK') {
                results.push({ pid: item.pid, ok: false, stage: 'snapup', resp: snap });
                continue;
            }
            try {
                const data = { ...item.cart, CAX: snap.MAC, CAXE: snap.MACExpire };
                const ts = Date.now();
                const url = args.modifyApi
                    + `?callback={CB}&${ts}`
                    + `&data=${encodeURIComponent(JSON.stringify(data))}`
                    + `&_=${ts}&_callback={CB}`;
                const resp = await jsonp(url);
                results.push({
                    pid: item.pid,
                    ok: resp.PRODADD === '1',
                    soldOut: resp.ISSALEOUT === 1,
                    stage: 'modify',
                    resp,
                });
            } catch (e) {
                results.push({ pid: item.pid, ok: false, stage: 'error', error: String(e) });
            }
        }
        return results;
    })();
}
"""
    % JSONP_JS
)
