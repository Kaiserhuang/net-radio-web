import os
import sqlite3
import logging
import uvicorn
import xlrd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("DB_PATH", os.path.join(DIR, "net_radio.db"))
EXCEL_PATH = os.path.join(DIR, "radio-list.xls")

stations = []
podcasts = []
categories = []

# Chinese geography → coordinates
GEO = {
    "北京": [39.9042, 116.4074], "上海": [31.2304, 121.4737],
    "天津": [39.3434, 117.3616], "重庆": [29.4316, 106.9123],
    "石家庄": [38.0428, 114.5149], "唐山": [39.6309, 118.1802], "秦皇岛": [39.9454, 119.6004],
    "邯郸": [36.6093, 114.5392], "保定": [38.8676, 115.4899], "廊坊": [39.5378, 116.6838],
    "太原": [37.8706, 112.5489], "大同": [40.0763, 113.3002], "呼和浩特": [40.8422, 111.7498],
    "沈阳": [41.8057, 123.4315], "大连": [38.9140, 121.6147], "鞍山": [41.1082, 122.9960],
    "长春": [43.8961, 125.3215], "吉林": [43.8983, 126.5499], "哈尔滨": [45.8038, 126.5350],
    "齐齐哈尔": [47.3544, 123.9181], "牡丹江": [44.5853, 129.6250],
    "南京": [32.0603, 118.7969], "苏州": [31.2990, 120.5853], "无锡": [31.4904, 120.3117],
    "常州": [31.8118, 119.9748], "南通": [31.9797, 120.8761], "扬州": [32.4074, 119.4146],
    "杭州": [30.2741, 120.1551], "宁波": [29.8671, 121.5449], "温州": [27.9942, 120.6991],
    "嘉兴": [30.7700, 120.7586], "合肥": [31.8206, 117.2272], "芜湖": [31.3536, 118.4329],
    "福州": [26.0745, 119.2965], "厦门": [24.4798, 118.0894], "泉州": [24.8747, 118.6766],
    "南昌": [28.6820, 115.8589], "九江": [29.7063, 115.9955], "济南": [36.6512, 116.9972],
    "青岛": [36.0674, 120.3826], "烟台": [37.4648, 121.4474], "潍坊": [36.7070, 119.1087],
    "郑州": [34.7466, 113.6253], "洛阳": [34.6219, 112.4538], "武汉": [30.5928, 114.3055],
    "宜昌": [30.6919, 111.2866], "长沙": [28.2282, 112.9388], "株洲": [27.8271, 113.1339],
    "广州": [23.1291, 113.2644], "深圳": [22.5431, 114.0579], "珠海": [22.2721, 113.5705],
    "汕头": [23.3793, 116.7084], "佛山": [23.0358, 113.1118], "东莞": [23.0208, 113.7518],
    "南宁": [22.8170, 108.3665], "桂林": [25.2744, 110.2933], "海口": [20.0440, 110.3484],
    "三亚": [18.2528, 109.5120], "成都": [30.5702, 104.0648], "绵阳": [31.4711, 104.6849],
    "贵阳": [26.6470, 106.6302], "昆明": [25.0389, 102.7183], "大理": [25.5916, 100.2295],
    "拉萨": [29.6500, 91.1000], "西安": [34.3416, 108.9398], "宝鸡": [34.3628, 107.2351],
    "兰州": [36.0611, 103.8343], "西宁": [36.6171, 101.7782], "银川": [38.4872, 106.2309],
    "乌鲁木齐": [43.8256, 87.6168], "台北": [25.0330, 121.5654], "高雄": [22.6273, 120.3014],
    "香港": [22.3193, 114.1694], "澳门": [22.1987, 113.5439],
    # Province names (use capital)
    "河北": [38.0428, 114.5149], "山西": [37.8706, 112.5489], "内蒙古": [40.8422, 111.7498],
    "辽宁": [41.8057, 123.4315], "吉林": [42.8961, 125.3215], "黑龙江": [45.8038, 126.5350],
    "江苏": [32.0603, 118.7969], "浙江": [30.2741, 120.1551], "安徽": [31.8206, 117.2272],
    "福建": [26.0745, 119.2965], "江西": [28.6820, 115.8589], "山东": [36.6512, 116.9972],
    "河南": [34.7466, 113.6253], "湖北": [30.5928, 114.3055], "湖南": [28.2282, 112.9388],
    "广东": [23.1291, 113.2644], "广西": [22.8170, 108.3665], "海南": [20.0440, 110.3484],
    "四川": [30.5702, 104.0648], "贵州": [26.6470, 106.6302], "云南": [25.0389, 102.7183],
    "西藏": [29.6500, 91.1000], "陕西": [34.3416, 108.9398], "甘肃": [36.0611, 103.8343],
    "青海": [36.6171, 101.7782], "宁夏": [38.4872, 106.2309], "新疆": [43.8256, 87.6168],
    "台湾": [25.0330, 121.5654],
    # Short forms
    "京": [39.9042, 116.4074], "沪": [31.2304, 121.4737],
    "津": [39.3434, 117.3616], "渝": [29.4316, 106.9123],
    "粤": [23.1291, 113.2644], "闽": [26.0745, 119.2965],
    "浙": [30.2741, 120.1551], "苏": [32.0603, 118.7969],
}
UNKNOWN_COORD = [2.0, -165.0]  # Pacific Ocean center


