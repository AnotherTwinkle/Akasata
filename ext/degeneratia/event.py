from discord.ext import commands, tasks
import discord

from io import BytesIO
import aiohttp
import asyncio
import time
import datetime

# Constants
GUILD_ID : int = 742276772355113041
PUBLIC_SUBMISSIONS_CHANNEL_ID : int = 921691775033298954
PRIVATE_SUBMISSIONS_CHANNEL_ID : int = 921691806788382772
IMAGE_DUMP_CHANNEL_ID : int = 921838665230077962
LOG_CHANNEL_ID : int = 921802913037307934

MAX_SUBMISSION_LIMIT : int = 3
MAX_UPVOTE_LIMIT : int = 2
MESSAGE_DELETE_SLEEP_TIME : int = 5
REACTION_REMOVE_SLEEP_TIME : int = 5

UPVOTE : str = '<:adil:832934134405791825>'
UPVOTE_EMOJI_ID  : int = 832934134405791825
ENABLE_UPVOTES_CACHE_INIT_POPULATION : bool = True

SUBMISSION_END_TIME : int = 1640260800
UPVOTE_END_TIME : int = 1640350800
MODERATORS : list[int] = [810461031821737994, 742661420683886597] # Twinkle, Apl

SUBMISSION_CHANNEL_FETCH_HISTORY_AMOUNT : int = 100
DISQUALIFIED_SUBMISSION_CONTENT_PREFIX : str = '***[DISQUALIFIED]*** '
VALID_SUBMISSION_FILETYPES  :  list = ['jpg', 'png', 'jpeg', 'gif']

MEME_REVIEW_MAX_SCORE : int = 10
MEME_REVIEW_GREETING_MESSAGE : str = '''
Hello, The review listener has been initiated.
Send `next` to move to the next submission, `abort` to abort the process. Sent an integer between `1` and `10` to apply that rating.
Everyone in the vc can give their opinion except from the author of the submission.
**Hint**: Waiting for you to send `next`.
'''

def authorized():
	def predicate(ctx):
		return ctx.author.id in MODERATORS
	return commands.check(predicate)

