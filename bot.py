import discord
from discord.ext import commands
import aiohttp
from config import token

import os
import time


os.environ['JISHAKU_NO_UNDERSCORE'] = "True"
os.environ['JISHAKU_NO_DM_TRACEBACK'] = "True"

class Akasata(commands.AutoShardedBot):
	def __init__(self, *options):
		super().__init__(intents= discord.Intents.all(), command_prefix= self._prefix_function)

	def _prefix_function(self, bot, message):
		prefixes= (
			'a!',
			's!',
			'ss'
			'aka',
			'aka ',
			'hey aka ',
			'dear aka ',
			'akasata ',
			'hey akasata ',
			'dear akasata '
			)

		return commands.when_mentioned_or(*prefixes)(bot, message)
	
	async def start(self, *args, **kwargs):
		self.session = aiohttp.ClientSession(loop= self.loop)
		await super().start(*args, **kwargs)
		await self.wait_until_ready()
		
		extensions = ['jishaku', 'ext.core.admin', 'ext.core.meta', 'ext.kaguya.reader', 'ext.kaguya.search', 'ext.degeneratia.event']
		
		for ext in extensions:
			self.load_extension(ext)


	async def close(self, *args, **kwargs):
		await self.session.close()
		print(f'[{round(time.time())}]: Shuting down...')
		await super().close(*args, **kwargs)

	async def on_ready(self):
		print(f'{self.user}: Ready. ({self.user.id})')
		print(f'{sum([guild.member_count for guild in self.guilds])} members.')

	async def on_command_error(self, ctx, error):
		if hasattr(ctx.command,'on_error'):
			return

		error = getattr(error, 'original', error)
		ignored = (commands.CommandNotFound)

		if isinstance(error, ignored):
			pass
		
		elif isinstance(error, commands.NotOwner):
			await ctx.reply(content= 'No, Fuck you.')
		else:
			 raise error


if __name__ == "__main__":
	bot= Akasata()
	bot.run(token)
