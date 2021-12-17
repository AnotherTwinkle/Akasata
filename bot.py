import discord
from discord.ext import commands
import aiohttp
import config

class Akasata(commands.AutoShardedBot):
	def __init__(self, *options):
		super().__init__(intents= discord.Intents.all(), command_prefix= self._prefix_function)

	def _prefix_function(self, bot, message):
		prefixes= (
			'a!',
			'aka',
			'aka ',
			'hey aka ',
			'dear aka ',
			'akasata ',
			'hey akasata ',
			'dear akasata '
			)

		return commands.when_mentioned_or(*prefixes)(bot, messages)
	
	async def start(self, *args, **kwargs):
		self.session = aiohttp.ClientSession(loop= self.loop)

		extensions = ['jishaku', 'ext.core.admin', 'ext.core.meta', 'ext.kaguya.reader', 'ext.kaguya.search']
		
		for ext in (extensions + kaguya_extensions):
			self.load_extension(ext)

		await super().start(*args, **kwargs)


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
	bot.run(config.token)
