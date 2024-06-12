import shlex

from typing import List, Tuple, Callable
from loguru import logger
from functools import wraps
from telegram.ext import CommandHandler, CallbackQueryHandler

from ..config.commands import AUTH_COMMAND, HELP_COMMAND, START_COMMAND
from ..config.secrets import ADMIN_AUTH_PASSWORD
from ..tg_handler.message import Response
from ..database import Database
from configparser import ConfigParser
from os.path import exists

custom_commands_exist=exists('/app/custom_commands.ini')

if custom_commands_exist == True:
    custom_responses = ConfigParser()
    custom_responses.read('/app/custom_commands.ini')

def custom_command(command):
    if custom_responses[command]['response'] == 'multiline':
        response_message = f"\n"
        for count in range(0,int(custom_responses[command]['count'])):
            response_message += custom_responses[command]['response'+str(count)]
            response_message += "\n"
    else:
        response_message = custom_responses[command]['response']

    async def handler(update, context):
        await update.message.reply_text(response_message, parse_mode="Markdown")

    return CommandHandler(command, handler)

def start_handler(services):
    response_message = f"Welcome to the *Notflix* requests bot! \n"
    if custom_commands_exist == True:
        response_message += f"\nYou can use this bot to interact with the following services"
        response_message += f"\n • `/help` *show available commands*"
        for cmd in custom_responses.sections():
            response_message += f"\n • `/{cmd}` *"+custom_responses[cmd]['info']+"*"

    response_message += f"\n\nuse `/auth` to use *Movie & TV* requests"

    for s in services:
        for cmd in s.commands:
            response_message += f"\n • `/{cmd} <search string>`"
    # [Notflix](https://www.pknw1.co.uk/assets/images/logo-stacked-511x282.png) Web Services:

    response_message += f"""\n
• [Plex](https://plex.pknw1.co.uk) to watch movies and TV [(info)](https://plex.tv) [(apps)](https://www.plex.tv/media-server-downloads/?cat=plex+desktop&plat=macos#plex-app)
• [Request](https://requests.pknw1.co.uk) auto adds any movie/show to plex 
• [Download](https://download.secure.pknw1.co.uk) any media, software, eBooks+ 
• [NoAdsTube](https://youtube.secure.pknw1.co.uk) is YouTube without Ads/Tracking 
• [MeTube](https://metube.secure.pknw1.co.uk) adds YouTube videos to Plex 

  [Recently Added](https://www.pknw1.co.uk/notflix#:~:text=Recently%20Added%20Movies)|[Login](https://www.pknw1.co.uk/plex_login)|[Info](https://www.pknw1.co.uk/notflix)|[Contact](https://t.me/pknw1)|[Status](https://status.pknw1.co.uk)
"""
    
    async def handler(update, context):
        await update.message.reply_text(response_message, parse_mode="Markdown")

    return CommandHandler(START_COMMAND, handler)

def get_help_handler(services):
    response_message = f"""
    The *Notflix Bot* helps you interact with available services.\n"""
   
    if custom_commands_exist == True:
        for cmd in custom_responses.sections():
            response_message += f"\n • `/{cmd}` *"+custom_responses[cmd]['info']+"*"

    response_message += f"""\n
To enable *requests*, type `/{AUTH_COMMAND}` to add your id.
You can then interact with the services using:"""
    for s in services:
        for cmd in s.commands:
            response_message += f"\n • `/{cmd} <search string>`"

    async def handler(update, context):
        await update.message.reply_text(response_message, parse_mode="Markdown")

    return CommandHandler(HELP_COMMAND, handler)


def get_clbk_handler(services):
    async def handler(update, context):
        args = shlex.split(update.callback_query.data.strip())
        if args[0] == "noop":
            await update.callback_query.answer()
            return
        logger.debug(f"Received callback: {args}")
        for s in services:
            if args[0] == s.commands[0]:
                return await s.handle_callback(update, context)
        logger.error("Found no matching callback handler!")

    return CallbackQueryHandler(handler)


def callback(cmds=[], default=False):
    def decorator(func):
        if default:
            func.clbk_default = True
        if cmds:
            func.clbk_cmds = cmds
        return func

    return decorator


def command(cmds=[], default=False):
    def decorator(func):
        if default:
            func.cmd_default = True
        if cmds:
            func.cmd_cmds = cmds
        return func

    return decorator


def handler(cls):
    cls.sub_commands = []
    cls.sub_callbacks = []
    default_command = None
    default_callback = None
    for method in cls.__dict__.values():
        if hasattr(method, "cmd_cmds"):
            cls.sub_commands += [(cmd, method) for cmd in method.cmd_cmds]
        if hasattr(method, "cmd_default"):
            assert default_command is None, "Only one default command allowed."
            default_command = method
        if hasattr(method, "clbk_cmds"):
            cls.sub_callbacks += [(cmd, method) for cmd in method.clbk_cmds]
        if hasattr(method, "clbk_default"):
            assert default_callback is None, "Only one default callback allowed."
            default_callback = method
    cls.default_command = default_command
    cls.default_callback = default_callback
    return cls


class TelegramHandler:
    db: Database
    commands: List[str]
    sub_commands: List[Tuple[str, Callable]]
    sub_callbacks: List[Tuple[str, Callable]]

    def register(self, application, db):
        self.db = db
        for cmd in self.commands:
            application.add_handler(CommandHandler(cmd, self.handle_command))

    async def default_command(self, _update, _context, _args=None):
        del _update, _context, _args
        raise NotImplementedError

    async def handle_command(self, update, context):
        args = shlex.split(update.message.text.strip())
        logger.info(f"Received command: {args}")

        if self.sub_commands and len(args) > 1:
            for s, c in self.sub_commands:
                if args[1] == s:
                    logger.debug(f"Subcommand - Executing {s} ({c.__name__})")
                    await c(self, update, context, args[1:])
                    return

            logger.debug("No matching subcommand registered. Trying fallback")
        try:
            await self.default_command(update, context, args[1:])
        except NotImplementedError:
            logger.error("No default command handler registered.")

    async def default_callback(self, _update, _context, _args=None):
        del _update, _context, _args
        raise NotImplementedError

    async def handle_callback(self, update, context):
        args = shlex.split(update.callback_query.data.strip())
        if args[0] != self.commands[0]:
            return
        if self.sub_callbacks and len(args) > 1:
            for s, c in self.sub_callbacks:
                if args[1] == s:
                    logger.debug(f"Subcallback - Executing {s} ({c.__name__})")
                    await c(self, update, context, args[1:])
                    return

            logger.debug("No matching subcallback registered. Trying fallback")
        try:
            await self.default_callback(update, context, args[1:])
        except NotImplementedError:
            logger.error("No default callback handler registered.")

    def get_clbk(self, *args: List[str]):
        args = [self.commands[0], *args]
        return (" ").join([f'"{arg}"' for arg in args])
