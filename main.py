"""My module docstring"""
import json
import time
import sqlite3
from datetime import datetime
import requests
import yaml
from twitchAPI.twitch import Twitch
import pytz
import discord
from discord.ext import tasks, commands
from twitchAPI.helper import first

class ConfigLoader:
    def __init__(self):
        with open('config.yml', "r", encoding="utf-8") as ymlfile:
            self.cfg = yaml.safe_load(ymlfile)

class DBManager:
    def __init__(self, db_name='twitch_db.sqlite'):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def add_streamer(self, twitch_name):
        cur = self.conn.cursor()
        cur.execute('''
            INSERT OR IGNORE INTO streamers (twitch_name, last_notified_at) 
            VALUES (?, ?)
        ''', (twitch_name, "1970-01-01 00:00:00"))
        self.conn.commit()

    def remove_streamer(self, twitch_name):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM streamers WHERE twitch_name = ?', (twitch_name,))
        self.conn.commit()

    def list_streamers(self):
        cur = self.conn.cursor()
        cur.execute('SELECT twitch_name FROM streamers')
        rows = cur.fetchall()
        return [row[0] for row in rows]

    def get_last_notified_at(self, twitch_name):
        cur = self.conn.cursor()
        cur.execute('SELECT last_notified_at FROM streamers WHERE twitch_name = ?', (twitch_name,))
        row = cur.fetchone()
        return row[0] if row else None

    def set_last_notified_at(self, twitch_name, last_notified_at):
        cur = self.conn.cursor()
        # Use INSERT OR REPLACE to insert a new record or replace the existing one
        cur.execute('''
            INSERT OR REPLACE INTO streamers (twitch_name, last_notified_at) 
            VALUES (?, ?)
        ''', (twitch_name, last_notified_at))
        self.conn.commit()

    def create_tables(self):
        cur = self.conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS streamers (
                twitch_name TEXT PRIMARY KEY,
                last_notified_at TIMESTAMP
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS commands (
                command TEXT PRIMARY KEY,
                response TEXT
            )
        ''')
        self.conn.commit()

    def add_command(self, command, response):
        cur = self.conn.cursor()
        cur.execute('INSERT OR IGNORE INTO commands (command, response) VALUES (?, ?)', (command, response))
        self.conn.commit()

    def remove_command(self, command):
        cur = self.conn.cursor()
        cur.execute('DELETE FROM commands WHERE command = ?', (command,))
        self.conn.commit()

    def list_commands(self):
        cur = self.conn.cursor()
        cur.execute('SELECT command, response FROM commands')
        return dict(cur.fetchall())

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
            print(user)
            user_info = await first(self.twitch.get_users(logins=user))
            userid = user_info.id
            print(userid)
            url = self.cfg['twitch']['user_api'].format(userid)
            print(url)
            req = requests.Session().get(url, headers=api_headers)
            jsondata = req.json()
            print(jsondata)
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

class DiscordBot:
    def __init__(self, cfg, db_manager):
        self.cfg = cfg
        self.twitch_bot = TwitchBot(cfg, db_manager)
        self.intents = discord.Intents.all()
        self.bot = commands.Bot(command_prefix='!', intents=self.intents)
        self.bot.event(self.on_ready)
        self.bot.event(self.on_message)
        self.db_manager = db_manager
        self.commands_dict = self.db_manager.list_commands()
        self.live_notifs_loop = tasks.loop(seconds=10)(self._live_notifs_loop)

        # Add commands to the bot
        self.add_streamer_command()
        self.remove_streamer_command()
        self.list_streamers_command()
        self.add_command_command()
        self.remove_command_command()

        # 自定義幫助指令
        self.bot.help_command = self.CustomHelpCommand()

    def add_streamer_command(self):
        @self.bot.command(name='addstreamer')
        @commands.has_permissions(administrator=True)
        async def add_streamer(ctx, twitch_name: str):
            """Add a streamer to the monitoring list."""
            self.db_manager.add_streamer(twitch_name)
            await ctx.send(f"Streamer {twitch_name} added to the monitoring list.")

    def remove_streamer_command(self):
        @self.bot.command(name='removestreamer')
        @commands.has_permissions(administrator=True)
        async def remove_streamer(ctx, twitch_name: str):
            """Remove a streamer from the monitoring list."""
            self.db_manager.remove_streamer(twitch_name)
            await ctx.send(f"Streamer {twitch_name} removed from the monitoring list.")

    def list_streamers_command(self):
        @self.bot.command(name='liststreamers')
        async def list_streamers(ctx):
            """List all the streamers being monitored."""
            streamers = self.db_manager.list_streamers()
            if streamers:
                await ctx.send("\n".join(streamers))
            else:
                await ctx.send("No streamers are currently being monitored.")

    def add_command_command(self):
        @self.bot.command(name='addcommand')
        @commands.has_permissions(administrator=True)
        async def add_command(ctx, command, *, response):
            """Add a command and its response."""
            self.db_manager.add_command(command, response)
            self.commands_dict[command] = response
            await ctx.reply(f"Command {command} added with response: {response}")

    def remove_command_command(self):
        @self.bot.command(name='removecommand')
        @commands.has_permissions(administrator=True)
        async def remove_command(ctx, command):
            """Remove a command and its response."""
            self.db_manager.remove_command(command)
            if command in self.commands_dict:
                del self.commands_dict[command]
            await ctx.send(f"Command {command} removed.")

    async def _live_notifs_loop(self):
        streamers = self.db_manager.list_streamers()
        if streamers:
            channel = self.bot.get_channel(self.cfg['discord']['channel'])
            for twitch_name in streamers:
                status, started_at = await self.twitch_bot.check_user(twitch_name)
                if status:
                    last_notified_at = self.db_manager.get_last_notified_at(twitch_name)
                    if not last_notified_at or started_at > last_notified_at:
                        message_content = f":red_circle: **LIVE** {twitch_name} is now live on Twitch since {started_at}! {self.cfg['twitch']['stream_url'].format(twitch_name)}"
                        await channel.send(message_content)
                        print(f"{twitch_name} Notification.")
                        self.db_manager.set_last_notified_at(twitch_name, started_at)
                    else:
                        print(f"{twitch_name}: already notified.")
                else:
                    print(f"{twitch_name}: not live.")

    class CustomHelpCommand(commands.HelpCommand):
        command_examples = {
            'addstreamer': {
                'description': 'Add a streamer to the monitoring list.',
                'example': '!addstreamer <twitch_name>'
            },
            'removestreamer': {
                'description': 'Remove a streamer from the monitoring list.',
                'example': '!removestreamer <twitch_name>'
            },
            'liststreamers': {
                'description': 'List all the streamers being monitored.',
                'example': '!liststreamers'
            },
            'addcommand': {
                'description': 'Add a command and its response.',
                'example': '!addcommand <command> <response>'
            },
            'removecommand': {
                'description': 'Remove a command and its response.',
                'example': '!removecommand <command>'
            }
        }

        async def send_bot_help(self, mapping):
            embed = discord.Embed(title='Command List', description='Here is a list of all commands:')
            for cog, command_list in mapping.items():
                command_details = []
                for command in command_list:
                    command_help = command.help or "No description available."
                    command_example = self.command_examples.get(command.name, {}).get('example', 'No example available.')
                    command_details.append(f"**{command.name}**: {command_help}\nExample: `{command_example}`")
                if command_details:
                    embed.add_field(name=cog.qualified_name if cog else 'Commands', value='\n'.join(command_details), inline=False)
            await self.get_destination().send(embed=embed)
            
    async def on_ready(self):
        self.live_notifs_loop.start()
        print('Logged in as:')
        print(self.bot.user.name)
        print(self.bot.user.id)
        print('---------------------------------------')
        print('Bot running.')
        game = discord.Game('Pokemon SV')
        await self.bot.change_presence(status=discord.Status.online, activity=game)

    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        # 頻道中的訊息
        if isinstance(message.channel, discord.abc.GuildChannel):
            if message.content in self.commands_dict:
                await message.channel.send(self.commands_dict[message.content])
            if message.content == 'help':
                embed = discord.Embed(
                    title='HELP',
                    description='type !help',
                    color=discord.Color.blue()
                )
                embed.add_field(name='A', value='1', inline=True)
                embed.add_field(name='B', value='2', inline=True)
                embed.set_footer(text='footer')
                await message.reply(embed=embed)
            if message.content == 'private_reply':
                user = message.author
                await user.send('這是只有你能看到的私人訊息！')
                await message.channel.send(f'{user.mention}，我已經向你發送了一個私人訊息。請檢查你的訊息匣。')
            await self.bot.process_commands(message)

        # 私人訊息
        elif isinstance(message.channel, discord.abc.PrivateChannel):
            if message.content == 'private':
                user = message.author
                await user.send('這是只有你能看到的私人訊息！')

    def run(self):
        self.bot.run(self.cfg['connection']['Discord bot token'])


if __name__ == "__main__":
    config_loader = ConfigLoader()
    db_streamers = DBManager('streamers.db')
    discord_bot = DiscordBot(config_loader.cfg, db_streamers)
    discord_bot.run()