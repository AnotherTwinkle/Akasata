from discord.ext import commands
import discord
import urllib

class DegenClubUtils(commands.Cog):
	'''A set of utilites for the degenclub VN'''
	def __init__(self, bot):
		self.bot = bot
		self.channels = {}
		self.dialouge_safe_prefix = 'dg '
		self.action_safe_prefix = 'ac '
		# Note, both of the prefixes must be 2 letters long plus a space (LEN 3), I'm sorry.

	@commands.command(hidden= True, aliases= ['img'])
	async def image(self, ctx, *, name : str):
		name = urllib.parse.quote(name if name.lower().endswith('.png') else name + '.png')
		return await ctx.send(f'https://raw.githubusercontent.com/AnotherTwinkle/degenclub/master/game/images/{name}')

	@commands.command(hidden= True, name='reflectionchannel', aliases= ['rfc', 'rc'])
	async def _set_reflection_channel(self,  ctx, channel: discord.TextChannel):
		self.channels[ctx.channel] = channel
		await ctx.send('ok.')

	@commands.Cog.listener('on_message')
	async def story_constructor_listener(self, message):
		if message.channel not in self.channels or message.author.bot: 
			return

		if (not message.content.startswith((self.dialouge_safe_prefix, self.action_safe_prefix))):
			return

		l = message.content[3:].split(' ')  # Remove the safe prefix and make each word part of a list
		if message.content.startswith(self.dialouge_safe_prefix):
			l[0] = f'**{l[0]}**' # Bold the first word, this should be the actor of the dialouge
			content = f"{l[0]} \"{' '.join(l[1:])}\""

		
		if message.content.startswith(self.action_safe_prefix):
			content = f'**{' '.join(l)}**' # Bold the whole fucking thing

		await self.channels[message.channel].send(content)


def setup(bot):
	bot.add_cog(DegenClubUtils(bot))

