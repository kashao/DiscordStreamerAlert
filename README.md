# Project Description

This Python script creates a bot for Discord that integrates with the Twitch API. It has the following functionalities:

Monitor a list of Twitch streamers and notify a Discord channel when a streamer goes live.
Store custom Discord commands and their responses in an SQLite database.
Add and remove streamers to/from the monitoring list.
Add and remove custom Discord commands.

## Requirements

Python 3.11 or higher
Install all necessary libraries by running pip install -r requirements.txt in your terminal.

```python
pip install -r requirements.txt
```

## How to run

Edit the config.yml file with your Twitch and Discord details.
Run python main.py in your terminal.

```python
python main.py
```

## Bot Commands

The bot responds to the following commands:

- !help
- !addstreamer [twitch_name]: Add a Twitch streamer to the monitoring list.
- !removestreamer [twitch_name]: Remove a Twitch streamer from the monitoring list.
- !liststreamers: Display the list of all monitored Twitch streamers.
- !addcommand [command] [response]: Add a custom command and its response to the Discord bot.
- !removecommand [command]: Remove a custom command from the Discord bot.
Make sure to prefix these commands with the bot's command prefix (e.g., !).

Note: Before running the bot, ensure that you have valid credentials for both Twitch and Discord. Refer to the config.yml file for the required format and make the necessary changes accordingly.

## Example Configuratio

Here is an example of the config.yml file:

```yaml
twitch:
  client_id: YOUR_TWITCH_CLIENT_ID
  client_secret: YOUR_TWITCH_CLIENT_SECRET
  redirect_uri: YOUR_TWITCH_REDIRECT_URI
  token_url: https://id.twitch.tv/oauth2/token
  user_api: https://api.twitch.tv/helix/users?id={}
  stream_url: https://www.twitch.tv/{}

connection:
  Discord bot token: YOUR_DISCORD_BOT_TOKEN
```

Replace YOUR_TWITCH_CLIENT_ID, YOUR_TWITCH_CLIENT_SECRET, YOUR_DISCORD_TOKEN, and YOUR_DISCORD_CHANNEL_ID with your actual credentials.
