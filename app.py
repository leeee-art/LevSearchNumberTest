from flask import Flask, request, jsonify
import requests, re, csv, io

app = Flask(__name__)
TOKEN = "LevSearchNumber"

def search_intelx(phone):
    p = re.sub(r'\D', '', phone)
    if len(p) < 8:
        return {"status": "error", "message": "номер слишком короткий"}
    
    url = f'http://data.intelx.io/saverudata/db2/dbpn/{p[:2]}/{p[2:4]}/{p[4:6]}/{p[6:8]}.csv'
    
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = list(csv.reader(io.StringIO(r.text)))
            if len(data) > 1:
                headers = data[0]
                results = []
                for row in data[1:]:
                    if p in ' '.join(row):
                        item = {}
                        for i, cell in enumerate(row):
                            if i < len(headers) and cell:
                                item[headers[i]] = cell
                        results.append(item)
                return {"status": "success", "phone": phone, "results": results}
            return {"status": "empty"}
        return {"status": "error", "code": r.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/search')
def search():
    token = request.args.get('token')
    phone = request.args.get('phone')
    
    if token != TOKEN:
        return jsonify({"error": "Invalid token"}), 403
    if not phone:
        return jsonify({"error": "Missing phone"}), 400
    
    return jsonify(search_intelx(phone))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
