
import yaml

class ConfigLoader:
    def __init__(self):
        with open('config.yml', "r", encoding="utf-8") as ymlfile:
            self.cfg = yaml.safe_load(ymlfile)
