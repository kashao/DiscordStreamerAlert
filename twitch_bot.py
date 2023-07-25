
import json
import time
import requests
from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from datetime import datetime
import pytz

class TwitchBot:
    def __init__(self, cfg, db_manager):
        self.cfg = cfg
        self.db_manager = db_manager

    def read_json(self, file_path):
        with open(file_path, 'r', encoding="utf-8") as file:
            data = json.load(file)
        return data

    def write_json(self, file_path, data):
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file)

    def check_token(self):
        try:
            token_data = self.read_json('token.json')
            expiration_time = token_data["create_date"] + token_data["expires_in"]
            if time.time() > expiration_time:
                # if token is expired, fetch a new one
                token_data = self.fetch_new_token()
        except FileNotFoundError:
            # if token.json does not exist, fetch a new token
            token_data = self.fetch_new_token()
        return token_data["access_token"]

    def fetch_new_token(self):
        params = {
            "client_id": self.cfg['twitch']['client_id'],
            "client_secret": self.cfg['twitch']['client_secret'],
            "grant_type": "client_credentials",
            "redirect_uri": self.cfg['twitch']['redirect_uri']
        }
        response = requests.post(self.cfg['twitch']['token_url'], params=params, timeout=30)
        if response.status_code == 200:
            token_data = response.json()
            token_data["create_date"] = int(time.time())
            self.write_json("token.json", token_data)
        else:
            raise Exception('Failed to fetch new token')
        return token_data
    
    async def check_user(self, user):
        access_token = self.check_token()
        api_headers = {
            'Authorization': f"Bearer {access_token}",
            'Client-Id': self.cfg['twitch']['client_id']
        }
        self.twitch = await Twitch(self.cfg['twitch']['client_id'], self.cfg['twitch']['client_secret'])
        try:
            user_info = await first(self.twitch.get_users(logins=user))
            userid = user_info.id
            url = self.cfg['twitch']['user_api'].format(userid)
            req = requests.Session().get(url, headers=api_headers)
            jsondata = req.json()
            if 'error' in jsondata and jsondata['message'] == 'Invalid OAuth token':
                access_token = self.fetch_new_token()  # regenerate the token
                api_headers['Authorization'] = f"Bearer {access_token}"  # update the headers
                req = requests.Session().get(url, headers=api_headers)  # retry the request
                jsondata = req.json()  # get the new response
            if 'data' in jsondata and jsondata['data']:
                started_at = jsondata['data'][0].get('started_at')
                started_at = datetime.strptime(started_at, '%Y-%m-%dT%H:%M:%SZ') # convert string to datetime
                tz = pytz.timezone('Asia/Taipei')
                started_at = started_at.replace(tzinfo=pytz.utc).astimezone(tz) # convert UTC to Asia/Taipei
                return jsondata['data'][0].get('type') == 'live', started_at.strftime('%Y-%m-%d %H:%M:%S')
            return False, None
        except (IndexError, ValueError) as error:
            print("Error: ", error)
            return False, None