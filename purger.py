import aiohttp
import asyncio
import shutil
import random
from datetime import datetime

# --- CONFIGURATION ---
# Paste your token between the quotes below
USER_TOKEN = "YOUR_TOKEN_HERE"
GITHUB_LINK = "https://github.com/vouchings"

# --- STYLE SETTINGS ---
PRIMARY = "\033[95m"  # Light Magenta/Purple
SUCCESS = "\033[92m"  # Green
WARNING = "\033[93m"  # Yellow
ERROR = "\033[91m"    # Red
RESET = "\033[0m"

class DiscordPurger:
    def __init__(self, token):
        self.token = token
        self.api_base = "https://discord.com/api/v10"
        self.headers = {
            'Authorization': self.token,
            'Content-Type': 'application/json',
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        }
        self.stats = {"success": 0, "failed": 0}

    async def _handle_request(self, session, method, endpoint, **kwargs):
        url = f"{self.api_base}{endpoint}"
        async with session.request(method, url, headers=self.headers, **kwargs) as resp:
            if resp.status == 429:
                retry_data = await resp.json()
                wait_time = retry_data.get('retry_after', 2)
                print(f"{WARNING}[!] API Overload: Sleeping {wait_time}s...{RESET}")
                await asyncio.sleep(wait_time)
                return await self._handle_request(session, method, endpoint, **kwargs)

            if resp.status in [200, 204]:
                return await resp.json() if resp.status == 200 else True
            return None

    async def fetch_user_id(self, session):
        user_data = await self._handle_request(session, 'GET', '/users/@me')
        return user_data['id'] if user_data else None

    async def get_my_messages(self, session, channel_id, user_id, limit):
        found_messages = []
        last_id = None
        
        while len(found_messages) < limit:
            params = {'limit': 100}
            if last_id: params['before'] = last_id
            
            batch = await self._handle_request(session, 'GET', f'/channels/{channel_id}/messages', params=params)
            if not batch: break
            
            my_batch = [m for m in batch if m['author']['id'] == user_id]
            found_messages.extend(my_batch)
            last_id = batch[-1]['id']
            
            print(f"[*] Scanning history... Targets found: {len(found_messages)}", end='\r')
            if len(batch) < 100: break
            
        return found_messages[:limit]

    async def start_purge(self, session, channel_id, messages):
        for msg in messages:
            msg_id = msg['id']
            success = await self._handle_request(session, 'DELETE', f'/channels/{channel_id}/messages/{msg_id}')
            
            if success:
                self.stats["success"] += 1
                status = f"{SUCCESS}DONE{RESET}"
            else:
                self.stats["failed"] += 1
                status = f"{ERROR}FAIL{RESET}"
                
            print(f"[{status}] ID: {msg_id} | Total: {self.stats['success']}/{len(messages)}", end='\r')
            
            # Humanized delay logic
            await asyncio.sleep(0.4 + random.uniform(0.1, 0.5))

async def main():
    cols = shutil.get_terminal_size().columns
    
    # Header UI
    print(f"\n{PRIMARY}{' -= DISCORD PURGER =- '.center(cols)}{RESET}")
    print(f"{PRIMARY}{GITHUB_LINK.center(cols)}{RESET}")
    print(f"{PRIMARY}{'—' * 40}".center(cols))

    async with aiohttp.ClientSession() as session:
        purger = DiscordPurger(USER_TOKEN)
        user_id = await purger.fetch_user_id(session)
        
        if not user_id:
            print(f"{ERROR}[!] Could not verify token. Please check USER_TOKEN.{RESET}".center(cols))
            return

        print(f"{SUCCESS}[+] Logged in as: {user_id}{RESET}".center(cols))
        print("\n" + "—" * 40)
        
        channel_id = input(f"{PRIMARY}Target Channel ID:{RESET} ").strip()
        try:
            limit = int(input(f"{PRIMARY}Purge Limit (default 50):{RESET} ") or 50)
        except ValueError:
            limit = 50

        print(f"[*] Initializing deep scan...")
        targets = await purger.get_my_messages(session, channel_id, user_id, limit)
        
        if not targets:
            print(f"\n{WARNING}[!] No messages found for your user in this channel.{RESET}")
            return

        print(f"\n{WARNING}[?] Found {len(targets)} messages. Start deletion? (y/n):{RESET} ", end="")
        if input().lower() == 'y':
            print(f"[*] Purge sequence engaged...")
            await purger.start_purge(session, channel_id, targets)
            print(f"\n\n{SUCCESS}Task Complete. {purger.stats['success']} messages removed.{RESET}")
        else:
            print(f"{ERROR}Sequence cancelled.{RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{ERROR}[!] Interrupted by user. Closing session.{RESET}")