#The cog
class MemeEvent(commands.Cog, name= 'Meme event'):

	def __init__(self, bot):
		self.bot = bot
		self.guild = bot.get_guild(GUILD_ID)
		self.public_submissions_channel = bot.get_channel(PUBLIC_SUBMISSIONS_CHANNEL_ID)
		self.private_submissions_channel = bot.get_channel(PRIVATE_SUBMISSIONS_CHANNEL_ID)
		self.dump_channel = bot.get_channel(IMAGE_DUMP_CHANNEL_ID)

		self.cache = SubmissionCache(self.bot, self.private_submissions_channel)
		self.bot.log = self.bot.logger.log
		self.bot.loop.create_task(self.cache.populate())

	async def cog_check(self, ctx):
		return ctx.guild == self.guild

	async def file_from_url(self, url: str, filename: str = 'submission.png', session : aiohttp.ClientSession = None):
		asession = session if session else aiohttp.ClientSession()
		async with asession.get(url) as resp:
			data = await resp.content.read()

		file = discord.File(fp= BytesIO(data), filename= filename)
		if not session:
			await asession.close()

		return file

	async def submit(self, s):
		# This assumes cleanup has been/will be done.
		# Denial cases
		if len(s.attachments) > 1:
			return await self.deny_submission(s, '❌ Submission Denied. Too many attachments. Please post one submission at a time.')

		if s.attachments[0].filename.split('.')[-1].lower() not in VALID_SUBMISSION_FILETYPES:
			return await self.deny_submission(s, f'❌ Submission Denied. Your file does not have a valid filetype. The allowed filetypes are- {", ".join(VALID_SUBMISSION_FILETYPES)}')

		if SUBMISSION_END_TIME < s.created_at.timestamp():
			return await self.deny_submission(s, f'❌ Submission Denied. You submitted outside of time limit. (It expired <t:{int(time.time())}:R>)')

		if len(self.cache.submissions_by(s.author)) >= MAX_SUBMISSION_LIMIT:
			return await self.deny_submission(s, f'❌ Submission Denied. You\'ve already reached the MAX_SUBMISSION_LIMIT of `{MAX_SUBMISSION_LIMIT}`')

		submission_time = round(s.created_at.timestamp())
		author = s.author
		index = len(self.cache.submissions) + 1
		index_for_user = len(self.cache.submissions_by(author)) + 1
		caption = s.content
		image_url = (await self.dump_channel.send(content= f'{author}', file= await self.file_from_url(url= s.attachments[0].url, filename= f'submission.{s.attachments[0].filename.split(".")[-1].lower()}'))).attachments[0].url

		embed = SubmissionEmbed(caption, author, index, index_for_user, image_url)
		m = await self.private_submissions_channel.send(content= f'{author.mention} | Submitted <t:{submission_time}:R>.', embed = embed)
		self.cache.add(m)
		print(await m.add_reaction(UPVOTE))
		return m

	@commands.Cog.listener('on_message')
	async def listen_for_submissions(self, message):

		if (message.channel != self.public_submissions_channel
			or message.author == self.bot.user):
			return

		if not (message.attachments or message.author.bot) and (message.author.id not in MODERATORS):
			return await self.delete_message(message)

		s = await self.submit(message)
		if not s:
			return

		remaining_submissions = MAX_SUBMISSION_LIMIT - len(self.cache.submissions_by(message.author))
		r = await message.reply(f'👌 Submitted. You have {remaining_submissions} submission(s) left.') # TODO: FETCH REMAINING SUBMISSIONS FROM CACHE	
		await self.delete_messages([message, r])

	async def delete_message(self, message):
		await asyncio.sleep(MESSAGE_DELETE_SLEEP_TIME)
		try:
			return await message.delete()
		except discord.NotFound:
			pass

	async def delete_messages(self, messages):
		for message in messages:
			await self.delete_message(message)

	async def deny_submission(self, submission, reason):
		r = await submission.reply(reason)
		await self.delete_messages([r,  submission])
		return

	def is_submission(self, message_id):
		return message_id in self.cache.get_all_submission_ids()

	# The listeners that maintain the submission cache and deal with upvotes
	@commands.Cog.listener('on_raw_message_delete')
	async def on_submission_delete(self, payload):
		# Ideally, this should never be called
		if not self.is_submission(payload.message_id):
			return
		self.cache.remove(self.cache.get(payload.message_id))
		del self.cache.upvotes[payload.message_id]

	@commands.Cog.listener('on_raw_message_edit')
	async def on_submission_edit(self, payload):
		# This should only be called during meme review
		if not self.is_submission(payload.message_id):
			return
		self.cache.update((await self.private_submissions_channel.fetch_message(payload.message_id))) #getch_message is too.. well.. *fast*
		
	@commands.Cog.listener('on_raw_reaction_add')
	async def on_upvote(self, payload):
		if not self.is_submission(payload.message_id) and not str(payload.emoji) == UPVOTE:
			return

		user = self.guild.get_member(payload.user_id)
		message = await self.getch_message(payload)

		self.cache.update(message)
		if not message.id in self.cache.upvotes:
			self.cache.upvotes[message.id] = []

		if not self.bot.user == user and (len(self.cache.upvoted_by(user)) >= MAX_UPVOTE_LIMIT
			or self.cache.get(message.id).mentions[0].id == user.id
			or self.is_disqualified(message)
			or SUBMISSION_END_TIME < round(time.time())):

			await asyncio.sleep(REACTION_REMOVE_SLEEP_TIME)
			await message.remove_reaction(self.bot.get_emoji(UPVOTE_EMOJI_ID), user)

		self.cache.upvotes[message.id].append(user)
		self.bot.log(f'Upvote added on {payload.message_id} by {user}')

	@commands.Cog.listener('on_raw_reaction_remove')
	async def on_upvote_removal(self, payload):
		if not self.is_submission(payload.message_id) and not str(payload.emoji) == UPVOTE:
			return

		if not self.cache.upvotes.get(payload.message_id):
			return

		self.cache.update(await self.getch_message(payload))
		upvoters = self.cache.upvotes[payload.message_id]
		target = [upvoter for upvoter in upvoters if upvoter.id == payload.user_id][0]
		self.cache.upvotes[payload.message_id].remove(target)
		self.bot.log(f'Upvote by {payload.user_id} on {payload.message_id} was removed.')

	@commands.Cog.listener('on_raw_reaction_clear_emoji')
	async def on_upvote_clear(self, payload):
		if not self.is_submission(payload.message_id) and not str(payload.emoji) == UPVOTE:
			return
		self.cache.update(await self.getch_message(payload))
		self.cache.upvotes[payload.message_id] = []

	async def getch_message(self, payload):
		m = None
		try:
			m = payload.cached_message
		except AttributeError:
			pass
		return m if m else (await self.private_submissions_channel.fetch_message(payload.message_id))

	def is_disqualified(self, submission):
		return DISQUALIFIED_SUBMISSION_CONTENT_PREFIX in submission.content

	# Commands
	@authorized()
	@commands.guild_only()
	@commands.command(name= 'disqualify', aliases= ['dq'])
	async def _disqualify_command(self, ctx, *, reason = None):
		try:
			message = ctx.message.reference.resolved
		except AttributeError:
			return await ctx.send('No message to check.')

		if not self.is_submission(message.id):
			return await ctx.send('Target is NAS (Not A Submission).')

		if self.is_disqualified(message):
			return await ctx.send('Target is already disqualified.')

		content, embed = message.content, message.embeds[0]
		content = DISQUALIFIED_SUBMISSION_CONTENT_PREFIX + content
		embed.color = discord.Color.red()
		await message.edit(content= content, embed= embed)
		await message.clear_reaction(self.bot.get_emoji(UPVOTE_EMOJI_ID))
		await message.add_reaction(UPVOTE)

		await ctx.send('👌')

		try:
			member = self.guild.get_member(message.mentions[0].id)
			remaining_submissions = MAX_SUBMISSION_LIMIT - len(self.cache.submissions_by(member))
			reason_string = f'The reason provided by `{ctx.author}` is: {reason}' if reason else 'No reason was provided.'
			submission_disqualify_string = f'Hello, Your submission has been **disqualified**. The submission slot won\'t be available to you as a penalty. You can post `{remaining_submissions}` more submission(s).\n{reason_string}'
			await member.send(content= submission_disqualify_string, embed= embed)
		except discord.HTTPException:
			await ctx.send('Couldn\'t DM user. (HTTPException)')

	@authorized()
	@commands.guild_only()
	@commands.command(name= 'undisqualify', aliases= ['udq', 'rq'])
	async def _undo_disqualify_command(self, ctx, *, reason = None):
		try:
			message = ctx.message.reference.resolved
		except AttributeError:
			return await ctx.send('No message to check.')

		if not self.is_submission(message.id):
			return await ctx.send('Target is NAS (Not A Submission).')

		if not self.is_disqualified(message):
			return await ctx.send('Target is not disqualifed.')

		content, embed = message.content, message.embeds[0]
		content = content.replace(DISQUALIFIED_SUBMISSION_CONTENT_PREFIX, '')
		embed.color = discord.Color.blue()
		await message.edit(content= content, embed= embed)
		await ctx.send('👌')

		try:
			member = self.guild.get_member(message.mentions[0].id)
			remaining_submissions = MAX_SUBMISSION_LIMIT - len(self.cache.submissions_by(member))
			reason_string = f'The reason provided by `{ctx.author}` is: {reason}' if reason else 'No reason was provided.'
			submission_requalify_string = f'Hello, the disqualification flag on your submission has been removed.\n{reason_string}'
			await member.send(content= submission_requalify_string, embed = embed)
		except discord.HTTPException:
			await ctx.send('Couldn\'t DM user. (HTTPException)')

	@authorized()
	@commands.guild_only()
	@commands.command(name= 'clearupvotes', aliases= ['cup'])
	async def _clear_all_upvotes(self, ctx):
		try:
			message = ctx.message.reference.resolved
		except AttributeError:
			return await ctx.send('No message to check.')

		if not self.is_submission(message.id):
			return await ctx.send('Target is NAS (Not A Submission).')

		await message.clear_reaction(self.bot.get_emoji(UPVOTE_EMOJI_ID))
		await message.add_reaction(UPVOTE)
		return await ctx.send('👌')

	@authorized()
	@commands.guild_only()
	@commands.command(name= 'memereview', aliases= ['mr'])
	async def _launch_meme_review(self, ctx):
		message = await ctx.channel.send(MEME_REVIEW_GREETING_MESSAGE)
		i = 0
		while True:
			m = await self.bot.wait_for('message', check= lambda m: m.author == ctx.author and m.channel == ctx.channel and (m.content in ['next', 'abort'] or m.content.isdigit), timeout= 3600)
			if m.content == 'next':
				if i >= len(self.cache.submissions):
					message = await message.edit(content= 'This is the last submission!')
					break
				submission = self.cache.submissions[i]
				message= await message.edit(content= submission.content, embed= submission.embeds[0])
				await m.delete()
				i += 1

			if m.content.isdigit():
				if not message.embeds:
					await self.delete_messages([await ctx.send('Please initiate meme review first.'), m])
					continue

				if not int(m.content) in range(0, MEME_REVIEW_MAX_SCORE + 1):
					await self.delete_messages([await ctx.send(f'Rating out of range. (`{MEME_REVIEW_MAX_SCORE}` max)'), m])
					continue

				if len(submission.content.split('|')) >= 3:
					s = submission.content.split('|')
					s[2] = f'Rating: `{m.content}`'
					newcontent = ('|'.join(s))
				else:
					newcontent = submission.content + f' | Rating: `{m.content}`'

				await submission.edit(newcontent)
				message = await message.edit(content= newcontent)
				await m.delete()

			if m.content == 'abort':
			 	await message.delete()
			 	await m.delete()
			 	break

	#Statistics
	@commands.guild_only()
	@commands.command(name= 'stats')
	async def _global_stats(self, ctx):
		'''Displays statistics for the event..'''

		scount = len([s for s in self.cache.submissions if not self.is_disqualified(s)])

		if not scount:
			await ctx.send(f'No (qualified) submissions were found.')
			
		ucount = sum([len(self.cache.upvotes[s]) for s in self.cache.upvotes if not self.is_disqualified(self.cache.get(s))])
		return await ctx.send(f'`GLOBAL`: `{ucount}` upvote(s) on `{scount}` submission(s). (`{round(ucount/scount, 2)}` upvote(s) on average)')

	@commands.guild_only()
	@commands.command(name= 'userstats', aliases= ['ustats'])
	async def _stat_for_user(self, ctx, user : discord.User = None):
		'''Displays statistics of for user.'''

		user = user or ctx.author
		submissions = self.cache.submissions_by(user)

		if not submissions:
			await ctx.send(f'No submissions found for user {user}.')

		scount = len(submissions)
		ucount = sum([len(self.cache.upvotes[s.id])-1 for s in submissions if not self.is_disqualified(s)])
		return await ctx.send(f'`{user}`:  `{ucount}` upvote(s) on `{scount}` submission(s). (`{round(ucount/scount, 2)}` upvote(s) on average)')

	@commands.guild_only()
	@commands.command(name= 'rankings', aliases= ['ranks', 'rank', 'top'])
	async def _rank_table(self, ctx):
		'''Dispalys a list of the most upvoted submissions'''

		r = sorted(self.cache.submissions, key= lambda s : len(self.cache.upvotes[s.id]), reverse= True)
		strings = [f'**{r.index(s)+1}.** `{s.embeds[0].title}` by {s.mentions[0]}: `{len(self.cache.upvotes[s.id])-1}` upvote(s).' for s in r][:min(10, len(r))]
		await ctx.send('\n'.join(strings))

	@commands.guild_only()
	@commands.command(name= 'urankings', aliases= ['uranks', 'urank'])
	async def _user_rank_table(self, ctx):
		'''Displays a list of most upvoted users.'''

		users = set([s.mentions[0] for s in self.cache.submissions])
		table = sorted([(user, sum([len(self.cache.upvotes[s.id])-1 for s in self.cache.submissions_by(user) if not self.is_disqualified(s)])) 
						for user in users], key= lambda t : t[1], reverse= True)

		strings = [f'**{table.index((u,c))+1}.** {u} : `{c}` upvote(s) on `{len([s for s in self.cache.submissions_by(u) if not self.is_disqualified(s)])}` submission(s).'
						 for u, c in table][:min(10, len(users))]

		await ctx.send('\n'.join(strings))

