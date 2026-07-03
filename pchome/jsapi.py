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

# 批次加入購物車：每個商品做 snapup fetch → cart modify JSONP，
# 多商品以 Promise.all 並行（MAC 授權碼效期僅 15 秒，兩步必須緊接執行）。
ADD_TO_CART_JS = """
(args) => {
    const jsonp = %s;
    return Promise.all(args.items.map(async (item) => {
        try {
            const snap = await fetch(item.snapupUrl).then(r => r.json());
            if (snap.Status !== 'OK')
                return { pid: item.pid, ok: false, stage: 'snapup', resp: snap };
            const data = { ...item.cart, CAX: snap.MAC, CAXE: snap.MACExpire };
            const ts = Date.now();
            const url = args.modifyApi
                + `?callback={CB}&${ts}`
                + `&data=${encodeURIComponent(JSON.stringify(data))}`
                + `&_=${ts}&_callback={CB}`;
            const resp = await jsonp(url);
            return {
                pid: item.pid,
                ok: resp.PRODADD === '1',
                soldOut: resp.ISSALEOUT === 1,
                stage: 'modify',
                resp,
            };
        } catch (e) {
            return { pid: item.pid, ok: false, stage: 'error', error: String(e) };
        }
    }));
}
""" % JSONP_JS
