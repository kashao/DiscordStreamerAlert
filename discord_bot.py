
import discord
from discord.ext import tasks, commands
from twitch_bot import TwitchBot

class DiscordBot:
    def __init__(self, cfg, db_manager):
        self.cfg = cfg
        self.twitch_bot = TwitchBot(cfg, db_manager)
        self.intents = discord.Intents.all()
        self.bot = commands.Bot(command_prefix='!', intents=self.intents)
        self.bot.event(self.on_ready)
        self.bot.event(self.on_message)
        self.db_manager = db_manager
        self.commands_dict = {}
        self.update_commands_dict()
        self.live_notifs_loop = tasks.loop(seconds=10)(self._live_notifs_loop)

        # Add commands to the bot
        self.add_streamer_command()
        self.remove_streamer_command()
        self.list_streamers_command()
        self.add_command_command()
        self.remove_command_command()
        self.remove_server_channel_command()
        self.add_server_channel_command()

        # 自定義幫助指令
        self.bot.help_command = self.CustomHelpCommand()

    def update_commands_dict(self):
        for guild in self.bot.guilds:
            server_id = guild.id
            self.commands_dict[server_id] = self.db_manager.list_commands(server_id)

    def add_streamer_command(self):
        @self.bot.command(name='addstreamer')
        @commands.has_permissions(administrator=True)
        async def add_streamer(ctx, twitch_name: str):
            server_id = ctx.guild.id
            self.db_manager.add_streamer(server_id, twitch_name)
            await ctx.send(f"Streamer {twitch_name} added to the monitoring list.")

    def remove_streamer_command(self):
        @self.bot.command(name='removestreamer')
        @commands.has_permissions(administrator=True)
        async def remove_streamer(ctx, twitch_name: str):
            server_id = ctx.guild.id
            self.db_manager.remove_streamer(server_id, twitch_name)
            await ctx.send(f"Streamer {twitch_name} removed from the monitoring list.")

    def list_streamers_command(self):
        @self.bot.command(name='liststreamers')
        async def list_streamers(ctx):
            server_id = ctx.guild.id
            streamers = self.db_manager.list_streamers(server_id)
            if streamers:
                await ctx.send("\n".join(streamers))
            else:
                await ctx.send("No streamers are currently being monitored.")

    def add_command_command(self):
        @self.bot.command(name='addcommand')
        @commands.has_permissions(administrator=True)
        async def add_command(ctx, command, *, response):
            server_id = ctx.guild.id
            self.db_manager.add_command(server_id, command, response)
            self.update_commands_dict()
            await ctx.reply(f"Command {command} added with response: {response}")

    def remove_command_command(self):
        @self.bot.command(name='removecommand')
        @commands.has_permissions(administrator=True)
        async def remove_command(ctx, command):
            server_id = ctx.guild.id
            self.db_manager.remove_command(server_id, command)
            self.update_commands_dict()
            await ctx.send(f"Command {command} removed.")

    def remove_server_channel_command(self):
        @self.bot.command(name='removeserverchannel')
        @commands.has_permissions(administrator=True)
        async def remove_server_channel(ctx):
            """Remove a server and its channels from the list."""
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
            self.db_manager.remove_server_channel(server_id, channel_id)
            await ctx.send(f"Server {server_id} and its channels removed from the list.")

    def add_server_channel_command(self):
        @self.bot.command(name='addserverchannel')
        @commands.has_permissions(administrator=True)
        async def add_server_channel(ctx):
            """Set the current channel as the notification channel."""
            server_id = ctx.guild.id
            channel_id = ctx.channel.id
            self.db_manager.add_server_channel(server_id, channel_id)
            await ctx.send(f"Current channel set as the notification channel.")

    async def _live_notifs_loop(self):
        for guild in self.bot.guilds:
            server_id = guild.id
            streamers = self.db_manager.list_streamers(server_id)
            channel_id = self.db_manager.get_channel_id(server_id)
            if streamers and channel_id:
                channel = self.bot.get_channel(channel_id)
                for twitch_name in streamers:
                    status, started_at = await self.twitch_bot.check_user(twitch_name)
                    if status:
                        last_notified_at = self.db_manager.get_last_notified_at(server_id, twitch_name)
                        if not last_notified_at or started_at > last_notified_at:
                            message_content = f":red_circle: **LIVE** {twitch_name} is now live on Twitch since {started_at}! {self.cfg['twitch']['stream_url'].format(twitch_name)}"
                            await channel.send(message_content)
                            print(f"{twitch_name} Notification.")
                            self.db_manager.set_last_notified_at(server_id, twitch_name, started_at)
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
            server_id = message.guild.id
            commands = self.commands_dict.get(server_id, {})
            if message.content in commands:
                await message.channel.send(commands[message.content])
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