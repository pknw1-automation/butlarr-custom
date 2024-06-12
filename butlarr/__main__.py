from loguru import logger
from telegram import Update
from telegram.ext import Application

from .database import Database
from .config.secrets import TELEGRAM_TOKEN
from .config.services import SERVICES 
from .tg_handler import get_clbk_handler, get_help_handler, start_handler, custom_command
from .tg_handler.auth import get_auth_handler
from configparser import ConfigParser
from os.path import exists

custom_commands_exist=exists('/app/custom_commands.ini')

if custom_commands_exist == True:
    custom_commands = ConfigParser()
    custom_commands.read('/app/custom_commands.ini')

def init():
    pass


def main():
    logger.info('Initializing database...')
    db = Database()

    logger.info('Creating bot...')
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    logger.info('Registering auth command...')
    application.add_handler(get_auth_handler(db))

    logger.info('Registering help commands...')
    application.add_handler(get_help_handler(SERVICES))

    logger.info('Registering start commands...')
    application.add_handler(start_handler(SERVICES))

    if custom_commands_exist == True:
        logger.info('Registering custom commands...')
        for command in custom_commands.sections():
            logger.info('Registering '+command+' handler')
            application.add_handler(custom_command(command))
    else:
        logger.info('No custom commands to process')

    logger.info('Registering services..')
    for s in SERVICES:
        s.register(application, db)

    logger.info('Registering callback handler...')
    application.add_handler(get_clbk_handler(SERVICES))

    logger.info('Start polling for messages..')
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
