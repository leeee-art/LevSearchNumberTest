from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import socket
import yt_dlp
from urllib.parse import unquote, quote

app = Flask(__name__)
CORS(app)

TOKEN_MAIN = "LevSearchApiAll"
TOKEN_1K = "1KSUBS"
LEAKOSINT_KEY = "8702237281:cYkLAFK4"
VK_TOKEN = "vk1.a.WX465fcyCl3FoFXysIyBPjQYn4D4Cgz3SJAmX7mxXvQBMUzTjzkaZfA0Tt-FBRDuA4WYq7tvbO3TaqZbvdl3oAva367V8KP4AQUFI1kC3I8UnT687rM12Bv-d-Ax9FnXAeOTxMp8MTBUwqQ_6kH-1LAQIT7fgdzWaawG3CEOhe6Q5VSuzTrDFF0iWIrUAXIwT22_uN6XzH25tZCegI-AWQ"
VERIPHONE_KEY = "A9A2A88762854D45888BA49E8F98509C"
OMKAR_API_KEY = "ok_ad50fb80682eff950d34e7a9b3a77c8c"

ALL_TOKENS = [TOKEN_MAIN, TOKEN_1K]

def check_token(token):
    return token in ALL_TOKENS

# ========== YOUTUBE ==========
@app.route('/youtube')
def youtube():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    url = request.args.get('url', '')
    if not url:
        return jsonify({"error": "Missing url parameter"}), 400
    
    ydl_opts = {'quiet': True, 'extract_flat': False}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return jsonify({
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
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

# ========== VERIPHONE ==========
@app.route('/veriphone')
def veriphone():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    phone_clean = re.sub(r'\D', '', phone)
    url = "https://api.veriphone.io/v2/verify"
    params = {"phone": phone_clean, "key": VERIPHONE_KEY}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return jsonify({
                "valid": data.get("valid"),
                "country": data.get("country_code"),
                "carrier": data.get("carrier"),
                "type": data.get("phone_type")
            })
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== WHATSAPP ==========
@app.route('/whatsapp')
def whatsapp():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    phone_clean = re.sub(r'\D', '', phone)
    if phone_clean.startswith('8'):
        phone_clean = '7' + phone_clean[1:]
    elif not phone_clean.startswith('7'):
        phone_clean = '7' + phone_clean
    
    try:
        r = requests.get(f"https://wa.me/{phone_clean}", timeout=10, allow_redirects=True)
        if r.status_code == 200:
            if "This phone number is not on WhatsApp" in r.text:
                return jsonify({"exists": False, "phone": phone_clean})
            else:
                return jsonify({"exists": True, "phone": phone_clean})
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== ODKLASSNIKI ==========
@app.route('/odnoklassniki')
def odnoklassniki():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    phone_clean = re.sub(r'\D', '', phone)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        url = "https://ok.ru/search"
        params = {"st.mode": "Users", "st.query": phone_clean}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            match = re.search(r'num-found["\s]*:["\s]*(\d+)', r.text)
            if match and int(match.group(1)) > 0:
                return jsonify({"exists": True, "phone": phone_clean})
            return jsonify({"exists": False, "phone": phone_clean})
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== OMKAR PHONE ==========
@app.route('/omkar/phone')
def omkar_phone():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    url = "https://carrier-lookup-api.omkar.cloud/lookup"
    params = {"phone": phone}
    headers = {"API-Key": OMKAR_API_KEY}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== OMKAR EMAIL ==========
@app.route('/omkar/email')
def omkar_email():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    email = request.args.get('email', '')
    if not email:
        return jsonify({"error": "Missing email parameter"}), 400
    
    url = "https://email-verification-api.omkar.cloud/verify"
    params = {"email": email}
    headers = {"API-Key": OMKAR_API_KEY}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            return jsonify(r.json())
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== LEAKOSINT ==========
@app.route('/leakosint')
def leakosint():
    token = request.args.get('token', '')
    if token != TOKEN_MAIN:
        return jsonify({"error": "LeakOSINT доступен только по токену LevSearchApiAll"}), 403
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Missing q parameter"}), 400
    
    try:
        r = requests.post('https://leakosintapi.com/', json={'token': LEAKOSINT_KEY, 'request': query}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return jsonify({
                "status": "success",
                "balance": data.get('remaining_balance'),
                "results": data.get('List', {})
            })
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== СОЦИАЛЬНЫЕ СЕТИ (ПОЛНЫЙ СПИСОК) ==========
@app.route('/social')
def social():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    phone_clean = ''.join(filter(str.isdigit, phone))
    links = {
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
    return jsonify({"phone": phone_clean, "links": links})

# ========== GOOGLE DORKS (ПОЛНЫЙ СПИСОК) ==========
@app.route('/dorks')
def dorks():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
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
    
    return jsonify({"phone": phone_clean, "dorks": dork_urls})

# ========== БАНКИ ПО ИНН (ПОЛНЫЙ СПИСОК) ==========
@app.route('/bank')
def bank():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    inn = request.args.get('inn', '')
    if not inn:
        return jsonify({"error": "Missing inn parameter"}), 400
    
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
    return jsonify({"inn": inn, "bank": banks_database.get(inn, "Банк не найден")})

# ========== ПОИСК ПО НОМЕРУ (ВСЁ ВМЕСТЕ) ==========
@app.route('/search')
def search():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Missing q parameter"}), 400
    
    result = {
        "query": query,
        "type": "phone" if re.search(r'\d', query) else "general",
        "token": token
    }
    
    # Veriphone
    phone_clean = re.sub(r'\D', '', query)
    if len(phone_clean) >= 10:
        vp = check_phone_veriphone(query)
        if vp:
            result["veriphone"] = vp
    
    # WhatsApp
    result["whatsapp"] = check_whatsapp(query)
    
    # Odnoklassniki
    result["odnoklassniki"] = check_ok(query)
    
    # Omkar phone
    result["omkar_phone"] = omkar_phone_lookup(query)
    
    # Социальные сети
    result["social_links"] = get_social_links(query)
    
    # Google Dorks
    result["google_dorks"] = get_google_dorks(query)
    
    # LeakOSINT (только для основного токена)
    if token == TOKEN_MAIN:
        result["leakosint"] = get_leakosint(query)
    else:
        result["leakosint"] = {"error": "Доступно только по токену LevSearchApiAll"}
    
    return jsonify(result)

# ========== ОСТАЛЬНЫЕ ЭНДПОИНТЫ ==========
@app.route('/')
def index():
    return jsonify({
        "status": "LevSearch API is running",
        "endpoints": {
            "/search": "?token=LevSearchApiAll&q=79233756070",
            "/youtube": "?token=LevSearchApiAll&url=https://youtube.com/watch?v=...",
            "/veriphone": "?token=LevSearchApiAll&phone=79233756070",
            "/whatsapp": "?token=LevSearchApiAll&phone=79233756070",
            "/odnoklassniki": "?token=LevSearchApiAll&phone=79233756070",
            "/omkar/phone": "?token=LevSearchApiAll&phone=79233756070",
            "/omkar/email": "?token=LevSearchApiAll&email=test@gmail.com",
            "/leakosint": "?token=LevSearchApiAll&q=79233756070",
            "/social": "?token=LevSearchApiAll&phone=79233756070",
            "/dorks": "?token=LevSearchApiAll&phone=79233756070",
            "/bank": "?token=LevSearchApiAll&inn=7707083893",
            "/card": "?token=LevSearchApiAll&bin=477964",
            "/domain": "?token=LevSearchApiAll&name=google.com",
            "/vk": "?token=LevSearchApiAll&id=1",
            "/ip": "?token=LevSearchApiAll&address=8.8.8.8",
            "/tiktok": "?token=LevSearchApiAll&username=marvel",
            "/instagram": "?token=LevSearchApiAll&phone=79233756070",
            "/email": "?token=LevSearchApiAll&address=test@gmail.com",
            "/telegram": "?token=LevSearchApiAll&username=durov"
        }
    })

@app.route('/card')
def card():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    bin_number = request.args.get('bin', '')[:6]
    if not bin_number:
        return jsonify({"error": "Missing bin parameter"}), 400
    
    try:
        r = requests.get(f"https://lookup.binlist.net/{bin_number}", headers={'Accept-Version': '3'}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return jsonify({
                "bin": bin_number,
                "bank": data.get('bank', {}).get('name'),
                "country": data.get('country', {}).get('name'),
                "brand": data.get('scheme'),
                "type": data.get('type')
            })
        return jsonify({"error": f"HTTP {r.status_code}"}), r.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/domain')
def domain():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    domain_name = request.args.get('name', '')
    if not domain_name:
        return jsonify({"error": "Missing name parameter"}), 400
    
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
    
    return jsonify(result)

@app.route('/vk')
def vk():
    token = request.args.get('token', '')
    if not check_token(token)):
        return jsonify({"error": "Invalid token"}), 403
    
    user_id = request.args.get('id', '')
    if not user_id:
        return jsonify({"error": "Missing id parameter"}), 400
    
    try:
        url = "https://api.vk.com/method/users.get"
        params = {
            "access_token": VK_TOKEN,
            "user_ids": user_id,
            "v": "5.131",
            "fields": "first_name,last_name,domain,followers_count,is_closed"
        }
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "response" in data and data["response"]:
                user = data["response"][0]
                return jsonify({
                    "id": user.get("id"),
                    "name": f"{user.get('first_name', '')} {user.get('last_name', '')}",
                    "domain": user.get("domain"),
                    "followers": user.get("followers_count"),
                    "is_closed": user.get("is_closed", False)
                })
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/ip')
def ip():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    ip_address = request.args.get('address', '')
    if not ip_address:
        return jsonify({"error": "Missing address parameter"}), 400
    
    try:
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return jsonify({
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "isp": data.get("isp"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon")
                })
        return jsonify({"error": "IP not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/tiktok')
def tiktok():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    username = request.args.get('username', '').replace('@', '').strip()
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    
    url = f"https://www.tiktok.com/@{username}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            followers_match = re.search(r'"followerCount":(\d+)', response.text)
            followers = int(followers_match.group(1)) if followers_match else 0
            name_match = re.search(r'"nickname":"([^"]+)"', response.text)
            name = name_match.group(1) if name_match else None
            return jsonify({
                "username": username,
                "name": name,
                "followers": followers
            })
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/instagram')
def instagram():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    phone_clean = ''.join(filter(str.isdigit, phone))
    url = f"https://www.google.com/search?q=site:instagram.com+{phone_clean}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and "instagram.com" in response.text:
            username_match = re.search(r'instagram\.com/([a-zA-Z0-9_.]+)', response.text)
            username = username_match.group(1) if username_match else None
            return jsonify({"exists": True, "username": username})
        return jsonify({"exists": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/email')
def email():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    email_address = request.args.get('address', '')
    if not email_address:
        return jsonify({"error": "Missing address parameter"}), 400
    
    email_address = unquote(email_address)
    domain = email_address.split('@')[-1]
    try:
        import subprocess
        result = subprocess.run(['nslookup', '-type=mx', domain], capture_output=True, text=True, timeout=10)
        has_mx = "mail exchanger" in result.stdout
        return jsonify({"email": email_address, "has_mx": has_mx, "domain": domain})
    except:
        return jsonify({"email": email_address, "has_mx": False, "domain": domain})

@app.route('/telegram')
def telegram():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    username = request.args.get('username', '').replace('@', '').strip()
    if not username:
        return jsonify({"error": "Missing username parameter"}), 400
    
    url = f"https://t.me/{username}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            if "If you have Telegram" in response.text or "is not available" in response.text:
                return jsonify({"exists": False, "username": username})
            else:
                return jsonify({"exists": True, "username": username})
        return jsonify({"exists": False, "error": f"HTTP {response.status_code}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
