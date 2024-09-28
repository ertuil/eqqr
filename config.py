import yaml
import logging

config = None

logger = logging.getLogger("eqqr.config")


def get_config(config_file: str):
    global config
    try:
        logger.info(f"Reading config file: {config_file}")
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to read config file: {e}")
        exit()
    return config


if __name__ == "__main__":
    config = get_config("config.yaml")
    print(config)
