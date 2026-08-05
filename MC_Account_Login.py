import json
import base64
import re
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
PURPLE = "\033[38;2;135;145;216m"
LPURP  = "\033[38;2;180;185;240m"
RED    = "\033[38;2;224;17;95m"
GREEN  = "\033[38;2;80;200;120m"
WHITE  = "\033[97m"
GRAY   = "\033[90m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"

def clr(color, text):
    return f"{color}{text}{RESET}"

def clear():
    os.system("cls" if os.name == "nt" else "clear")

MS_CLIENT_ID = "00000000402b5328"
MS_SCOPE = "service::user.auth.xboxlive.com::MBI_SSL"
DUMMY_REFRESH = "M.C551_BAY.0.U.-CjuETVLq3csyG8QsSNi7HOMsyQ1hD*LubC1O9Kzfpu52LbuvcNlma7C5W*QzDp2Io!Kw5LGOJfqJP9XYnVm42KUk9vHYG7oEa995JLStRBPDRbSYk5dUaaHUfbvG9p!ZLLtOKjuDmof2FP6J59Y8z1UHTxv8Jc3E5I84xj9H7WHzVUeJWjOhRrkme3jwIY8ncVn9EK0v5f34S!*d1GmgqX40E9J!11mS7vKQ2ZRVIFjhl83xHQKVs4!r*qCS1SS3dXAD425tYUOTA6YQriGpel0JTmCXNKbgJfQbZGKTLR2CTlcrpb3uxSvU8SSODznzrj1p8rpNH9aW7S87l64dkNOZTQcAX57LW!sONPJ1IPoP"

def http_post(url, data, headers=None, content_type="application/json"):
    if headers is None:
        headers = {}
    if content_type == "application/json":
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = data.encode() if isinstance(data, str) else data
        headers["Content-Type"] = content_type
    headers["Accept"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:300] if e.fp else ""
        print(clr(RED, f"    HTTP {e.code}: {err}"))
        return None
    except Exception as e:
        print(clr(RED, f"    Error: {e}"))
        return None

def http_get(url, headers=None):
    if headers is None:
        headers = {}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(clr(RED, f"    HTTP {e.code}"))
        return None
    except Exception as e:
        print(clr(RED, f"    Error: {e}"))
        return None

def is_jwt(text):
    return bool(re.fullmatch(r'ey[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+', text.strip()))

def is_msa_refresh(text):
    t = text.strip()
    return t.startswith("M.") and len(t) > 50

def extract_refresh_from_cookie(text):
    match = re.search(r'(M\.[A-Za-z0-9_\-.*!]+)', text)
    if match:
        return match.group(1)
    return None

def decode_jwt(token):
    try:
        p = token.split('.')[1]
        p += '=' * (4 - len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception:
        return {}

def msa_refresh_to_ms_token(refresh_token):
    print(clr(GRAY, "    [1/4] Exchanging MSA refresh token..."))
    data = (
        f"client_id={MS_CLIENT_ID}"
        f"&refresh_token={urllib.parse.quote(refresh_token)}"
        f"&grant_type=refresh_token"
        f"&scope={urllib.parse.quote(MS_SCOPE)}"
    )
    result = http_post(
        "https://login.live.com/oauth20_token.srf",
        data,
        content_type="application/x-www-form-urlencoded"
    )
    if result and "access_token" in result:
        print(clr(GREEN, "    ✓ Got MS access token"))
        return result["access_token"], result.get("refresh_token", refresh_token)
    print(clr(RED, "    ✗ Failed — token may be expired"))
    return None, None

def ms_token_to_xbox(ms_token):
    print(clr(GRAY, "    [2/4] Xbox Live auth..."))
    result = http_post("https://user.auth.xboxlive.com/user/authenticate", {
        "Properties": {
            "AuthMethod": "RPS",
            "SiteName": "user.auth.xboxlive.com",
            "RpsTicket": ms_token
        },
        "RelyingParty": "http://auth.xboxlive.com",
        "TokenType": "JWT"
    })
    if result and "Token" in result:
        uhs = result["DisplayClaims"]["xui"][0]["uhs"]
        print(clr(GREEN, f"    ✓ Xbox token (uhs: {uhs})"))
        return result["Token"], uhs
    print(clr(RED, "    ✗ Xbox auth failed"))
    return None, None

def xbox_to_xsts(xbox_token):
    print(clr(GRAY, "    [3/4] XSTS token..."))
    result = http_post("https://xsts.auth.xboxlive.com/xsts/authorize", {
        "Properties": {
            "SandboxId": "RETAIL",
            "UserTokens": [xbox_token]
        },
        "RelyingParty": "rp://api.minecraftservices.com/",
        "TokenType": "JWT"
    })
    if result and "Token" in result:
        print(clr(GREEN, "    ✓ XSTS token"))
        return result["Token"]
    print(clr(RED, "    ✗ XSTS failed"))
    return None

def xsts_to_minecraft(xsts_token, uhs):
    print(clr(GRAY, "    [4/4] Minecraft token..."))
    result = http_post("https://api.minecraftservices.com/authentication/login_with_xbox", {
        "identityToken": f"XBL3.0 x={uhs};{xsts_token}"
    })
    if result and "access_token" in result:
        print(clr(GREEN, "    ✓ Minecraft access token"))
        return result["access_token"]
    print(clr(RED, "    ✗ Minecraft auth failed"))
    return None

def get_mc_profile(mc_token):
    result = http_get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers={"Authorization": f"Bearer {mc_token}"}
    )
    if result and "id" in result and "name" in result:
        return result["id"], result["name"]
    return None, None

