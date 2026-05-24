# app.py для Render
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import socket
import dns.resolver
from urllib.parse import unquote, quote

app = Flask(__name__)
CORS(app)

TOKEN_MAIN = "LevSearchApiAll"
TOKEN_1K = "1KSUBS"
LEAKOSINT_KEY = "8702237281:cYkLAFK4"
VK_TOKEN = "vk1.a.WX465fcyCl3FoFXysIyBPjQYn4D4Cgz3SJAmX7mxXvQBMUzTjzkaZfA0Tt-FBRDuA4WYq7tvbO3TaqZbvdl3oAva367V8KP4AQUFI1kC3I8UnT687rM12Bv-d-Ax9FnXAeOTxMp8MTBUwqQ_6kH-1LAQIT7fgdzWaawG3CEOhe6Q5VSuzTrDFF0iWIrUAXIwT22_uN6XzH25tZCegI-AWQ"

ALL_TOKENS = [TOKEN_MAIN, TOKEN_1K]

def check_token(token):
    return token in ALL_TOKENS

# ========== HTMLWEB.RU ==========
def get_htmlweb_info(phone):
    phone_clean = re.sub(r'\D', '', phone)
    if len(phone_clean) < 10:
        return {"error": "Неверный номер"}
    
    geo_url = f"https://htmlweb.ru/geo/api.php?json&telcod={phone_clean[:4]}"
    operator_url = f"https://htmlweb.ru/json/mnp/phone/{phone_clean}"
    
    result = {}
    try:
        r = requests.get(geo_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            result["geo"] = {
                "country": data.get('country', {}).get('name') if isinstance(data.get('country'), dict) else data.get('country'),
                "region": data.get('region', {}).get('name') if isinstance(data.get('region'), dict) else data.get('region'),
                "city": data.get('0', {}).get('city') if '0' in data else data.get('city'),
                "latitude": data.get('0', {}).get('latitude') if '0' in data else data.get('latitude'),
                "longitude": data.get('0', {}).get('longitude') if '0' in data else data.get('longitude'),
                "timezone": data.get('time_zone'),
                "mobile": data.get('mobile', False)
            }
    except:
        pass
    
    try:
        r = requests.get(operator_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == 200:
                result["operator"] = {
                    "name": data.get('oper', {}).get('name'),
                    "brand": data.get('oper', {}).get('brand'),
                    "ported": data.get('oper_from') is not None
                }
    except:
        pass
    
    return result

# ========== LEAKOSINT ==========
def get_leakosint(query):
    try:
        r = requests.post('https://leakosintapi.com/', json={'token': LEAKOSINT_KEY, 'request': query}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            return {
                "balance": data.get('remaining_balance'),
                "results": data.get('List', {})
            }
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# ========== СОЦИАЛЬНЫЕ СЕТИ (ПОЛНЫЙ СПИСОК) ==========
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

# ========== GOOGLE DORKS (ПОЛНЫЙ СПИСОК) ==========
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

# ========== БАНКИ ПО ИНН (ПОЛНЫЙ СПИСОК) ==========
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

# ========== ЕДИНЫЙ ПОИСК ==========
@app.route('/search')
def unified_search():
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
    
    # HTMLWeb.ru
    result["htmlweb"] = get_htmlweb_info(query)
    
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

# ========== БАНК ПО ИНН (отдельный эндпоинт) ==========
@app.route('/bank')
def bank_by_inn():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    inn = request.args.get('inn', '')
    if not inn:
        return jsonify({"error": "Missing inn parameter"}), 400
    
    bank_name = get_bank_by_inn(inn)
    return jsonify({"inn": inn, "bank": bank_name})

# ========== LEAKOSINT (отдельный эндпоинт) ==========
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

# ========== ОСТАЛЬНЫЕ ЭНДПОИНТЫ ==========
@app.route('/')
def index():
    return jsonify({
        "status": "LevSearch API is running",
        "endpoints": {
            "/search": "?token=LevSearchApiAll&q=79233756070",
            "/leakosint": "?token=LevSearchApiAll&q=79233756070",
            "/card": "?token=LevSearchApiAll&bin=477964",
            "/domain": "?token=LevSearchApiAll&name=google.com",
            "/vk": "?token=LevSearchApiAll&id=1",
            "/ip": "?token=LevSearchApiAll&address=8.8.8.8",
            "/tiktok": "?token=LevSearchApiAll&username=marvel",
            "/instagram": "?token=LevSearchApiAll&phone=79233756070",
            "/email": "?token=LevSearchApiAll&address=test@gmail.com",
            "/telegram": "?token=LevSearchApiAll&username=durov",
            "/bank": "?token=LevSearchApiAll&inn=7707083893",
            "/dorks": "?token=LevSearchApiAll&phone=79233756070",
            "/links": "?token=LevSearchApiAll&phone=79233756070"
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
    
    domain = request.args.get('name', '')
    if not domain:
        return jsonify({"error": "Missing domain parameter"}), 400
    
    result = {"domain": domain}
    try:
        result["ip"] = socket.gethostbyname(domain)
    except:
        result["ip"] = None
    
    common_ports = [21, 22, 25, 80, 443, 3306, 5432, 8080]
    open_ports = []
    for port in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            if s.connect_ex((domain, port)) == 0:
                open_ports.append(port)
            s.close()
        except:
            pass
    result["open_ports"] = open_ports
    
    dns_records = {}
    for q in ['A', 'MX', 'NS', 'TXT']:
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '1.1.1.1']
            answers = resolver.resolve(domain, q)
            dns_records[q] = [str(r) for r in answers]
        except:
            dns_records[q] = []
    result["dns"] = dns_records
    
    return jsonify(result)

@app.route('/vk')
def vk():
    token = request.args.get('token', '')
    if not check_token(token):
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
    
    ip = request.args.get('address', '')
    if not ip:
        return jsonify({"error": "Missing address parameter"}), 400
    
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
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
    if not check_token(token)):
        return jsonify({"error": "Invalid token"}), 403
    
    email = request.args.get('address', '')
    if not email:
        return jsonify({"error": "Missing address parameter"}), 400
    
    email = unquote(email)
    domain = email.split('@')[-1]
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '1.1.1.1']
        resolver.resolve(domain, 'MX')
        return jsonify({"email": email, "has_mx": True, "domain": domain})
    except:
        return jsonify({"email": email, "has_mx": False, "domain": domain})

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

@app.route('/dorks')
def dorks():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    dorks_list = get_google_dorks(phone)
    return jsonify({"phone": phone, "dorks": dorks_list})

@app.route('/links')
def links():
    token = request.args.get('token', '')
    if not check_token(token):
        return jsonify({"error": "Invalid token"}), 403
    
    phone = request.args.get('phone', '')
    if not phone:
        return jsonify({"error": "Missing phone parameter"}), 400
    
    links_list = get_social_links(phone)
    return jsonify({"phone": phone, "links": links_list})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
