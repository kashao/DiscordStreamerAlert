
from config_loader import ConfigLoader
from db_manager import DBManager
from discord_bot import DiscordBot

if __name__ == "__main__":
    config_loader = ConfigLoader()
    db_streamers = DBManager('streamers.db')
    discord_bot = DiscordBot(config_loader.cfg, db_streamers)
    discord_bot.run()