def resolve_token(raw_input):
    text = raw_input.strip()

    if is_jwt(text):
        print(clr(GREEN, "  Detected: MC access token (JWT)"))
        return text

    if is_msa_refresh(text):
        print(clr(GREEN, "  Detected: MSA refresh token"))
        print()
        ms_token, _ = msa_refresh_to_ms_token(text)
        if not ms_token:
            return None
        xbox_token, uhs = ms_token_to_xbox(ms_token)
        if not xbox_token:
            return None
        xsts_token = xbox_to_xsts(xbox_token)
        if not xsts_token:
            return None
        return xsts_to_minecraft(xsts_token, uhs)

    refresh = extract_refresh_from_cookie(text)
    if refresh:
        print(clr(GREEN, "  Detected: Cookie (extracted refresh token)"))
        print()
        ms_token, _ = msa_refresh_to_ms_token(refresh)
        if not ms_token:
            return None
        xbox_token, uhs = ms_token_to_xbox(ms_token)
        if not xbox_token:
            return None
        xsts_token = xbox_to_xsts(xbox_token)
        if not xsts_token:
            return None
        return xsts_to_minecraft(xsts_token, uhs)

    print(clr(RED, "  ✗ Unrecognized token format"))
    return None

def get_lunar_path():
    return Path.home() / ".lunarclient" / "settings" / "game" / "accounts.json"

def add_to_lunar(mc_token, uuid, username):
    path = get_lunar_path()
    data = {"accounts": {}}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass

    if "accounts" not in data:
        data["accounts"] = {}

    claims = decode_jwt(mc_token)
    xuid = claims.get("xuid", "")
    sub = claims.get("sub", "")
    local_id = sub.replace("-", "") or uuid
    expires_at = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    entry = {
        "accessToken": mc_token,
        "accessTokenExpiresAt": expires_at,
        "eligibleForMigration": False,
        "hasMultipleProfiles": False,
        "legacy": False,
        "persistent": True,
        "userProperites": [],
        "localId": local_id,
        "refreshToken": DUMMY_REFRESH,
        "minecraftProfile": {
            "id": uuid,
            "name": username,
        },
        "remoteId": xuid,
        "type": "Xbox",
        "username": username,
    }

    data["accounts"][local_id] = entry
    data["activeAccountLocalId"] = local_id

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(clr(GREEN, f"    ✓ Added to Lunar Client as active account"))
    print(clr(GRAY, f"    Path: {path}"))

def print_banner():
    clear()
    print()
    print(clr(PURPLE, "  ╔═══════════════════════════════════════════════╗"))
    print(clr(PURPLE, "  ║") + clr(WHITE, "       MC Account Manager                    ") + clr(PURPLE, "║"))
    print(clr(PURPLE, "  ║") + clr(GRAY,  "       Lunar Client                          ") + clr(PURPLE, "║"))
    print(clr(PURPLE, "  ╚═══════════════════════════════════════════════╝"))
    print()

