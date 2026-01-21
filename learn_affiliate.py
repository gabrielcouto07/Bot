# learn_affiliate.py
import asyncio
import json
import time
import re
from pathlib import Path
from playwright.async_api import async_playwright

TEMPLATE_PATH = Path("./ml_affiliate_template.json")
DUMP_PATH = Path("./ml_affiliate_network_dump.json")

SEC_RE = re.compile(r"https?://[^\s<>'\"]*mercadolivre\.com/[^\s<>'\"]*/sec/[A-Za-z0-9]+", re.IGNORECASE)
ITEM_RE = re.compile(r"\bMLB-?\d+\b", re.IGNORECASE)

HINT_WORDS = (
    "afiliad", "affiliate", "link", "deeplink", "short", "share",
    "token", "tracking", "graphql", "recommend", "recomend", "promoter"
)

# 🔧 Use o MESMO profile que você usa no bot
CHROME_USER_DATA_DIR = r"C:\Users\GABRIEL.CARDOSO\AppData\Local\BotChromeProfile"
CHROME_PROFILE_DIR_NAME = "Default"


def _filter_headers(headers: dict) -> dict:
    # NÃO salva cookies (Playwright usa os cookies do contexto logado)
    drop = {
        "cookie", "content-length", "host", "accept-encoding", "connection",
        "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    }
    out = {}
    for k, v in (headers or {}).items():
        if k.lower() in drop:
            continue
        out[k] = v
    return out


def _is_interesting(url: str, post_data: str | None) -> bool:
    u = (url or "").lower()
    if any(w in u for w in HINT_WORDS):
        return True
    pd = (post_data or "").lower()
    if "/sec/" in pd or "mlb" in pd or any(w in pd for w in ("afiliad", "link", "token", "graphql")):
        return True
    return False


def _score(entry: dict, sample_url: str, sample_item: str | None) -> int:
    score = 0
    url = (entry.get("url") or "").lower()
    pd = (entry.get("post_data") or "").lower()
    snippet = (entry.get("response_snippet") or "").lower()

    if entry.get("found_sec"):
        score += 1000
    if sample_url and sample_url.lower() in pd:
        score += 400
    if sample_item and sample_item.lower() in pd:
        score += 400
    if "/sec/" in pd:
        score += 250
    if any(w in url for w in HINT_WORDS):
        score += 120
    if any(w in snippet for w in ("sec/", "mercadolivre.com/sec")):
        score += 300
    if entry.get("method") == "POST":
        score += 30
    st = entry.get("status") or 0
    if 200 <= st < 300:
        score += 10
    return score


async def _resolve_final_and_item(page, url: str) -> tuple[str, str | None]:
    try:
        r = await page.request.get(url, timeout=60000)
        final_url = r.url or url
    except Exception:
        final_url = url

    m = ITEM_RE.search(final_url or "")
    item = m.group(0).upper() if m else None
    return final_url, item


async def _replay_and_find_sec(page, entry: dict) -> str | None:
    method = (entry.get("method") or "GET").upper()
    url = entry.get("url") or ""
    headers = entry.get("headers") or {}
    post_data = entry.get("post_data")

    try:
        if method == "POST":
            resp = await page.request.post(url, headers=headers, data=post_data, timeout=60000)
        elif method == "PUT":
            resp = await page.request.put(url, headers=headers, data=post_data, timeout=60000)
        else:
            resp = await page.request.get(url, headers=headers, timeout=60000)

        if not resp.ok:
            return None

        # tenta json
        try:
            js = await resp.json()
            sec = _find_sec_any(js)
            if sec:
                return sec
        except Exception:
            pass

        txt = await resp.text()
        m = SEC_RE.search(txt or "")
        return m.group(0) if m else None

    except Exception:
        return None


def _find_sec_any(obj):
    if obj is None:
        return None
    if isinstance(obj, str):
        m = SEC_RE.search(obj)
        return m.group(0) if m else None
    if isinstance(obj, dict):
        for v in obj.values():
            got = _find_sec_any(v)
            if got:
                return got
        return None
    if isinstance(obj, list):
        for v in obj:
            got = _find_sec_any(v)
            if got:
                return got
        return None
    return None


async def learn(sample_url: str):
    events: list[dict] = []
    found_template = asyncio.get_running_loop().create_future()

    async def on_response(resp):
        if found_template.done():
            return

        req = resp.request
        rtype = req.resource_type  # xhr/fetch/other...

        # foco em xhr/fetch (mas sem matar outros)
        if rtype not in ("xhr", "fetch", "other"):
            return

        try:
            url = req.url
            method = req.method
            headers = _filter_headers(req.headers)
            post_data = req.post_data
            status = resp.status

            snippet = ""
            found_sec = False

            # tentar ler o body (se falhar, não aborta)
            try:
                txt = await resp.text()
                snippet = (txt or "")[:1200]
                found_sec = bool(SEC_RE.search(txt or ""))
            except Exception:
                snippet = ""

            entry = {
                "ts": time.time(),
                "resource_type": rtype,
                "method": method,
                "url": url,
                "status": status,
                "headers": headers,
                "post_data": post_data,
                "response_snippet": snippet,
                "found_sec": found_sec,
            }
            events.append(entry)

            # log enxuto
            if found_sec or _is_interesting(url, post_data):
                tag = "✅" if found_sec else "…"
                print(f"[NET]{tag} {method} {status} {rtype} {url[:140]}")

            # se já viu /sec/ na resposta: capturou
            if found_sec and not found_template.done():
                found_template.set_result(entry)

        except Exception:
            return

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                f"--profile-directory={CHROME_PROFILE_DIR_NAME}",
                "--start-maximized",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
            ],
        )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.on("response", lambda r: asyncio.create_task(on_response(r)))

        print("\n[LEARN] Abrindo:", sample_url)
        await page.goto(sample_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1200)

        print("\n[LEARN] Faça MANUALMENTE (pra forçar a request):")
        print("  1) clique 'Compartilhar'")
        print("  2) clique 'Gerar link / ID de produto'")
        print("  3) clique no ícone de copiar do 'Link do produto'")
        print("  4) IMPORTANTÍSSIMO: clique no dropdown 'Etiqueta em uso' e selecione a MESMA etiqueta de novo")
        print("     (isso quase sempre força uma XHR nova)\n")

        # espera achar /sec/ em alguma response
        entry = None
        try:
            entry = await asyncio.wait_for(found_template, timeout=180)
        except asyncio.TimeoutError:
            entry = None

        # resolve final url + item pra ajudar substituições no template
        final_url, item_id = await _resolve_final_and_item(page, sample_url)

        # se achou direto
        if entry:
            template = {
                "captured_at": int(time.time()),
                "method": entry["method"],
                "url": entry["url"],
                "headers": entry["headers"],
                "post_data": entry["post_data"],
                "sample_url": sample_url,
                "sample_final_url": final_url,
                "sample_item_id": item_id,
                "sample_response_snippet": entry.get("response_snippet", "")[:500],
            }
            TEMPLATE_PATH.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
            print("\n✅ Template salvo em:", str(TEMPLATE_PATH))
            return

        # se não achou /sec/ em resposta: tenta replay nas melhores candidatas
        print("\n[LEARN] Não achei /sec/ direto na response. Vou tentar replay das melhores XHRs...")
        # salva dump pra você ter sempre o log
        DUMP_PATH.write_text(json.dumps(events[-250:], ensure_ascii=False, indent=2), encoding="utf-8")
        print("   📄 Dump salvo em:", str(DUMP_PATH))

        # rank
        ranked = sorted(
            events,
            key=lambda e: _score(e, sample_url, item_id),
            reverse=True
        )

        for cand in ranked[:12]:
            sec = await _replay_and_find_sec(page, cand)
            if sec:
                print("\n✅ Achei /sec/ via replay:", sec)
                template = {
                    "captured_at": int(time.time()),
                    "method": cand["method"],
                    "url": cand["url"],
                    "headers": cand["headers"],
                    "post_data": cand["post_data"],
                    "sample_url": sample_url,
                    "sample_final_url": final_url,
                    "sample_item_id": item_id,
                    "sample_response_snippet": (cand.get("response_snippet") or "")[:500],
                }
                TEMPLATE_PATH.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
                print("✅ Template salvo em:", str(TEMPLATE_PATH))
                return

        print("\n❌ Não consegui descobrir a request certa ainda.")
        print("➡️ Envie o arquivo ml_affiliate_network_dump.json que eu te devolvo o parser/template exato.")
        return


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://mercadolivre.com.br"
    asyncio.run(learn(url))