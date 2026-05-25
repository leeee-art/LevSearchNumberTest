from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import requests
import json
import re
import socket
import yt_dlp
import csv
import io
import whois
import dns.resolver
from urllib.parse import unquote, quote
from datetime import date
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# ========== КОНФИГУРАЦИЯ ==========
TOKEN_MAIN = "LevSearchApiAll"
TOKEN_1K = "1KSUBS"
LEAKOSINT_KEY = "8702237281:cYkLAFK4"
VK_TOKEN = "vk1.a.WX465fcyCl3FoFXysIyBPjQYn4D4Cgz3SJAmX7mxXvQBMUzTjzkaZfA0Tt-FBRDuA4WYq7tvbO3TaqZbvdl3oAva367V8KP4AQUFI1kC3I8UnT687rM12Bv-d-Ax9FnXAeOTxMp8MTBUwqQ_6kH-1LAQIT7fgdzWaawG3CEOhe6Q5VSuzTrDFF0iWIrUAXIwT22_uN6XzH25tZCegI-AWQ"
VERIPHONE_KEY = "A9A2A88762854D45888BA49E8F98509C"
OMKAR_API_KEY = "ok_ad50fb80682eff950d34e7a9b3a77c8c"

ALL_TOKENS = [TOKEN_MAIN, TOKEN_1K]

# ========== ЛИМИТЫ ЗАПРОСОВ (ТОЛЬКО ДЛЯ 1KSUBS - 500 В ДЕНЬ) ==========
request_counts = defaultdict(int)
request_dates = defaultdict(str)

def check_limit(token):
    # У токена LevSearchApiAll НЕТ ограничений
    if token == TOKEN_MAIN:
        return True, None
    
    # У токена 1KSUBS - 500 запросов в день
    today = date.today().isoformat()
    if request_dates[token] != today:
        request_dates[token] = today
        request_counts[token] = 0
    
    if request_counts[token] >= 500:
        return False, "Превышен лимит 500 запросов в день для токена 1KSUBS"
    
    request_counts[token] += 1
    return True, None

def check_token(token):
    return token in ALL_TOKENS

# ========== INTELX ПАРСЕР ==========
def get_intelx(phone):
    phone_clean = re.sub(r'\D', '', phone)
    if len(phone_clean) < 8:
        return {"error": "номер слишком короткий"}
    
    url = f'https://data.intelx.io/saverudata/db2/dbpn/{phone_clean[:2]}/{phone_clean[2:4]}/{phone_clean[4:6]}/{phone_clean[6:8]}.csv'
    
    try:
        r = requests.get(url, timeout=15, verify=False)
        if r.status_code == 200:
            data = list(csv.reader(io.StringIO(r.text)))
            if len(data) > 1:
                headers = data[0]
                results = []
                for row in data[1:]:
                    if phone_clean in ' '.join(row):
                        item = {}
                        for i, cell in enumerate(row):
                            if i < len(headers) and cell:
                                item[headers[i]] = cell
                        results.append(item)
                return {"status": "success", "source": "intelx", "results": results}
            return {"status": "empty", "source": "intelx"}
        return {"status": "error", "source": "intelx", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "source": "intelx", "message": str(e)}