def add_account():
    print()
    print(clr(CYAN, "  Paste your token (JWT, MSA refresh, or cookie):"))
    print()
    raw = input(clr(PURPLE, "  ❯ ")).strip()
    print()

    mc_token = resolve_token(raw)
    if not mc_token:
        input(clr(GRAY, "\n  Press enter to continue..."))
        return

    print()
    print(clr(GRAY, "  Fetching profile..."))
    uuid, username = get_mc_profile(mc_token)
    if not uuid:
        print(clr(RED, "  ✗ Could not fetch profile. Token expired?"))
        input(clr(GRAY, "\n  Press enter to continue..."))
        return

    print()
    print(clr(GREEN, f"  ✓ {username} ({uuid})"))
    print()
    print(clr(CYAN, "  Add to Lunar Client?"))
    print(clr(WHITE, "    [1] Yes"))
    print(clr(WHITE, "    [2] No (just show token)"))
    print()

    choice = input(clr(PURPLE, "  ❯ ")).strip()
    print()

    if choice == "1":
        add_to_lunar(mc_token, uuid, username)
    else:
        print(clr(WHITE, f"    Token: {mc_token}"))
        print(clr(WHITE, f"    UUID: {uuid}"))
        print(clr(WHITE, f"    Username: {username}"))

    print()
    input(clr(GRAY, "  Press enter to continue..."))

def view_lunar_accounts():
    path = get_lunar_path()
    if not path.exists():
        print(clr(GRAY, "  No Lunar accounts found."))
        input(clr(GRAY, "\n  Press enter to continue..."))
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("accounts", {})
    if not accounts:
        print(clr(GRAY, "  No accounts saved."))
    else:
        print(clr(CYAN, f"  Lunar Client — {len(accounts)} account(s)"))
        print()
        for uid, acc in accounts.items():
            name = acc.get("username", "Unknown")
            mc_id = acc.get("minecraftProfile", {}).get("id", "")
            exp = acc.get("accessTokenExpiresAt", "?")
            print(clr(WHITE, f"    {name}") + clr(GRAY, f"  |  {mc_id}  |  expires: {exp}"))
        print()

    input(clr(GRAY, "  Press enter to continue..."))

def remove_lunar_account():
    path = get_lunar_path()
    if not path.exists():
        print(clr(GRAY, "  No Lunar accounts found."))
        input(clr(GRAY, "\n  Press enter to continue..."))
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = data.get("accounts", {})
    if not accounts:
        print(clr(GRAY, "  No accounts."))
        input(clr(GRAY, "\n  Press enter to continue..."))
        return

    entries = list(accounts.items())
    print(clr(CYAN, "  Select account to remove:"))
    print()
    for i, (uid, acc) in enumerate(entries, 1):
        name = acc.get("username", "Unknown")
        print(clr(WHITE, f"    [{i}] {name}"))
    print()

    choice = input(clr(PURPLE, "  ❯ ")).strip()
    try:
        idx = int(choice) - 1
        key = entries[idx][0]
        name = accounts[key].get("username", "Unknown")
        del data["accounts"][key]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(clr(GREEN, f"  ✓ Removed {name}"))
    except:
        print(clr(RED, "  Invalid selection"))

    input(clr(GRAY, "\n  Press enter to continue..."))

def main():
    while True:
        print_banner()
        print(clr(WHITE, "    [1] Add Account"))
        print(clr(WHITE, "    [2] View Accounts"))
        print(clr(WHITE, "    [3] Remove Account"))
        print(clr(WHITE, "    [4] Exit"))
        print()

        choice = input(clr(PURPLE, "  ❯ ")).strip()

        if choice == "1":
            add_account()
        elif choice == "2":
            view_lunar_accounts()
        elif choice == "3":
            remove_lunar_account()
        elif choice == "4":
            clear()
            print(clr(PURPLE, "\n  ✦ goodbye ✦\n"))
            sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(clr(GRAY, "\n  Interrupted."))
        sys.exit(0)
