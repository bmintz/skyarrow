#!/usr/bin/env python3
# encoding: utf-8

# Copyright © 2018 Benjamin Mintz <bmintz@protonmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import contextlib
import logging
import os.path
import re
import traceback
import uuid

import discord
from discord.ext import commands
import json5

BASE_DIR = os.path.dirname(__file__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SkyArrow:
	def __init__(self, *, config, loop=None):
		self.config = config
		self.loop = loop or asyncio.get_event_loop()
		self.discord = SkyArrowDiscordBot(self.config['discord'], loop=loop)
		self.irc = SkyArrowIrcBot(self.config['irc'], loop=loop)

	def run(self):
		# TODO deal with cleanup braindeath
		self.loop.create_task(self.discord.start())
		self.loop.create_task(self.irc.start())
		self.loop.run_forever()

class SkyArrowDiscordBot(commands.Bot):
	def __init__(self, config)
		self.config = config
		self._process_config()
		self._fallback_prefix = str(uuid.uuid4())

		super().__init__(
			command_prefix=self.get_prefix_,
			description='An IRC bridge.')

	def get_prefix_(self, bot, message):
		prefixes = []
		mention_match = re.search(fr'({bot.user.mention}|<@!{bot.user.id}>)\s+', message.content)
		if mention_match:
			prefixes.append(mention_match[0])

		match = re.search(fr'{self.config["prefix"]}', message.content, re.IGNORECASE)

		if match is not None:
			prefixes.append(match[0])

		# a UUID is something that's practically guaranteed to not be in the message
		# because we have to return *something*
		# annoying af
		return prefixes or self._fallback_prefix

	def _process_config(self):
		success_emojis = self.config.get('success_or_failure_emojis')
		if success_emojis:
			utils.SUCCESS_EMOJIS = success_emojis

	async def on_ready(self):
		logger.info('Logged in as: %s', self.user)
		logger.info('ID: %s', self.user.id)

	def _formatted_prefix(self):
		prefix = self.config['prefix']
		if prefix is None:
			prefix = f'@{self.user.name} '
		return prefix

	async def process_commands(self, message):
		# overridden because the default process_commands now ignores bots
		if message.author == self.user:
			return

		context = await self.get_context(message)
		await self.invoke(context)

	# https://github.com/Rapptz/RoboDanny/blob/ca75fae7de132e55270e53d89bc19dd2958c2ae0/bot.py#L77-L85
	async def on_command_error(self, context, error):
		if isinstance(error, commands.NoPrivateMessage):
			await context.author.send('This command cannot be used in private messages.')
		elif isinstance(error, commands.DisabledCommand):
			message = 'Sorry. This command is disabled and cannot be used.'
			try:
				await context.author.send(message)
			except discord.Forbidden:
				await context.send(message)
		elif isinstance(error, commands.NotOwner):
			logger.error('%s tried to run %s but is not the owner', context.author, context.command.name)
			with contextlib.suppress(discord.HTTPException):
				await context.try_add_reaction(utils.SUCCESS_EMOJIS[False])
		elif isinstance(error, (commands.UserInputError, commands.CheckFailure)):
			await context.send(error)
		elif isinstance(error, commands.CommandInvokeError):
			logger.error('"%s" caused an exception', context.message.content)
			logger.error(''.join(traceback.format_tb(error.original.__traceback__)))
			# pylint: disable=logging-format-interpolation
			logger.error('{0.__class__.__name__}: {0}'.format(error.original))

			await context.send('An internal error occured while trying to run that command.')

	async def start(self):
		self._load_extensions()

		await super().start(self.config['tokens'].pop('discord'))

	def _load_extensions(self):
		for extension in self.config['startup_extensions']:
			self.load_extension(extension)
			logger.info('Successfully loaded %s', extension)

class SkyArrowIrcBot:
	def __init__(self, config, *, loop=None):
		self.config = config
		self.bot = IRCBot(log_communication=True, loop=loop)
		self.bot.load_events(self)

	async def start(self):
		await self.bot.connect_async(self.config['hostname'], self.config['port'])
		await self.bot.register_async(self.config['name'])
		for channel in self.config['channels']:
			await self.bot.join(channel)
