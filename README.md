# Lunar Account Switcher

A simple CLI tool to add Minecraft accounts to Lunar Client.

## What it does

- Accepts MC access tokens (JWT), MSA refresh tokens, or cookies
- Authenticates through the Xbox Live / Minecraft flow
- Adds the account directly to Lunar Client's `accounts.json`
- View and remove saved accounts

## Usage

```
python MC_Account_Login.py
```

Then follow the menu:

1. **Add Account** — paste your token and it handles the rest
2. **View Accounts** — see all accounts currently saved in Lunar
3. **Remove Account** — delete an account from Lunar
4. **Exit**

## Requirements

- Python 3.6+
- No external libraries needed (uses only the standard library)

## Install

```
git clone https://github.com/LilForkHatesYou/Lunar-Account-Switcher.git
cd Lunar-Account-Switcher
python MC_Account_Login.py
```

## Notes

- Lunar Client must be closed when adding/removing accounts for changes to take effect.
- Tokens expire — you'll need to re-add accounts periodically.
- Works on Windows, macOS, and Linux.
