"""End-to-end probe: verify .pl.txt playlist + MP3 download chain works on prod."""
import re
import sys
import requests

BID = sys.argv[1] if len(sys.argv) > 1 else "115455"


def imgurl(img_id) -> str:
    return "".join(c + "/" for c in str(img_id))


CDN = "https://vvoqhuz9dcid9zx9.redirectto.cc"
H = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": CDN,
}


def main():
    pl = f"{CDN}/s01/{imgurl(BID)}{BID}.pl.txt"
    print("PL URL:", pl)
    r = requests.get(pl, headers=H, timeout=15)
    print("Status:", r.status_code, "Size:", len(r.content))
    print("First 600:", r.text[:600])
    matches = re.findall(r'"file":"(.*?)"\}', r.text)
    print("MP3 count:", len(matches))
    if not matches:
        return
    raw = matches[0]
    mp3 = raw.replace("\\/", "/").replace("\\", "")
    print("First MP3:", mp3)
    r2 = requests.get(mp3, headers=H, timeout=15, stream=True)
    print(
        "MP3 status:", r2.status_code,
        "CT:", r2.headers.get("Content-Type"),
        "len:", r2.headers.get("Content-Length"),
    )


if __name__ == "__main__":
    main()