def parse_excel():
    global stations, podcasts, categories
    wb = xlrd.open_workbook(EXCEL_PATH)

    sh = wb.sheet_by_index(0)
    stations.clear()
    current_province = ""
    for r in range(1, sh.nrows):
        prov = sh.cell_value(r, 0).strip()
        name = sh.cell_value(r, 1).strip()
        raw_url = sh.cell_value(r, 2).strip()
        note = sh.cell_value(r, 3).strip()
        if prov:
            current_province = prov
        if name and raw_url:
            idx = raw_url.rfind(",")
            url = raw_url[idx + 1:].strip() if idx >= 0 else raw_url
            fmt = "hls" if ".m3u8" in url else "mp3"
            geo_name, _ = extract_location(name)
            stations.append({
                "name": name,
                "url": url,
                "format": fmt,
                "province": current_province,
                "geo_name": geo_name,
                "note": note,
                "ref_id": f"station:{len(stations)}"
            })

    podcast_config = [(1, "相声"), (2, "脱口秀")]
    podcasts.clear()
    for sheet_idx, cat_name in podcast_config:
        sh = wb.sheet_by_index(sheet_idx)
        for r in range(sh.nrows):
            raw = sh.cell_value(r, 0).strip()
            if not raw:
                continue
            idx = raw.rfind(",")
            url = raw[idx + 1:].strip() if idx >= 0 else ""
            pod_name = raw[:idx].strip() if idx >= 0 else raw
            fmt = "hls" if ".m3u8" in url else "mp3"
            podcasts.append({
                "name": pod_name,
                "url": url,
                "format": fmt,
                "category": cat_name,
                "ref_id": f"{cat_name}:{len([p for p in podcasts if p['category'] == cat_name])}"
            })

    prov_count = {}
    for s in stations:
        prov_count[s["province"]] = prov_count.get(s["province"], 0) + 1
    categories.clear()
    for p, cnt in sorted(prov_count.items()):
        categories.append({"name": p, "count": cnt, "type": "station"})
    categories.append({"name": "相声", "count": len([p for p in podcasts if p["category"] == "相声"]), "type": "podcast"})
    categories.append({"name": "脱口秀", "count": len([p for p in podcasts if p["category"] == "脱口秀"]), "type": "podcast"})

    log.info("Parsed %d stations, %d podcasts", len(stations), len(podcasts))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            type TEXT NOT NULL,
            ref_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            category TEXT DEFAULT '',
            format TEXT DEFAULT 'hls',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fav_device ON favorites(device_id)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_stations (
            ref_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            format TEXT DEFAULT 'hls',
            province TEXT DEFAULT '',
            note TEXT DEFAULT '',
            geo_name TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deleted_refs (
            ref_id TEXT PRIMARY KEY,
            deleted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def extract_location(name):
    for geo_name in sorted(GEO.keys(), key=len, reverse=True):
        if geo_name in name:
            return geo_name, GEO[geo_name]
    if any(k in name for k in ["CCTV", "央视", "电视"]):
        return "电视伴音", [35.0, 110.0]
    if any(k in name for k in ["中国之声", "CNR", "中央"]):
        return "国家", [35.86, 104.0]
    if any(k in name for k in ["CRI", "中国国际广播"]):
        return "中国国际广播电台", [39.95, 116.4]
    return "未知", list(UNKNOWN_COORD)


parse_excel()
init_db()

app = FastAPI(title="Net Radio Web")


def get_merged_stations():
    conn = sqlite3.connect(DB_PATH)
    deleted = set(r[0] for r in conn.execute("SELECT ref_id FROM deleted_refs").fetchall())
    customs = {}
    for r in conn.execute("SELECT * FROM custom_stations").fetchall():
        customs[r[0]] = {
            "ref_id": r[0], "name": r[1], "url": r[2], "format": r[3],
            "province": r[4], "note": r[5], "geo_name": r[6]
        }
    conn.close()

    items = [s for s in stations if s["ref_id"] not in deleted]
    for i, s in enumerate(items):
        if s["ref_id"] in customs:
            items[i] = {**s, **customs[s["ref_id"]]}
    for cid, c in customs.items():
        if cid not in {s["ref_id"] for s in stations}:
            c["geo_name"] = c.get("geo_name") or extract_location(c["name"])[0]
            items.append(c)
    return items


def rebuild_categories():
    global categories
    merged = get_merged_stations()
    prov_count = {}
    for s in merged:
        prov_count[s["province"]] = prov_count.get(s["province"], 0) + 1
    categories.clear()
    for p, cnt in sorted(prov_count.items()):
        categories.append({"name": p, "count": cnt, "type": "station"})
    categories.append({"name": "相声", "count": len([p for p in podcasts if p["category"] == "相声"]), "type": "podcast"})
    categories.append({"name": "脱口秀", "count": len([p for p in podcasts if p["category"] == "脱口秀"]), "type": "podcast"})


@app.get("/api/station-locations")
def get_station_locations():
    merged = get_merged_stations()
    groups = {}
    for s in merged:
        loc_name, coord = extract_location(s["name"])
        if loc_name not in groups:
            groups[loc_name] = {"name": loc_name, "coord": coord, "count": 0, "stations": []}
        groups[loc_name]["count"] += 1
        groups[loc_name]["stations"].append(s["ref_id"])
    result = sorted(groups.values(), key=lambda x: -x["count"])
    return {"locations": result}


@app.get("/api/categories")
def get_categories():
    return {"categories": categories}


@app.get("/api/stations")
def get_stations(category: str = "", search: str = "", geo: str = ""):
    items = get_merged_stations()
    if category:
        items = [s for s in items if s["province"] == category]
    if geo:
        items = [s for s in items if s["geo_name"] == geo]
    if search:
        q = search.lower()
        items = [s for s in items if q in s["name"].lower()]
    return {"stations": items, "total": len(items)}


class StationIn(BaseModel):
    name: str
    url: str
    format: str = "hls"
    province: str = ""
    note: str = ""


@app.post("/api/stations")
def create_station(st: StationIn):
    import uuid
    ref_id = f"user:{uuid.uuid4().hex[:12]}"
    geo = extract_location(st.name)[0]
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO custom_stations (ref_id, name, url, format, province, note, geo_name) VALUES (?,?,?,?,?,?,?)",
        (ref_id, st.name, st.url, st.format, st.province, st.note, geo)
    )
    conn.commit()
    conn.close()
    rebuild_categories()
    return {"ref_id": ref_id, "message": "created"}


@app.put("/api/stations/{ref_id}")
def update_station(ref_id: str, st: StationIn):
    conn = sqlite3.connect(DB_PATH)
    # Check if it's a custom station
    cur = conn.execute("SELECT 1 FROM custom_stations WHERE ref_id=?", (ref_id,))
    exists = cur.fetchone()
    if exists:
        conn.execute(
            "UPDATE custom_stations SET name=?, url=?, format=?, province=?, note=? WHERE ref_id=?",
            (st.name, st.url, st.format, st.province, st.note, ref_id)
        )
    else:
        # Create an override for an Excel station
        conn.execute(
            "INSERT INTO custom_stations (ref_id, name, url, format, province, note, geo_name) VALUES (?,?,?,?,?,?,?)",
            (ref_id, st.name, st.url, st.format, st.province, st.note, extract_location(st.name)[0])
        )
    conn.commit()
    conn.close()
    rebuild_categories()
    return {"message": "updated"}


@app.delete("/api/stations/{ref_id}")
def delete_station(ref_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO deleted_refs (ref_id) VALUES (?)", (ref_id,))
    conn.execute("DELETE FROM custom_stations WHERE ref_id=?", (ref_id,))
    conn.commit()
    conn.close()
    rebuild_categories()
    return {"message": "deleted"}


@app.get("/api/podcasts")
def get_podcasts(category: str = "", search: str = ""):
    items = podcasts
    if category:
        items = [p for p in items if p["category"] == category]
    if search:
        q = search.lower()
        items = [p for p in items if q in p["name"].lower()]
    return {"podcasts": items, "total": len(items)}


class FavoriteIn(BaseModel):
    device_id: str
    type: str
    ref_id: str
    name: str
    url: str
    category: str = ""
    format: str = "hls"


@app.get("/api/favorites")
def list_favorites(device_id: str = ""):
    if not device_id:
        return {"favorites": []}
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(
        "SELECT * FROM favorites WHERE device_id=? ORDER BY created_at DESC", (device_id,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"favorites": rows}


@app.post("/api/favorites")
def add_favorite(fav: FavoriteIn):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO favorites (device_id, type, ref_id, name, url, category, format) VALUES (?,?,?,?,?,?,?)",
        (fav.device_id, fav.type, fav.ref_id, fav.name, fav.url, fav.category, fav.format)
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return {"id": new_id, "message": "ok"}


@app.delete("/api/favorites/{fav_id}")
def delete_favorite(fav_id: int, device_id: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("DELETE FROM favorites WHERE id=? AND device_id=?", (fav_id, device_id))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if not deleted:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"message": "deleted"}


@app.get("/api/health")
def health():
    return {"status": "ok", "stations": len(stations), "podcasts": len(podcasts)}


static_dir = os.path.join(DIR, "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    log.info("Starting on %s:%s", HOST, PORT)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