class SubmissionEmbed(discord.Embed):
	def  __init__(self, caption, author, index, index_for_user, image_url, *options):
		super().__init__(*options)

		self.title = f'Submission #{index}'
		self.color = author.top_role.color
		self.timestamp = datetime.datetime.now(datetime.timezone.utc)
		self.description = caption

		#self.set_thumbnail(url= author.avatar.url)
		self.set_author(name= author, icon_url= author.avatar.url)
		self.set_image(url= image_url)
		self.set_footer(text= f'{author.name}\'s submission #{index_for_user}')

class SubmissionCache:
	def __init__(self, bot, channel : discord.TextChannel):
		self.channel = channel
		self.bot = bot
		self.submissions = []
		self.upvotes = {}

	async def populate(self):
		submissions = [message for message in 
					(await self.channel.history(limit= SUBMISSION_CHANNEL_FETCH_HISTORY_AMOUNT).flatten())[::-1]
					if message.author == self.bot.user
					and message.embeds and message.mentions
					and message.embeds[0].title.lower().startswith('submission')]
		self.submissions = submissions
		self.bot.log(f'Cache populated with {len(submissions)} submissions.')

		if ENABLE_UPVOTES_CACHE_INIT_POPULATION:
			for submission in self.submissions:
				self.upvotes[submission.id] = await self.get_upvoters(submission) 
			self.bot.log(f'Built upvote cache with {len(self.upvotes)} calls.')

		return self

	async def get_upvoters(self, submission):
		target = [reaction for reaction in submission.reactions if str(reaction) == UPVOTE][0]
		return await target.users().flatten()

	def upvoted_by(self, user):
		return [self.get(sub) for sub in self.upvotes if user in self.upvotes[sub]]

	def get(self, id):
		target = [s for s in self.submissions if s.id == id]
		if not target:
			return
		return target[0]

	def add(self, submission):
		self.submissions.append(submission)
		self.bot.log(f'{submission.id} has been added to cache.')

	def update(self, new):
		target = None
		for s in range(0, len(self.submissions)):
			if self.submissions[s].id == new.id:
				target = s
				break

		if not target:
			return
		self.submissions[target] = new
		# self.bot.log(f'{new.id} has been updated in cache.')

	def remove(self, submission):
		self.submissions.remove(submission)
		self.bot.log(f'{submission.id} has been removed from cache.')

	def submissions_by(self, user):
		return [s for s in self.submissions if s.mentions[0].id == user.id]

	def get_all_submission_ids(self):
		return [s.id for s in self.submissions]
		
class Logger:
	def __init__(self, bot, channel_id):
		self.channel = bot.get_channel(channel_id)
		self.buffer = []
		self.empty_buffer.start()

	def log(self, content):
		self.buffer.append(content)

	@tasks.loop(seconds= 5)
	async def empty_buffer(self):
		if self.buffer:
			message = '\n'.join(self.buffer)
			await self.channel.send(message)
			self.buffer = []

def setup(bot):
	bot.logger = Logger(bot, LOG_CHANNEL_ID)
	bot.add_cog(MemeEvent(bot))
