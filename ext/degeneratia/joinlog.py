from discord.ext import commands

GUILD_ID : int = 918929892618407966
CHANNEL_ID : int = 919202798388789278

class JoinOrLeaveEventLogger(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.guild = self.bot.get_guild(GUILD_ID)
		self.channel = self.bot.get_channel(CHANNEL_ID)

	def cog_check(self, ctx):
		return ctx.guild == self.guild

	@commands.Cog.listener('on_member_join')
	async def on_member_join(self, member):
		await self.channel.send(f'`{member}` just joined the server.')

	@commands.Cog.listener('on_member_remove')
	async def on_member_remove(self, member):
		await self.channel.send(f'`{member}` has left the server.')

	@commands.Cog.listener('on_member_ban')
	async def on_member_ban(self, guild, user):
		await self.channel.send(f'(`{user}` was banned).')


def setup(bot):
	bot.add_cog(JoinOrLeaveEventLogger(bot))