# ========== LEAKOSINT ПАРСЕР (ТОЛЬКО ДЛЯ MAIN ТОКЕНА) ==========
def get_leakosint(query):
    try:
        r = requests.post('https://leakosintapi.com/', json={'token': LEAKOSINT_KEY, 'request': query}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return {
                "status": "success",
                "balance": data.get('remaining_balance'),
                "results": data.get('List', {}),
                "raw_data": data
            }
        return {"status": "error", "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ========== VERIPHONE ==========
def get_veriphone(phone):
    phone_clean = re.sub(r'\D', '', phone)
    url = "https://api.veriphone.io/v2/verify"
    params = {"phone": phone_clean, "key": VERIPHONE_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "valid": data.get("valid"),
                "country": data.get("country_code"),
                "carrier": data.get("carrier"),
                "type": data.get("phone_type")
            }
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== WHATSAPP ==========
def get_whatsapp(phone):
    phone_clean = re.sub(r'\D', '', phone)
    if phone_clean.startswith('8'):
        phone_clean = '7' + phone_clean[1:]
    elif not phone_clean.startswith('7'):
        phone_clean = '7' + phone_clean
    try:
        r = requests.get(f"https://wa.me/{phone_clean}", timeout=10, allow_redirects=True)
        if r.status_code == 200:
            if "This phone number is not on WhatsApp" in r.text:
                return {"exists": False, "phone": phone_clean}
            else:
                return {"exists": True, "phone": phone_clean}
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== ODNOKLASSNIKI ==========
def get_odnoklassniki(phone):
    phone_clean = re.sub(r'\D', '', phone)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        url = "https://ok.ru/search"
        params = {"st.mode": "Users", "st.query": phone_clean}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            match = re.search(r'num-found["\s]*:["\s]*(\d+)', r.text)
            if match and int(match.group(1)) > 0:
                return {"exists": True, "phone": phone_clean}
            return {"exists": False, "phone": phone_clean}
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== OMKAR PHONE ==========
def get_omkar_phone(phone):
    url = "https://carrier-lookup-api.omkar.cloud/lookup"
    params = {"phone": phone}
    headers = {"API-Key": OMKAR_API_KEY}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== OMKAR EMAIL ==========
def get_omkar_email(email):
    url = "https://email-verification-api.omkar.cloud/verify"
    params = {"email": email}
    headers = {"API-Key": OMKAR_API_KEY}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== YOUTUBE ==========
def get_youtube_info(url):
    ydl_opts = {'quiet': True, 'extract_flat': False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                "status": "success",
                "title": info.get('title'),
                "description": info.get('description'),
                "view_count": info.get('view_count'),
                "like_count": info.get('like_count'),
                "duration": info.get('duration_string'),
                "channel": info.get('channel'),
                "channel_url": info.get('channel_url'),
                "upload_date": info.get('upload_date'),
                "tags": info.get('tags'),
                "thumbnail": info.get('thumbnail'),
                "url": info.get('webpage_url'),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# ========== СОЦИАЛЬНЫЕ СЕТИ ==========
def get_social_links(phone):
    phone_clean = ''.join(filter(str.isdigit, phone))
    return {
        "Facebook": f"https://www.facebook.com/search/top?q={phone_clean}",
        "Instagram": f"https://www.instagram.com/{phone_clean}",
        "VK": f"https://vk.com/search?c[q]={phone_clean}&c[section]=people",
        "TikTok": f"https://www.tiktok.com/search?q={phone_clean}",
        "LinkedIn": f"https://www.linkedin.com/search/results/all/?keywords={phone_clean}",
        "Twitter": f"https://twitter.com/search?q={phone_clean}",
        "Snapchat": f"https://www.snapchat.com/add/{phone_clean}",
        "Telegram": f"https://t.me/{phone_clean}",
        "WhatsApp": f"https://wa.me/{phone_clean}",
        "Viber": f"viber://add?number={phone_clean}",
        "Skype": f"skype:{phone_clean}?chat",
        "Pinterest": f"https://www.pinterest.com/search/people/?q={phone_clean}",
        "Reddit": f"https://www.reddit.com/search/?q={phone_clean}",
        "YouTube": f"https://www.youtube.com/results?search_query={phone_clean}",
        "Odnoklassniki": f"https://ok.ru/search?q={phone_clean}",
        "Mail.ru": f"https://my.mail.ru/search?q={phone_clean}",
        "Avito": f"https://www.avito.ru/all?q={phone_clean}",
        "Yandex": f"https://yandex.ru/search/?text={phone_clean}",
        "Google": f"https://www.google.com/search?q={phone_clean}",
        "Bing": f"https://www.bing.com/search?q={phone_clean}",
        "DuckDuckGo": f"https://duckduckgo.com/?q={phone_clean}",
        "2GIS": f"https://2gis.ru/search/{phone_clean}",
        "Zoon": f"https://zoon.ru/search/?q={phone_clean}",
        "Flamp": f"https://flamp.ru/search?query={phone_clean}",
        "Prozvon": f"https://prozvon.info/ru/number/{phone_clean}",
        "NumBuster": f"https://numbuster.com/ru/number/{phone_clean}",
        "GetContact": f"https://getcontact.com/ru/search/{phone_clean}",
        "Truecaller": f"https://www.truecaller.com/search/ru/{phone_clean}",
        "FindClone": f"https://findclone.ru/phone?phone={phone_clean}",
        "LeakCheck": f"https://leakcheck.net/search?query={phone_clean}",
        "HaveIBeenPwned": f"https://haveibeenpwned.com/account/{phone_clean}"
    }

# ========== GOOGLE DORKS ==========
def get_google_dorks(phone):
    phone_clean = ''.join(filter(str.isdigit, phone))
    if phone_clean.startswith('8'):
        phone_clean = '7' + phone_clean[1:]
    
    dorks_list = [
        f'"+{phone_clean}"',
        f'"{phone_clean}" filetype:pdf',
        f'"{phone_clean}" filetype:xlsx',
        f'"{phone_clean}" filetype:txt',
        f'"{phone_clean}" site:avito.ru',
        f'"{phone_clean}" site:vk.com',
        f'"{phone_clean}" site:facebook.com',
        f'"{phone_clean}" site:instagram.com',
        f'"{phone_clean}" site:ok.ru',
        f'"{phone_clean}" site:2gis.ru',
        f'"{phone_clean}" site:yandex.ru',
        f'"{phone_clean}" site:google.com',
        f'"{phone_clean}" intext:"контакт"',
        f'"{phone_clean}" intext:"связь"',
        f'"{phone_clean}" intext:"телефон"',
        f'"{phone_clean}" site:gov.ru',
        f'"{phone_clean}" site:edu.ru',
        f'"{phone_clean}" site:ru filetype:pdf',
        f'"{phone_clean}" site:ru filetype:xlsx',
        f'"{phone_clean}" "ИНН"',
        f'"{phone_clean}" "паспорт"',
        f'"{phone_clean}" "адрес"',
        f'"{phone_clean}" "доставка"',
        f'"{phone_clean}" "заказ"',
        f'"{phone_clean}" "СНИЛС"'
    ]
    
    dork_urls = []
    for dork in dorks_list:
        encoded = quote(dork)
        dork_urls.append(f"https://www.google.com/search?q={encoded}")
    
    return dork_urls

# ========== БАНКИ ПО ИНН ==========
def get_bank_by_inn(inn):
    banks_database = {
        "7707083893": "Публичное акционерное общество Сбербанк России",
        "7702070139": "Банк ВТБ публичное акционерное общество",
        "7710140679": "Т-Банк (ранее Тинькофф Банк)",
        "7728168971": "Акционерное общество Альфа-Банк",
        "7710030411": "ЮниКредит Банк",
        "7744000302": "Райффайзенбанк",
        "7744001497": "Газпромбанк (акционерное общество)",
        "7725114488": "Россельхозбанк",
        "7734203979": "Московский Кредитный Банк",
        "7709202522": "Публичное акционерное общество Банк Открытие",
        "4401116480": "Публичное акционерное общество Совкомбанк",
        "7744000912": "Промсвязьбанк",
        "7830000023": "Росбанк",
        "7702235133": "Центральный Банк Российской Федерации",
        "7703214210": "Московский Банк Сбербанка",
        "7729497622": "Ренессанс Кредит",
        "7706115350": "МТС-Банк",
        "7736255716": "Русский Стандарт",
        "7831000571": "Банк Санкт-Петербург",
        "7704010100": "Росгосстрах Банк",
        "7705426190": "Дойче Банк",
        "7744001678": "Новикомбанк",
        "7710383406": "Экспобанк",
        "7725161778": "ФК Открытие",
        "7704037971": "Абсолют Банк",
        "7704120582": "Транскапиталбанк",
        "7708023639": "Номос-Банк",
        "7723013520": "Российский Капитал",
        "7811322120": "Балтийский Банк",
        "7728073774": "Связь-Банк",
        "7708010008": "Банк Зенит",
        "7717019510": "Кредит Европа Банк",
        "7707309927": "Уралсиб",
        "7804000073": "Банк Санкт-Петербург",
        "7724008957": "Интерпромбанк",
        "7730161008": "Московский Индустриальный Банк",
        "7728020682": "Банк ДОМ.РФ",
        "7715015200": "Хоум Кредит Банк",
        "7711000001": "Сбербанк (спецказначейский)",
        "7710031876": "Банк Синара",
        "7727009645": "Почта Банк",
        "7728230191": "Озон Банк"
    }
    return banks_database.get(inn, "Банк не найден")

# ========== BIN CARD ==========
def get_card_info(bin_number):
    url = f"https://lookup.binlist.net/{bin_number}"
    headers = {'Accept-Version': '3'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "bin": bin_number,
                "bank": data.get('bank', {}).get('name'),
                "country": data.get('country', {}).get('name'),
                "brand": data.get('scheme'),
                "type": data.get('type')
            }
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== DOMAIN ==========
def get_domain_info(domain_name):
    result = {"domain": domain_name}
    try:
        result["ip"] = socket.gethostbyname(domain_name)
    except:
        result["ip"] = None
    
    common_ports = [21, 22, 25, 80, 443, 3306, 5432, 8080]
    open_ports = []
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex((domain_name, port)) == 0:
                open_ports.append(port)
            s.close()
        except:
            pass
    result["open_ports"] = open_ports
    
    return result

# ========== VK ==========
def get_vk_user(user_id):
    try:
        url = "https://api.vk.com/method/users.get"
        params = {
            "access_token": VK_TOKEN,
            "user_ids": user_id,
            "v": "5.131",
            "fields": "first_name,last_name,domain,followers_count,is_closed,sex,bdate,city,country,photo_max_orig,status"
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if "response" in data and data["response"]:
                user = data["response"][0]
                return {
                    "id": user.get("id"),
                    "name": f"{user.get('first_name', '')} {user.get('last_name', '')}",
                    "domain": user.get("domain"),
                    "followers": user.get("followers_count"),
                    "is_closed": user.get("is_closed", False),
                    "sex": "Женский" if user.get("sex") == 1 else "Мужской" if user.get("sex") == 2 else "Не указан",
                    "bdate": user.get("bdate"),
                    "city": user.get("city", {}).get("title"),
                    "country": user.get("country", {}).get("title"),
                    "photo": user.get("photo_max_orig"),
                    "status": user.get("status")
                }
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

# ========== IP ==========
def get_ip_info(ip_address):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "success":
                return {
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "isp": data.get("isp"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon")
                }
        return {"error": "IP not found"}
    except Exception as e:
        return {"error": str(e)}

# ========== TIKTOK ==========
def get_tiktok_user(username):
    username = username.replace('@', '').strip()
    url = f"https://www.tiktok.com/@{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            followers_match = re.search(r'"followerCount":(\d+)', r.text)
            followers = int(followers_match.group(1)) if followers_match else 0
            name_match = re.search(r'"nickname":"([^"]+)"', r.text)
            name = name_match.group(1) if name_match else None
            return {
                "username": username,
                "name": name,
                "followers": followers
            }
        return {"error": "User not found"}
    except Exception as e:
        return {"error": str(e)}

# ========== INSTAGRAM ==========
def get_instagram_by_phone(phone):
    phone_clean = ''.join(filter(str.isdigit, phone))
    url = f"https://www.google.com/search?q=site:instagram.com+{phone_clean}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and "instagram.com" in r.text:
            username_match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', r.text)
            username = username_match.group(1) if username_match else None
            return {"exists": True, "username": username}
        return {"exists": False}
    except Exception as e:
        return {"error": str(e)}

# ========== EMAIL MX ==========
def get_email_mx(email_address):
    email_address = unquote(email_address)
    domain = email_address.split('@')[-1]
    try:
        import subprocess
        result = subprocess.run(['nslookup', '-type=mx', domain], capture_output=True, text=True, timeout=10)
        has_mx = "mail exchanger" in result.stdout
        return {"email": email_address, "has_mx": has_mx, "domain": domain}
    except:
        return {"email": email_address, "has_mx": False, "domain": domain}

# ========== TELEGRAM ==========
def get_telegram_user(username):
    username = username.replace("@", "").strip()
    url = f"https://t.me/{username}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            if "If you have Telegram" in r.text or "is not available" in r.text:
                return {"exists": False, "username": username}
            else:
                return {"exists": True, "username": username}
        return {"exists": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== WHOIS ПАРСЕР ==========
@app.route('/whois')
def whois_parser():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    domain = request.args.get('domain', '')
    if not domain:
        return jsonify({"error": "Missing domain parameter"}), 400
    
    try:
        w = whois.whois(domain)
        result = {
            "domain": domain,
            "registrar": str(w.registrar) if w.registrar else None,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "updated_date": str(w.updated_date) if w.updated_date else None,
            "name_servers": w.name_servers,
            "status": w.status,
            "emails": w.emails,
            "org": str(w.org) if w.org else None,
            "country": str(w.country) if w.country else None
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== DNS ПАРСЕР ==========
@app.route('/dns')
def dns_parser():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    domain = request.args.get('domain', '')
    if not domain:
        return jsonify({"error": "Missing domain parameter"}), 400
    
    records = {}
    types = ['A', 'AAAA', 'MX', 'NS', 'TXT', 'CNAME', 'SOA']
    
    for record_type in types:
        try:
            answers = dns.resolver.resolve(domain, record_type)
            records[record_type] = [str(r) for r in answers]
        except:
            records[record_type] = []
    
    return jsonify({"domain": domain, "records": records})

# ========== ЗАГОЛОВКИ САЙТА ==========
@app.route('/headers')
def headers_parser():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    url = request.args.get('url', '')
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    if not url.startswith('http'):
        url = 'https://' + url
    
    try:
        r = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        result = {
            "url": url,
            "status_code": r.status_code,
            "server": r.headers.get('Server'),
            "content_type": r.headers.get('Content-Type'),
            "headers": dict(r.headers),
            "response_time": r.elapsed.total_seconds()
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== ПОДДОМЕНЫ ==========
@app.route('/subdomains')
def subdomains_parser():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    domain = request.args.get('domain', '')
    if not domain:
        return jsonify({"error": "Missing domain parameter"}), 400
    
    try:
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            subdomains = set()
            for entry in data:
                name = entry.get('name_value', '')
                if name:
                    for sub in name.split('\n'):
                        if domain in sub:
                            subdomains.add(sub.strip())
            return jsonify({"domain": domain, "subdomains": list(subdomains)[:50]})
        return jsonify({"error": f"HTTP {r.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== OMKAR ОТЗЫВЫ ==========
@app.route('/omkar/reviews')
def omkar_reviews():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    query = request.args.get('query', '')
    if not query:
        return jsonify({"error": "Missing query parameter"}), 400
    
    try:
        url = "https://travel-data-api.omkar.cloud/travel/reviews"
        r = requests.get(
            url,
            params={"query": query},
            headers={"API-Key": OMKAR_API_KEY},
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            results = []
            for review in data.get('results', [])[:20]:
                results.append({
                    "title": review.get('title'),
                    "rating": review.get('rating'),
                    "text": review.get('text')[:500] if review.get('text') else None,
                    "date": review.get('published_at_date'),
                    "author": review.get('reviewer', {}).get('name'),
                    "link": review.get('review_link')
                })
            return jsonify({
                "query": query,
                "total": data.get('count', 0),
                "reviews": results
            })
        return jsonify({"error": f"HTTP {r.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== VK СТЕНА ==========
@app.route('/vk/wall')
def vk_wall():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    user_id = request.args.get('id', '')
    count = int(request.args.get('count', 10))
    
    try:
        url = "https://api.vk.com/method/wall.get"
        params = {
            "access_token": VK_TOKEN,
            "owner_id": user_id,
            "v": "5.131",
            "count": count,
            "filter": "all"
        }
        r = requests.get(url, params=params, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== VK ДРУЗЬЯ ==========
@app.route('/vk/friends')
def vk_friends():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    user_id = request.args.get('id', '')
    
    try:
        url = "https://api.vk.com/method/friends.get"
        params = {
            "access_token": VK_TOKEN,
            "user_id": user_id,
            "v": "5.131",
            "fields": "first_name,last_name,photo_100"
        }
        r = requests.get(url, params=params, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== VK ГРУППЫ ==========
@app.route('/vk/groups')
def vk_groups():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    user_id = request.args.get('id', '')
    
    try:
        url = "https://api.vk.com/method/groups.get"
        params = {
            "access_token": VK_TOKEN,
            "user_id": user_id,
            "v": "5.131",
            "extended": 1,
            "fields": "name,photo_100,members_count"
        }
        r = requests.get(url, params=params, timeout=10)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e)})

# ========== HTML ДОКУМЕНТАЦИЯ (КРАСИВАЯ) ==========
HTML_DOC = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LevSearch API - Документация</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0a0e27 0%, #0f1228 100%);
            color: #e0e0e0;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        /* Header */
        .header {
            text-align: center;
            padding: 40px 20px;
            background: linear-gradient(135deg, #00ff9d20 0%, #00ff9d05 100%);
            border-radius: 20px;
            margin-bottom: 40px;
            border: 1px solid #00ff9d30;
        }
        
        .header h1 {
            font-size: 3em;
            background: linear-gradient(135deg, #00ff9d, #00cc7a);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            margin-bottom: 10px;
        }
        
        .header p {
            color: #888;
            font-size: 1.1em;
        }
        
        .badge {
            display: inline-block;
            background: #00ff9d20;
            color: #00ff9d;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-top: 15px;
            border: 1px solid #00ff9d40;
        }
        
        /* Stats */
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .stat-card {
            background: #0f1228;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            border: 1px solid #1a1f3a;
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            color: #00ff9d;
        }
        
        .stat-label {
            color: #888;
            margin-top: 5px;
        }
        
        /* Search */
        .search-section {
            background: #0f1228;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 40px;
            border: 1px solid #1a1f3a;
        }
        
        .search-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #00ff9d;
        }
        
        .search-form {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .search-input {
            flex: 1;
            padding: 12px 20px;
            background: #1a1f3a;
            border: 1px solid #2a2f4a;
            border-radius: 10px;
            color: #e0e0e0;
            font-size: 1em;
            outline: none;
            transition: all 0.3s;
        }
        
        .search-input:focus {
            border-color: #00ff9d;
            box-shadow: 0 0 10px #00ff9d20;
        }
        
        .search-select {
            padding: 12px 20px;
            background: #1a1f3a;
            border: 1px solid #2a2f4a;
            border-radius: 10px;
            color: #e0e0e0;
            font-size: 1em;
            cursor: pointer;
        }
        
        .search-button {
            padding: 12px 30px;
            background: linear-gradient(135deg, #00ff9d, #00cc7a);
            border: none;
            border-radius: 10px;
            color: #0a0e27;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        .search-button:hover {
            transform: translateY(-2px);
        }
        
        /* Endpoints */
        .endpoints {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }
        
        .endpoint-card {
            background: #0f1228;
            border-radius: 15px;
            overflow: hidden;
            border: 1px solid #1a1f3a;
            transition: all 0.3s;
        }
        
        .endpoint-card:hover {
            border-color: #00ff9d40;
            transform: translateY(-3px);
        }
        
        .endpoint-header {
            background: #1a1f3a;
            padding: 15px 20px;
            border-bottom: 1px solid #2a2f4a;
        }
        
        .endpoint-method {
            display: inline-block;
            padding: 4px 12px;
            background: #00ff9d20;
            color: #00ff9d;
            border-radius: 6px;
            font-size: 0.75em;
            font-weight: bold;
            margin-right: 10px;
        }
        
        .endpoint-path {
            font-family: monospace;
            font-size: 1em;
            color: #e0e0e0;
        }
        
        .endpoint-body {
            padding: 15px 20px;
        }
        
        .endpoint-desc {
            color: #aaa;
            font-size: 0.9em;
            margin-bottom: 10px;
        }
        
        .endpoint-example {
            background: #0a0e27;
            padding: 10px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 0.8em;
            color: #00ff9d;
            word-break: break-all;
        }
        
        .token-badge {
            display: inline-block;
            padding: 4px 10px;
            background: #ff444420;
            color: #ff4444;
            border-radius: 6px;
            font-size: 0.7em;
            margin-top: 10px;
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 30px;
            border-top: 1px solid #1a1f3a;
            margin-top: 40px;
            color: #666;
        }
        
        @media (max-width: 768px) {
            .endpoints {
                grid-template-columns: 1fr;
            }
            .search-form {
                flex-direction: column;
            }
            .header h1 {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 LevSearch API</h1>
            <p>Мощный OSINT инструмент для поиска информации</p>
            <div class="badge">🟢 API работает</div>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">30+</div>
                <div class="stat-label">Эндпоинтов</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">15+</div>
                <div class="stat-label">Парсеров</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">∞</div>
                <div class="stat-label">Лимит (LevSearchApiAll)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">500</div>
                <div class="stat-label">Лимит/день (1KSUBS)</div>
            </div>
        </div>
        
        <div class="search-section">
            <div class="search-title">🚀 Быстрый тест API</div>
            <div class="search-form">
                <input type="text" id="queryInput" class="search-input" placeholder="Телефон, email, домен, IP...">
                <select id="endpointSelect" class="search-select">
                    <option value="/search">🔍 Поиск (все данные)</option>
                    <option value="/intelx">📂 IntelX утечки</option>
                    <option value="/leakosint">🔥 LeakOSINT</option>
                    <option value="/whois">🌐 WHOIS домена</option>
                    <option value="/dns">📋 DNS записи</option>
                    <option value="/subdomains">🌍 Поддомены</option>
                    <option value="/headers">📄 Заголовки сайта</option>
                    <option value="/vk">👤 VK пользователь</option>
                    <option value="/ip">📍 IP геолокация</option>
                    <option value="/card">💳 BIN карты</option>
                    <option value="/bank">🏦 Банк по ИНН</option>
                    <option value="/tiktok">🎵 TikTok пользователь</option>
                    <option value="/telegram">📱 Telegram пользователь</option>
                    <option value="/email">📧 Email проверка</option>
                    <option value="/omkar/reviews">⭐ Отзывы Omkar</option>
                    <option value="/youtube">🎬 YouTube</option>
                    <option value="/whatsapp">💬 WhatsApp</option>
                    <option value="/odnoklassniki">👥 Одноклассники</option>
                </select>
                <input type="text" id="tokenInput" class="search-input" placeholder="Токен (LevSearchApiAll или 1KSUBS)" value="LevSearchApiAll">
                <button class="search-button" onclick="testAPI()">▶ Отправить</button>
            </div>
            <pre id="resultPre" style="margin-top: 20px; background: #0a0e27; padding: 15px; border-radius: 10px; overflow-x: auto; font-size: 12px; display: none;"></pre>
        </div>
        
        <div class="endpoints">
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/search</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🔍 Основной поиск - объединяет IntelX, Veriphone, WhatsApp, Одноклассники, Omkar, соцсети, Google Dorks и LeakOSINT</div>
                    <div class="endpoint-example">/search?token=LevSearchApiAll&q=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/intelx</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📂 Поиск утечек в открытых базах IntelX</div>
                    <div class="endpoint-example">/intelx?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/leakosint</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🔥 Платный API утечек (ТОЛЬКО для токена LevSearchApiAll)</div>
                    <div class="endpoint-example">/leakosint?token=LevSearchApiAll&q=79233756070</div>
                    <div class="token-badge">⚡ Только LevSearchApiAll</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/whois</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🌐 WHOIS информация о домене</div>
                    <div class="endpoint-example">/whois?token=LevSearchApiAll&domain=google.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/dns</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📋 DNS записи домена (A, MX, NS, TXT, CNAME, SOA, AAAA)</div>
                    <div class="endpoint-example">/dns?token=LevSearchApiAll&domain=google.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/subdomains</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🌍 Поиск поддоменов через crt.sh</div>
                    <div class="endpoint-example">/subdomains?token=LevSearchApiAll&domain=google.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/headers</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📄 HTTP заголовки сайта</div>
                    <div class="endpoint-example">/headers?token=LevSearchApiAll&url=google.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/vk</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">👤 Информация о VK пользователе</div>
                    <div class="endpoint-example">/vk?token=LevSearchApiAll&id=1</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/vk/wall</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📝 Стена VK пользователя</div>
                    <div class="endpoint-example">/vk/wall?token=LevSearchApiAll&id=1&count=5</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/vk/friends</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">👥 Друзья VK пользователя</div>
                    <div class="endpoint-example">/vk/friends?token=LevSearchApiAll&id=1</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/vk/groups</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📚 Группы VK пользователя</div>
                    <div class="endpoint-example">/vk/groups?token=LevSearchApiAll&id=1</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/ip</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📍 Геолокация IP адреса</div>
                    <div class="endpoint-example">/ip?token=LevSearchApiAll&address=8.8.8.8</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/card</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">💳 Информация о банковской карте по BIN</div>
                    <div class="endpoint-example">/card?token=LevSearchApiAll&bin=477964</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/bank</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🏦 Поиск банка по ИНН</div>
                    <div class="endpoint-example">/bank?token=LevSearchApiAll&inn=7707083893</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/tiktok</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🎵 Информация о TikTok пользователе</div>
                    <div class="endpoint-example">/tiktok?token=LevSearchApiAll&username=marvel</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/telegram</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📱 Проверка существования Telegram</div>
                    <div class="endpoint-example">/telegram?token=LevSearchApiAll&username=durov</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/instagram</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📸 Поиск Instagram по номеру телефона</div>
                    <div class="endpoint-example">/instagram?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/email</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📧 Проверка MX записей email</div>
                    <div class="endpoint-example">/email?token=LevSearchApiAll&address=test@gmail.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/omkar/reviews</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">⭐ Отзывы о месте через Omkar</div>
                    <div class="endpoint-example">/omkar/reviews?token=LevSearchApiAll&query=Krasnoyarsk</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/youtube</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🎬 Информация о YouTube видео</div>
                    <div class="endpoint-example">/youtube?token=LevSearchApiAll&url=https://youtube.com/watch?v=dQw4w9WgXcQ</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/veriphone</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📞 Валидация телефона (страна, оператор)</div>
                    <div class="endpoint-example">/veriphone?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/whatsapp</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">💬 Проверка наличия WhatsApp</div>
                    <div class="endpoint-example">/whatsapp?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/odnoklassniki</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">👥 Поиск профиля в Одноклассниках</div>
                    <div class="endpoint-example">/odnoklassniki?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/social</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🔗 Ссылки для поиска в 30+ соцсетях</div>
                    <div class="endpoint-example">/social?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/dorks</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🔍 Google Dorks для номера телефона</div>
                    <div class="endpoint-example">/dorks?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/domain</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">🌐 IP адрес и открытые порты домена</div>
                    <div class="endpoint-example">/domain?token=LevSearchApiAll&name=google.com</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/omkar/phone</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📱 Информация о телефоне через Omkar</div>
                    <div class="endpoint-example">/omkar/phone?token=LevSearchApiAll&phone=79233756070</div>
                </div>
            </div>
            
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="endpoint-method">GET</span>
                    <span class="endpoint-path">/omkar/email</span>
                </div>
                <div class="endpoint-body">
                    <div class="endpoint-desc">📧 Проверка email через Omkar</div>
                    <div class="endpoint-example">/omkar/email?token=LevSearchApiAll&email=test@gmail.com</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>LevSearch API | OSINT инструмент | 🔒 Все запросы логируются | ⚡ Лимиты: LevSearchApiAll - безлимит, 1KSUBS - 500/день</p>
        </div>
    </div>
    
    <script>
        async function testAPI() {
            const query = document.getElementById('queryInput').value;
            const endpoint = document.getElementById('endpointSelect').value;
            const token = document.getElementById('tokenInput').value;
            
            if (!query) {
                alert('Введите запрос');
                return;
            }
            
            let url = endpoint + '?token=' + token;
            
            if (endpoint === '/search' || endpoint === '/leakosint') {
                url += '&q=' + encodeURIComponent(query);
            } else if (endpoint === '/intelx' || endpoint === '/whatsapp' || endpoint === '/odnoklassniki' || endpoint === '/omkar/phone' || endpoint === '/instagram' || endpoint === '/social' || endpoint === '/dorks') {
                url += '&phone=' + encodeURIComponent(query);
            } else if (endpoint === '/whois' || endpoint === '/dns' || endpoint === '/subdomains') {
                url += '&domain=' + encodeURIComponent(query);
            } else if (endpoint === '/vk' || endpoint === '/vk/wall' || endpoint === '/vk/friends' || endpoint === '/vk/groups') {
                url += '&id=' + encodeURIComponent(query);
            } else if (endpoint === '/headers' || endpoint === '/youtube') {
                url += '&url=' + encodeURIComponent(query);
            } else if (endpoint === '/ip') {
                url += '&address=' + encodeURIComponent(query);
            } else if (endpoint === '/card') {
                url += '&bin=' + encodeURIComponent(query);
            } else if (endpoint === '/bank') {
                url += '&inn=' + encodeURIComponent(query);
            } else if (endpoint === '/tiktok' || endpoint === '/telegram') {
                url += '&username=' + encodeURIComponent(query);
            } else if (endpoint === '/email' || endpoint === '/omkar/email') {
                url += '&address=' + encodeURIComponent(query);
            } else if (endpoint === '/omkar/reviews') {
                url += '&query=' + encodeURIComponent(query);
            }
            
            const resultPre = document.getElementById('resultPre');
            resultPre.style.display = 'block';
            resultPre.textContent = 'Загрузка...';
            
            try {
                const response = await fetch(url);
                const data = await response.json();
                resultPre.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                resultPre.textContent = 'Ошибка: ' + error.message;
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_DOC)

# ========== ОСНОВНЫЕ ЭНДПОИНТЫ ==========

@app.route('/search')
def search():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Missing q parameter"}), 400
    
    result = {
        "query": query,
        "type": "phone" if re.search(r'\d', query) else "general",
        "token": token
    }
    
    if re.search(r'\d', query):
        result["intelx"] = get_intelx(query)
        result["veriphone"] = get_veriphone(query)
        result["whatsapp"] = get_whatsapp(query)
        result["odnoklassniki"] = get_odnoklassniki(query)
        result["omkar_phone"] = get_omkar_phone(query)
        result["social_links"] = get_social_links(query)
        result["google_dorks"] = get_google_dorks(query)
    
    if token == TOKEN_MAIN:
        result["leakosint"] = get_leakosint(query)
    else:
        result["leakosint"] = {"error": "LeakOSINT доступен только по токену LevSearchApiAll"}
    
    return jsonify(result)

@app.route('/intelx')
def intelx():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_intelx(phone)
    return jsonify(result)

@app.route('/leakosint')
def leakosint():
    token = request.args.get('token', '')
    if token != TOKEN_MAIN:
        return jsonify({"error": "LeakOSINT доступен только по токену LevSearchApiAll"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Missing q parameter"}), 400
    
    result = get_leakosint(query)
    return jsonify(result)

@app.route('/youtube')
def youtube():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    url = request.args.get('url', '')
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    result = get_youtube_info(url)
    return jsonify(result)

@app.route('/veriphone')
def veriphone():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_veriphone(phone)
    return jsonify(result)

@app.route('/whatsapp')
def whatsapp():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_whatsapp(phone)
    return jsonify(result)

@app.route('/odnoklassniki')
def odnoklassniki():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_odnoklassniki(phone)
    return jsonify(result)

@app.route('/omkar/phone')
def omkar_phone():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_omkar_phone(phone)
    return jsonify(result)

@app.route('/omkar/email')
def omkar_email():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    email = request.args.get('email', '')
    if not email:
        return jsonify({"error": "Missing email parameter"}), 400
    
    result = get_omkar_email(email)
    return jsonify(result)

@app.route('/social')
def social():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_social_links(phone)
    return jsonify(result)

@app.route('/dorks')
def dorks():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_google_dorks(phone)
    return jsonify(result)

@app.route('/bank')
def bank():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    inn = request.args.get('inn', '')
    if not inn:
        return jsonify({"error": "Missing inn parameter"}), 400
    
    bank_name = get_bank_by_inn(inn)
    return jsonify({"inn": inn, "bank": bank_name})

@app.route('/card')
def card():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    bin_number = request.args.get('bin', '')[:6]
    if not bin_number:
        return jsonify({"error": "Missing bin parameter"}), 400
    
    result = get_card_info(bin_number)
    return jsonify(result)

@app.route('/domain')
def domain():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    domain_name = request.args.get('name', '')
    if not domain_name:
        return jsonify({"error": "Missing name parameter"}), 400
    
    result = get_domain_info(domain_name)
    return jsonify(result)

@app.route('/vk')
def vk():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    user_id = request.args.get('id', '')
    if not user_id:
        return jsonify({"error": "Missing id parameter"}), 400
    
    result = get_vk_user(user_id)
    return jsonify(result)

@app.route('/ip')
def ip():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    ip_address = request.args.get('address', '')
    if not ip_address:
        return jsonify({"error": "Missing address parameter"}), 400
    
    result = get_ip_info(ip_address)
    return jsonify(result)

@app.route('/tiktok')
def tiktok():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    username = request.args.get('username', '').replace('@', '').strip()
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    
    result = get_tiktok_user(username)
    return jsonify(result)

@app.route('/instagram')
def instagram():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    result = get_instagram_by_phone(phone)
    return jsonify(result)

@app.route('/email')
def email():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    email_address = request.args.get('address', '')
    if not email_address:
        return jsonify({"error": "Missing address parameter"}), 400
    
    result = get_email_mx(email_address)
    return jsonify(result)

@app.route('/telegram')
def telegram():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    limit_ok, limit_msg = check_limit(token)
    if not limit_ok:
        return jsonify({"error": limit_msg}), 429
    
    username = request.args.get('username', '').replace('@', '').strip()
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    
    result = get_telegram_user(username)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
