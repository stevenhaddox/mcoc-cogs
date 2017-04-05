import re
from datetime import datetime, timedelta
from textwrap import wrap
from math import log2
import os
import inspect
import urllib
import requests
#import json
import asyncio
from .utils.dataIO import dataIO
from functools import wraps
import discord
from discord.ext import commands
from .utils.dataIO import dataIO



data_files = {
    'frogspawn': {'remote': 'http://coc.frogspawn.de/champions/js/champ_data.json',
               'local':'data/mcoc/frogspawn_data.json', 'update_delta': 1},
    'spotlight': {'remote': 'https://spreadsheets.google.com/feeds/list/1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks/2/public/values?alt=json',
                'local': 'data/mcoc/spotlight_data.json', 'update_delta': 0},
    'crossreference': {'remote': 'https://spreadsheets.google.com/feeds/list/1QesYLjDC8yd4t52g4bN70N8FndJXrrTr7g7OAS0BItk/1/public/values?alt=json',
                'local': 'data/mcoc/crossreference.json', 'update_delta': 1},
    'signatures':{'remote':'https://spreadsheets.google.com/feeds/list/1kNvLfeWSCim8liXn6t0ksMAy5ArZL5Pzx4hhmLqjukg/5/public/values?alt=json',
                'local': 'data/mcoc/signatures.json', 'update_delta': 1},
## prestige - strictly the export of mattkraft's prestige table
    'prestige': {'remote': 'https://spreadsheets.google.com/feeds/list/1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks/2/public/values?alt=json',
                'local': 'data/mcoc/prestige.json', 'update_delta': 1},
    #'five-star-sig': {'remote':'https://spreadsheets.google.com/feeds/list/1kNvLfeWSCim8liXn6t0ksMAy5ArZL5Pzx4hhmLqjukg/3/public/values?alt=json',
                #'local': 'data/mcoc/five-star-sig.json'},
    #'four-star-sig': {'remote':'https://spreadsheets.google.com/feeds/list/1kNvLfeWSCim8liXn6t0ksMAy5ArZL5Pzx4hhmLqjukg/4/public/values?alt=json',
                #'local': 'data/mcoc/five-star-sig.json'},
    'phc_jpg' : {'remote': 'http://marvelbitvachempionov.ru/wp-content/dates_PCHen.jpg',
                'local': 'data/mcoc/dates_PCHen.jpg', 'update_delta': 7},
### coefficient by rank is HOOK's prestige coefficients.  But I am uncertain of generation process.
##   'coefficient-by-rank': {'remote': 'https://github.com/hook/champions/blob/master/src/data/pi/coefficient-by-rank.json',
##               'local': 'data/mcoc/coefficient-by-rank.json'},
    }

prestige_data = 'data/mcoc/prestige_data.json'
champ_portraits='data/mcoc/portraits/portrait_'
champ_featured='data/mcoc/uigacha/featured/GachaChasePrize_256x256_'
lolmap_path='data/mcoc/maps/lolmap.png'
champ_avatar='https://raw.github.com/JasonJW/mcoc-cogs/master/mcoc/data/portraits/portrait_'
file_checks_json = 'data/mcoc/file_checks.json'

###### KEYS for MCOC JSON Data Extraction
mcoc_dir='data/mcoc/com.kabam.marvelbattle/files/xlate/snapshots/en/'
kabam_bio = mcoc_dir + 'character_bios_en.json'
kabam_special_attacks = mcoc_dir+ 'special_attacks_en.json'
kabam_bcg_stat_en = mcoc_dir+'bcg_stat_en.json'
##### Special attacks require:
## mcoc_files + mcoc_special_attack + <champ.mcocjson> + {'_0','_1','_2'} ---> Special Attack title
#mcoc_special_attack='ID_SPECIAL_ATTACK_'
## mcoc_files mcoc_special_attack_desc + <champ.mcocjson> + {'_0','_1','_2'} ---> Special Attack Short description
#mcoc_special_attack_desc='ID_SPECIAL_ATTACK_DESCRIPTION_'


class_color_codes = {
        'Cosmic': discord.Color(0x2799f7), 'Tech': discord.Color(0x0033ff),
        'Mutant': discord.Color(0xffd400), 'Skill': discord.Color(0xdb1200),
        'Science': discord.Color(0x0b8c13), 'Mystic': discord.Color(0x7f0da8),
        'All': discord.Color(0xffffff), 'default': discord.Color.light_grey(),
        }

# if message.attachments > 0 :
#   if message.attachments = champsions.csv
#       store user champions.cons


def alias_resolve(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        for i in range(len(args)):
            args[i] = self._resolve_alias(args[i])
        return f(self, *args, **kwargs)
    return wrapper

class ChampConverter(commands.Converter):
    async def convert(self):
        bot = self.ctx.bot
        mcoc = bot.get_cog('MCOC')
        try:
            champ = mcoc._resolve_alias(self.argument)
        except KeyError:
            champs = mcoc._resolve_mult_aliases('.*{}.*'.format(self.argument))
            if len(champs) == 1:
                await bot.say("'{}' was not exact but found close alternative".format(
                        self.argument))
                champ = champs[0]
            else:
                await bot.say("```Cannot resolve alias for '{}'```".format(
                        self.argument))
                raise commands.BadArgument("Cannot resolve alias for '{}'".format(
                        self.argument))
        return champ


class MCOC:
    '''A Cog for Marvel's Contest of Champions'''

    lookup_links = {
            'event': (
                'Tiny MCoC Schedule',
                '<http://simians.tk/MCOC-Sched>'),
            'spotlight': (
                'MCoC Spotlight',
                '<http://simians.tk/MCoCspotlight>'),
            'marvelsynergy': (
                'Marvel Synergy Builder',
                '<http://www.marvelsynergy.com/team-builder>'),
            'frogspawn': (
                'Champion Signature Abilities',
                '<http://coc.frogspawn.de/champions>'),
            'alsciende':(
                'Alsciende Mastery Tool',
                '<https://alsciende.github.io/masteries/v10.0.1/#>'),
            'simulator': (
                'Mastery Simulator',
                '<http://simians.tk/msimSDF>'),
            'streak': (
                'Infinite Streak',
                'http://simians.tk/-sdf-streak')
                #'http://simians.tk/SDFstreak')
    }

    def __init__(self, bot):
        self.bot = bot

        self.settings = {
                'siglvl': 1,
                'sigstep': 20,
                'table_width': 9,
                'sig_inc_zero': False,
                }

        self.parse_re = re.compile(r'(?:s(?P<sig>[0-9]{1,3}))|(?:r(?P<rank>[1-5]))|(?:(?P<star>[45])\\?\*)')
        self.split_re = re.compile(', (?=\w+:)')
        self.verify_cache_remote_files(verbose=True)
        self._init()

    def _init(self):
        self._prepare_aliases()
        self._prepare_frogspawn_champ_data()
        self._prepare_prestige_data()
        # self._prepare_spotlight_data()

    @commands.command()
    async def flat(self, flat_val: float, challenger_rating : int=100):
        '''Convert MCOC Flat value to Percentge'''
        denom = 5 * challenger_rating + 1500 + flat_val
        p = round(100*flat_val/denom, 2)
        em = discord.Embed(color=discord.Color.gold(),
                title='Convert FlatValue to Percentage',
                description='FlatValue: {}'.format(flat_val))
        em.add_field(name='Percentage:', value='{}\%'.format(p))
        await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def list_members(self, ctx, role):
        server = ctx.message.server

        if role.id in discord.role:
            await self.bot.say('DBEUG: Discord Role detected')
            members = '\n'.join(k.full_name for k in role.members)
            await self.bot.say(members)


    @commands.command()
    async def mcoc_update(self, fname, force=False):
        if len(fname) > 3:
            for key in data_files.keys():
                if key.startswith(fname):
                    fname = key
                    break
        if fname in data_files:
            self.cache_remote_file(**data_files[fname], force_cache=force, verbose=True)
        else:
            await self.bot.say('Valid options for 1st argument are one of (or initial portion of)\n\t'
                    + '\n\t'.join(data_files.keys()))
            return

        self._init()
        await self.bot.say('Summoner, I have Collected the data')

    @commands.command()
    async def mcocset(self, setting, value):
        if setting in self.settings:
            self.settings[setting] = int(value)

    @commands.command(help=lookup_links['event'][0], aliases=('events',))
    async def event(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['event']))

    @commands.command(help=lookup_links['spotlight'][0])
    async def spotlight(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['spotlight']))

    # @commands.command(help=lookup_links['hook'][0])
    # async def hook(self):
    #     await self.bot.say('**{}**\n{}'.format(*self.lookup_links['hook']))

    @commands.command(help=lookup_links['frogspawn'][0])
    async def frogspawn(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['frogspawn']))

    @commands.command(help=lookup_links['marvelsynergy'][0])
    async def marvelsynergy(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['marvelsynergy']))

    @commands.command(help=lookup_links['simulator'][0])
    async def simulator(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['simulator']))

    @commands.command(help=lookup_links['alsciende'][0], aliases=('mrig',))
    async def alsciende(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['alsciende']))

    @commands.command(help=lookup_links['streak'][0])
    async def streak(self):
        await self.bot.say('**{}**\n{}'.format(*self.lookup_links['streak']))

    @commands.command()
    async def lolmap(self):
        '''Labrynth of Legends Map'''
        await self.bot.upload(lolmap_path, content='**LABYRINTH OF LEGENDS Map by Frogspawn**')

    def verify_cache_remote_files(self, verbose=False, force_cache=False):
        if os.path.exists(file_checks_json):
            try:
                file_checks = dataIO.load_json(file_checks_json)
            except:
                file_checks = {}
        else:
            file_checks = {}
        for key, val in data_files.items():
            if key in file_checks:
                last_check = datetime(*file_checks.get(key))
            else:
                last_check = None
            remote_check = self.cache_remote_file(**val, verbose=verbose, last_check=last_check)
            if remote_check:
                file_checks[key] = remote_check.timetuple()[:6]
            #print(key, remote_check)
        dataIO.save_json(file_checks_json, file_checks)

    def cache_remote_file(self, remote=None, local=None, verbose=False,
                update_delta=0, last_check=None, force_cache=False):
        strf_remote = '%a, %d %b %Y %H:%M:%S %Z'
        response = None
        remote_check = False
        now = datetime.now()
        if os.path.exists(local) and not force_cache:
            check_marker = None
            if last_check:
                check_marker = now - timedelta(days=update_delta)
                refresh_remote_check = check_marker > last_check
            else:
                refresh_remote_check = True
            local_dt = datetime.fromtimestamp(os.path.getmtime(local))
            #print(check_marker, last_check, refresh_remote_check, local_dt)
            if refresh_remote_check:
                response = requests.get(remote)
                remote_dt = datetime.strptime(response.headers['Last-Modified'], strf_remote)
                remote_check = now
                if remote_dt < local_dt:
                    # Remote file is older, so no need to transfer
                    response = None
        else:
            response = requests.get(remote)
        if response:
            print('Caching remote contents to local file: ' + local)
            fp = open(local, 'wb')
            for chunk in response.iter_content():
                fp.write(chunk)
            remote_check = now
        elif verbose and remote_check:
            print('Local file up-to-date:', local, now)
        return remote_check

    @commands.command()
    async def phc(self):
        '''Premium Hero Crystal Release Dates'''
        await self.bot.upload(data_files['phc_jpg']['local'],
                content='Dates Champs are added to PHC (and as 5* Featured for 2nd time)')

    @commands.command()
    async def portrait(self, champ : ChampConverter):
        '''View Champion Portraits'''
        await self.bot.upload(champ.get_portrait(), content=champ.bold_name)

    @commands.command()
    async def featured(self, champ : ChampConverter):
        '''View Champion Feature Images'''
        await self.bot.upload(champ.get_featured(), content=champ.bold_name)

    @commands.command()
    async def warmap(self, maptype='ai', dbg=1):
        '''Select a Warmap
        syntax: /warmap <left><right>
        Where <left> = [a, b, c, d, e]
        Where <right> = [f, g, g+, h, i]'''
        filepath_png = 'data/mcoc/warmaps/warmap_{}.png'
        mapurl = 'https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcoc/data/warmaps/warmap_{}.png'.format(maptype.lower())
        maps = {'af','ag','ag+','ah','ai','bf','bg','bg+','bh','bi','cf','cg',
                'cg+','ch','ci','df','dg','dg+','dh','ef','eg','eg+','eh','ei'}
        mapTitle = 'Alliance War Map {}'.format(maptype.upper())
        filepath = filepath_png.format(maptype.lower())
        if dbg == 0:
            if maptype in maps:
                await self.bot.upload(filepath, content=mapTitle)
            else :
                raise KeyError('Summoner, I cannot find that map with arg <{}>'.format(maptype))
        elif dbg == 1:
            if maptype in maps:
                em = discord.Embed(color=discord.Color.gold(),title=mapTitle)
                em.set_image(url=mapurl)
                await self.bot.say(embed=em)
            else :
                raise KeyError('Summoner, I cannot find that map with arg <{}>'.format(maptype))

    #@alias_resolve
    @commands.command()
    async def bio(self, champ : ChampConverter, dbg=0):
        '''Retrieve the Bio of a Champion'''
        em = discord.Embed(color=champ.class_color, title=champ.full_name,
                description=champ.get_bio())
        em.set_thumbnail(url=champ.get_avatar())
        #em.set_thumbnail(url=champ.get_portrait())
        await self.bot.say(embed=em)
        if dbg == 1:
            await self.bot.say('DEBUG: {}'.format(champ.mcocjson))

    @commands.command()
    async def sig_test(self, champ : ChampConverter, star: int=4, sig: int=99):
        key = '{}-{}-{}'.format(star, champ, sig)
        self.bot.say('DEBUG: key is ' + key)

    @commands.command()
    async def mcoc_sig(self, champ : ChampConverter, siglvl=99, dbg=0):
        '''Retrieve Champion Signature Ability from MCOC Files'''
        sigs = load_kabam_json(kabam_bcg_stat_en)
        title, title_lower, simple, desc = self._get_mcoc_keys(champ, sigs)

        if dbg == 1:
            await self.bot.say('DEBUG: Title: '+ title)
            await self.bot.say('DEBUG: title_lower: '+ title_lower)
            for k in simple:
                await self.bot.say('DEBUG: Simple: '+ k)
            for k in desc:
                await self.bot.say('DEBUG: Desc: '+ k)

        em = discord.Embed(color=champ.class_color, title=champ.full_name)
        if title in sigs:
            em.add_field(name=sigs[title], value='\n'.join([sigs[k] for k in simple]))
        else:
            em.add_field(name=sigs[title_lower], value='\n'.join([sigs[k] for k in simple]))
        em.add_field(name='Signature Level {}'.format(siglvl),
                value='\n'.join(['• ' + Champion._sig_header(sigs[k]) for k in desc]))
        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def role_roster(self, ctx, role : discord.Role):
        server = ctx.message.server
        if role.name is 'bg1':
            chosen = discord.color.blue()
        elif role.name is 'bg2':
            chosen = discord.color.purple()
        elif role.name is 'bg3':
            chosen = discord.color.orange()
        else:
            chose = discord.color.gold()
        if role in server.roles:
            cnt, line_out = self.get_roster(server, role)
            em = discord.Embed(color=chosen,title='{}'.format(role.name))
            em.add_field(name='{} members'.format(cnt), value='\n'.join(line_out))
            await self.bot.say(embed=em)
        else:
            await self.bot.say('Invalid Role')

    @commands.command()
    async def sig(self, champ : ChampConverter, siglvl=None, dbg=0, *args):
        '''Retrieve the Signature Ability of a Champion'''
        settings = self.settings.copy()
        if siglvl is not None:
            settings['siglvl'] = int(siglvl)
        title, desc, siglvl = champ.get_sig(**settings)
        if dbg == 0:
            em = discord.Embed(color=champ.class_color, title=champ.full_name)
            em.add_field(name='Signature Level '+str(siglvl),  value=desc)
        elif dbg == 1:
            em = discord.Embed(color=champ.class_color, title='Signature Ability')
            em.add_field(name='@ Level', value=siglvl)
            em.add_field(name = champ.full_name, value=desc)
        else:
            em = discord.Embed(color=champ.class_color,
                title=champ.full_name + ' Signature Ability')
            em.add_field(name='Level '+str(siglvl),  value=desc)
        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @commands.command()
    async def abilities(self, champ : ChampConverter):
        '''Champion Abilities List'''
        specials = champ.get_special_attacks()
        em = discord.Embed(color=champ.class_color,
        title=champ.full_name + 'Abilities')
        em.add_field(name='Passive',value='placeholder')
        em.add_field(name='All Attacks',value='placeholder')
        em.add_field(name='When Attacked',value='placeholder')
        em.set_thumbnail(url=champ.get_avatar())
        em2 = discord.Embed(color=champ.class_color,
        title=champ.full_name + ' Special Attacks')
        em2.add_field(name=specials[0], value=specials[3])
        em2.add_field(name=specials[1], value=specials[4])
        em2.add_field(name=specials[2], value=specials[5])
        await self.bot.say(embed=em)
        await self.bot.say(embed=em2)

#    @commands.command()
#    async def special(self, )

    @commands.command()
    async def sigarray(self, champ : ChampConverter, dbg=1, *args):
        '''Retrieve the Signature Ability of a Champion at multiple levels'''
        champ = self._resolve_alias(champ)
        title, desc = champ.get_sigarray(**self.settings)
        if dbg == 0:
            em = discord.Embed(color=champ.class_color, title=title,
                    description=desc)
        elif dbg == 1:
            em = discord.Embed(color=champ.class_color, title=champ.full_name)
            em.add_field(name='Signature Ability Array', value=desc)
        else:
            em = discord.Embed(color=champ.class_color, title=title)
            em.add_field(name='__SigLvl__', value='1\n20\n40')
            em.add_field(name='__X__', value='1.0\n1.9\n2.1', inline=True)

        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @commands.command()
    async def prestige(self, *args):
        champs = []
        default = {'star': 4, 'rank': 5, 'sig': 0}
        for arg in args:
            attrs = default.copy()
            for m in self.parse_re.finditer(arg):
                attrs[m.lastgroup] = int(m.group(m.lastgroup))
            remain = self.parse_re.sub('', arg)
            if remain != '':
                try:
                    champs.append((self._resolve_alias(remain),attrs))
                except KeyError:
                    raise KeyError('Cannot resolve: arg {},'.format(arg)
                            + ' residual champ {}, processing with {}'.format(remain, str(attrs)))
            else:
                default.update(attrs)
        #sigstep_arr = bound_lvl(list(range(0, 101, self.settings['sigstep'])))
        #table_data = [[''] + sigstep_arr]
        #table_data.append(champ.get_prestige(5, sigstep_arr))
        em = discord.Embed(color=discord.Color.magenta(), title='Debug', )
                #description=tabulate(table_data, self.settings['table_width']))
        for champ, attrs in champs:
            pres_dict = champ.get_prestige(**attrs)
            if pres_dict is None:
                await self.bot.say("**WARNING** Champion Data for {}, {star}*, rank {rank} does not exist".format(
                    champ.full_name, **attrs))
            else:
                em.add_field(**pres_dict)
        ##em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    def find_champ(self, champ_name, key):
        for champ in self.champs:
            if getattr(champ, key, '') == champ_name:
                return champ
        raise KeyError('No champion {} with key {}'.format(champ_name, key))

    @commands.command()
    async def champ_aliases(self, *args):
        champs_matched = []
        em = discord.Embed(color=discord.Color.teal(), title='Champion Aliases')
        for arg in args:
            if (arg.startswith("'") and arg.endswith("'")) or (arg.startswith('"') and arg.endswith('"')) :
                champs = self._resolve_mult_aliases(arg[1:-1])
            elif '*' in arg:
                champs = self._resolve_mult_aliases('.*'.join(re.split(r'\\?\*', arg)))
            else:
                champs = (self._resolve_alias(arg),)
            for champ in champs:
                if champ not in champs_matched:
                    #print(champ.alias_set)
                    em.add_field(name=champ.full_name, value=champ.get_aliases())
                    champs_matched.append(champ)
        await self.bot.say(embed=em)

    @commands.command()
    async def tst(self, key):
        files = {'bio': (kabam_bio, 'ID_CHARACTER_BIOS_', 'mcocjson'),
                 'sig': (kabam_bcg_stat_en, 'ID_UI_STAT_', 'mcocsig')}
        ignore_champs = ('DRONE', 'SYMBIOD')
        if key not in files:
            await self.bot.say('Accepted Key values:\n\t' + '\n\t'.join(files.keys()))
            return
        data = load_kabam_json(files[key][0])
        no_mcocjson = []
        no_kabam_key = []
        data_keys = {k for k in data.keys() if k.startswith(files[key][1])}
        ignore_keys = set()
        for champ in ignore_champs:
            ignore_keys.update({k for k in data_keys if k.find(champ) != -1})
        data_keys -= ignore_keys
        print(ignore_keys)
        for champ in self.champs:
            if not getattr(champ, files[key][2], None):
                no_mcocjson.append(champ.full_name)
                continue
            kabam_key = files[key][1] + getattr(champ, files[key][2])
            champ_keys = {k for k in data.keys() if k.startswith(kabam_key)}
            if not champ_keys:
                no_kabam_key.append(champ.full_name)
            else:
                data_keys -= champ_keys
        if no_mcocjson:
            await self.bot.say('Could not find mcocjson alias for champs:\n\t' + ', '.join(no_mcocjson))
        if no_kabam_key:
            await self.bot.say('Could not find Kabam key for champs:\n\t' + ', '.join(no_kabam_key))
        if data_keys:
            #print(data_keys, len(data_keys))
            if len(data_keys) > 20:
                dump = {k for k in data_keys if k.endswith('TITLE')}
            else:
                dump = data_keys
            await self.bot.say('Residual keys:\n\t' + '\n\t'.join(dump))
        await self.bot.say('Done')

#My intention was to create a hook command group. If nothing is specified, then drop the URL
    @commands.command()
    async def hook(self, args=None):
        if args is None:
            hookTitle = 'Hook Roster Manager'
            hookPayload = '<http://hook.github.io/champions>'
            em = discord.Embed(color=discord.Color.gold(), title=hookTitle, description=hookPayload)
            await self.bot.say(embed=em)
        else:
            await self.bot.say('DEBUG: process hook args')

    def _get_mcoc_keys(self, champ, sigs):
        mcocsig = champ.mcocsig
        preamble = 'undefined'
        title = 'undefined'
        title_lower = 'undefined'
        simple = []
        desc = []

        if mcocsig == 'COMICULTRON':
            mcocsig = 'ULTRON'
        elif mcocsig == 'CYCLOPS_90S':
            mcocsig = 'CYCLOPS'

        titles={'ID_UI_STAT_SIGNATURE_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_{}_SIGNATURE_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIG_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIGNATURE_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIG_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_FORMAT_{}_SIG_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_{}_SIG_TITLE'.format(mcocsig),
            }

        for x in titles:
            if x in sigs:
                title = x

        if title is 'undefined':
            raise KeyError('DEBUG - title not found')
        elif title +'_LOWER' in sigs:
            title_lower = title+'_LOWER'

        preambles ={'ID_UI_STAT_SIGNATURE_{}'.format(mcocsig),
            'ID_UI_STAT_{}_SIGNATURE'.format(mcocsig),
            'ID_UI_STAT_SIG_{}'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIGNATURE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_FORMAT_{}_SIG'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_{}_SIG'.format(mcocsig)}

        for x in preambles:
            if x+'_SIMPLE' in sigs:
                preamble = x
                break


        # if preamble is 'undefined':
        #     raise KeyError('DEBUG - Preamble not found')
        if preamble + '_SIMPLE_NEW' in sigs:
            simple.append(preamble + '_SIMPLE_NEW')
        elif preamble + '_SIMPLE' in sigs:
            simple.append(preamble + '_SIMPLE')
        else:
            raise KeyError('Signature SIMPLE cannot be found')

        champ_exceptions = {
            #'CYCLOPS_90S': ['ID_UI_STAT_SIGNATURE_CYCLOPS_DESC_90S_AO'],
            'LOKI': ['ID_UI_STAT_SIGNATURE_LOKI_LONGDESC'],
            'DEADPOOL': ['ID_UI_STAT_SIGNATURE_DEADPOOL_DESC2_AO'],
            'ULTRON': ['ID_UI_STAT_SIGNATURE_ULTRON_DESC'],
            'COMICULTRON': ['ID_UI_STAT_SIGNATURE_ULTRON_DESC'],
            'BEAST': ['ID_UI_STAT_SIGNATURE_LONGDESC_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_B_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_C_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_D_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_E_AO'],
            'GUILLOTINE': ['ID_UI_STAT_SIGNATURE_GUILLOTINE_DESC'],
        }

        if champ.mcocsig == 'CYCLOPS_90S':
            title = 'ID_UI_STAT_SIGNATURE_CYCLOPS_TITLE'
            title_lower = 'ID_UI_STAT_SIGNATURE_CYCLOPS_TITLE_LOWER'
            desc.append('ID_UI_STAT_SIGNATURE_CYCLOPS_DESC_90S_AO')
        elif mcocsig in champ_exceptions:
            desc.extend(champ_exceptions[mcocsig])
        #elif mcocsig == 'LOKI':
            #desc.append('ID_UI_STAT_SIGNATURE_LOKI_LONGDESC')
        #elif mcocsig == 'DEADPOOL':
            #desc.append('ID_UI_STAT_SIGNATURE_DEADPOOL_DESC2_AO')
        #elif mcocsig == 'ULTRON':
            #desc.append('ID_UI_STAT_SIGNATURE_ULTRON_DESC')
        #elif mcocsig == 'COMICULTRON':
            #desc.append('ID_UI_STAT_SIGNATURE_ULTRON_DESC')
        #elif mcocsig == 'BEAST':
            #desc.append('ID_UI_STAT_SIGNATURE_LONGDESC_AO')
            #desc.append('ID_UI_STAT_SIGNATURE_LONGDESC_B_AO')
            #desc.append('ID_UI_STAT_SIGNATURE_LONGDESC_C_AO')
            #desc.append('ID_UI_STAT_SIGNATURE_LONGDESC_D_AO')
            #desc.append('ID_UI_STAT_SIGNATURE_LONGDESC_E_AO')
        #elif mcocsig == 'GUILLOTINE':
            #desc.append('ID_UI_STAT_SIGNATURE_GUILLOTINE_DESC')
        elif preamble + '_DESC_NEW' in sigs:
            for k in {'_DESC_NEW','_DESC_NEW_B'}:
                if preamble + k in sigs:
                    if preamble + k + '_AO' in sigs:
                        desc.append(preamble + k + '_AO')
                    else:
                        desc.append(preamble + k)
        elif preamble + '_5STAR_DESC_MOD' in sigs:
            desc.append(preamble+'_DESC_MOD')
        else:
            for k in {'_DESC','_DESC_B'}:#,'_DESC2','_DESC3'}:
                if preamble + k in sigs:
                    if preamble + k + '_ALT' in sigs:
                        desc.append(preamble + k + '_ALT')
                    elif preamble + k + '_AO' in sigs:
                        desc.append(preamble + k + '_AO')
                    else:
                        desc.append(preamble + k)

        if champ.mcocsig == 'IRONMAN_SUPERIOR':
            desc.append('ID_UI_STAT_SIGNATURE_IRONMAN_DESC_B_AO')

        return title, title_lower, simple, desc

    def get_roster(self, server, role : discord.Role):
        cnt = 0
        line_out = []
        for member in server.members:
            if role in member.roles:
                cnt +=1
                line_out.append(member.display_name)
        return (cnt, line_out)

    def _prepare_aliases(self):
        '''Create a python friendly data structure from the aliases json'''
        raw_data = dataIO.load_json(data_files['crossreference']['local'])
        champs = []
        all_aliases = set()
        id_index = False
        for row in raw_data['feed']['entry']:
            cells = self.split_re.split(row['content']['$t'])
            if id_index is False:
                id_index = 0
                for i in cells:
                    id_index += 1
                    if i.startswith('champ:'):
                        break
            key_values = {}
            alias_set = set()
            for i in range(len(cells)):
                try:
                    k, v = cells[i].split(': ')
                except:
                    print('DEBUG: ', i, cells[i])
                    raise
                key_values[k] = v
                if i < id_index:
                    if v != 'n/a':
                        alias_set.add(v.lower())
            if all_aliases.isdisjoint(alias_set):
                all_aliases.union(alias_set)
            else:
                raise KeyError("There are aliases that conflict with previous aliases."
                        + "  First occurance with champ {}.".format(key_values['champ']))
            #champs.append(Champion(alias_set, **key_values, debug=len(champs)==0))
            champs.append(Champion(alias_set, **key_values))
        self.champs = champs

    def _prepare_frogspawn_champ_data(self):
        champ_data = dataIO.load_json(data_files['frogspawn']['local'])
        for champ in self.champs:
            if getattr(champ, 'frogspawnid', None):
                champ.update_frogspawn(champ_data.get(champ.frogspawnid))

    def _resolve_alias(self, alias, raise_err=True):
        for champ in self.champs:
            if champ.re_alias.fullmatch(alias):
                return champ
        if raise_err:
            raise KeyError("Champion for alias '{}' not found".format(alias))
        else:
            return None

    def _resolve_mult_aliases(self, match_str):
        re_champ = re.compile(match_str)
        champs = []
        for champ in self.champs:
            for alias in champ.alias_set:
                if re_champ.fullmatch(alias):
                    champs.append(champ)
                    break
        return champs

    def _google_json_content_split(self, row):
            return dict([kv.split(': ') for kv in self.split_re.split(row['content']['$t'])])

    def _prepare_prestige_data(self):
        mattkraft_re = re.compile(r'(?P<star>\d)-(?P<champ>.+)-(?P<rank>\d)')
        raw_data = dataIO.load_json(data_files['spotlight']['local'])
        champs = {}
        for row in raw_data['feed']['entry']:
            raw_dict = self._google_json_content_split(row)
            champ_match = mattkraft_re.fullmatch(raw_dict['mattkraftid'])
            if champ_match:
                champ_name = champ_match.group('champ')
                champ_star = int(champ_match.group('star'))
                champ_rank = int(champ_match.group('rank'))
            else:
                continue
            if champ_name not in champs:
                champs[champ_name] = {}
                champs[champ_name][4] = [None] * 5
                champs[champ_name][5] = [None] * 5
            if champ_star == 5:
                sig_len = 201
            else:
                sig_len = 100
            key_values = {}
            sig = [0] * sig_len
            for k, v in raw_dict.items():
                if k.startswith('sig'):
                    try:
                        if (int(k[3:]) < sig_len) and v != '#N/A':
                            sig[int(k[3:])] = int(v)
                    except:
                        print(champ_name, k, v, len(sig))
                        raise
            try:
                champs[champ_name][champ_star][champ_rank-1] = sig
            except:
                print(champ_name, champ_star, champ_rank, len(champs[champ_name]), len(champs[champ_name][champ_star]))
                raise
        dataIO.save_json(prestige_data, champs)
        for champ in self.champs:
            if champ.mattkraftid in champs:
                champ.prestige_data = champs[champ.mattkraftid]


def validate_attr(*expected_args):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            for attr in expected_args:
                if getattr(self, attr + '_data', None) is None:
                    raise AttributeError("{} for Champion ".format(attr.capitalize())
                        + "'{}' has not been initialized.".format(self.champ))
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class Champion:

    def __init__(self, alias_set, *args, debug=0, **kwargs):
        self.alias_set = alias_set
        self.re_alias = re.compile('|'.join(alias_set), re.I)
        self.frogspawn_data = None
        if debug:
            print(kwargs)
        for key, value in kwargs.items():
            if value == 'n/a':
                value = None
            setattr(self, key, value)
        self.full_name = self.champ
        self.bold_name = '**' + ' '.join(
            [word.capitalize() for word in self.full_name.split(' ')]) + '**'
        self.class_color = class_color_codes[getattr(self, 'class', 'default')]

    def update_frogspawn(self, data):
        self.frogspawn_data = data

    def getSigValue(self, siglvl, i=None):
        '''Python port of siglvl interpolator from
        http://coc.frogspawn.de/champions/js/functions.js'''
        if i is None:
            base = self.frogspawn_data['sb']
            multi = self.frogspawn_data['sm']
        else:
            base = self.frogspawn_data['sb'][i]
            multi = self.frogspawn_data['sm'][i]
        if siglvl > 0 and base:
            return round(base + log2(siglvl) * multi, 1)
        else:
            return '-'

    def get_avatar(self):
        #print('{}{}.png'.format(champ_avatar, self.mcocui))
        return '{}{}.png'.format(champ_avatar, self.mcocui)

    def get_portrait(self):
        return '{}{}.png'.format(champ_portraits, self.mcocui)

    def get_featured(self):
        return '{}{}.png'.format(champ_featured, self.mcocui)

    #@validate_attr('frogspawn')
    def get_bio(self):
        #return self.frogspawn_data['bio']
        bios = load_kabam_json(kabam_bio)
        key = 'ID_CHARACTER_BIOS_' + self.mcocjson
        if key not in bios:
            raise KeyError('Cannot find Champion {} in data files'.format(self.full_name))
        return bios[key]

    def get_special_attacks(self):
        specials = load_kabam_json(kabam_special_attacks)
        prefix = 'ID_SPECIAL_ATTACK_'
        desc = 'DESCRIPTION_'
        zero = '_0'
        one = '_1'
        two = '_2'
        s0 = specials[prefix + self.mcocjson + zero]
        s1 = specials[prefix + self.mcocjson + one]
        s2 = specials[prefix + self.mcocjson + two]
        s0d = specials[prefix + desc + self.mcocjson + zero]
        s1d = specials[prefix + desc + self.mcocjson + one]
        s2d = specials[prefix + desc + self.mcocjson + two]
        specials = (s0, s1, s2, s0d, s1d, s2d)
        return specials

    @validate_attr('frogspawn')
    def get_sig(self, **kwargs):
        sig_str = self._sig_header(self.frogspawn_data['sd'])
        siglvl = bound_lvl(kwargs['siglvl'])
        str_data = []
        for i in range(len(self.frogspawn_data['sn'])):
            if self.frogspawn_data['sn'][i] != 0:
                str_data.append(self.frogspawn_data['sn'][i])
            elif isinstance(self.frogspawn_data['sb'], list):
                str_data.append(self.getSigValue(siglvl, i))
            else:
                str_data.append(self.getSigValue(siglvl))
        return ('Signature Ability for {}'.format(
                self.full_name.capitalize()), sig_str.format(*str_data), siglvl)

    @validate_attr('frogspawn')
    def get_sigarray(self, sigstep=20, width=10, inc_zero=False, **kwargs):
        '''Retrieve the Signature Ability of a Champion at multiple levels'''
        var_list = 'XYZABCDEF'
        sig_str = self._sig_header(self.frogspawn_data['sd'])
        str_data = []
        sigstep_arr = bound_lvl(list(range(0, 101, sigstep)))
        if inc_zero:
            sigstep_arr.insert(1, 1)
        else:
            sigstep_arr[0] = 1
        table_data = [[''] + sigstep_arr]
        count = 0
        for i in range(len(self.frogspawn_data['sn'])):
            if self.frogspawn_data['sn'][i] != 0:
                str_data.append(self.frogspawn_data['sn'][i])
            elif '{' + str(i) + '}' in sig_str:
                table_data.append([var_list[count]])
                str_data.append(var_list[count])
                for j in sigstep_arr:
                    if isinstance(self.frogspawn_data['sb'], list):
                        table_data[-1].append(self.getSigValue(j, i))
                    else:
                        table_data[-1].append(self.getSigValue(j))
                count += 1
            else:
                # nothing to do if there is no valid sub in sig_str
                #  but we need to make sure the length is correct for format
                str_data.append('dummy')
        title = 'Signature Ability for {} at multiple Sig Levels:'.format(
                self.bold_name)
        response = sig_str.format(*str_data) + tabulate(table_data, width=width)
        return (title, response)

    @validate_attr('prestige')
    def get_prestige(self, *, rank, sig, star, value=False):
        if star == 5 and rank == 5:
            #silently reduce to max rank for 5*
            rank = 4
        if self.prestige_data[star][rank-1] is None:
            return 0 if value else None
        if value:
            return self.prestige_data[star][rank-1][sig]
        else:
            return {'name':'{}*{}r{}s{}'.format(star, self.short, rank, sig),
                    'value':self.prestige_data[star][rank-1][sig]}

    @validate_attr('prestige')
    def get_prestige_arr(self, rank, sig_arr, star=4):
        row = ['{}r{}'.format(self.short, rank)]
        for sig in sig_arr:
            try:
                row.append(self.prestige_data[star][rank-1][sig])
            except:
                print(rank, sig, self.prestige_data)
                raise
        return row


    def get_aliases(self):
        return '```{}```'.format(', '.join(self.alias_set))

    @staticmethod
    def _sig_header(str_data):
        hex_re = re.compile(r'\[[0-9a-f]{6,8}\](.+?)\[-\]', re.I)
        return hex_re.sub(r'**\1**', str_data)
        # return hex_re.sub(r'**[ \1 ]**', str_data)

def bound_lvl(siglvl, max_lvl=99):
    if isinstance(siglvl, list):
        ret = []
        for j in siglvl:
            if j > max_lvl:
                j = max_lvl
            elif j < 0:
                j = 0
            ret.append(j)
    else:
        ret = siglvl
        if siglvl > max_lvl:
            ret = max_lvl
        elif siglvl < 0:
            ret = 0
    return ret

def tabulate(table_data, width, do_rotate=True, header_sep=True):
    rows = []
    cells_in_row = None
    for i in rotate(table_data, rotate):
        if cells_in_row is None:
            cells_in_row = len(i)
        elif cells_in_row != len(i):
            raise IndexError("Array is not uniform")
        rows.append('|'.join(['{:^{width}}']*len(i)).format(*i, width=width))
    if header_sep:
        rows.insert(1, '|'.join(['-' * width] * cells_in_row))
    return '```' + '\n'.join(rows) + '```'

def rotate(array, do_rotate):
    if not do_rotate:
        for i in array:
            yield i
    for j in range(len(array[0])):
        row = []
        for i in range(len(array)):
            row.append(array[i][j])
        yield row

def load_kabam_json(file):
    raw_data = dataIO.load_json(file)
    data = {}
    for d in raw_data['strings']:
        data[d['k']] = d['v']
    return data

def _truncate_text(self, text, max_length):
    if len(text) > max_length:
        if text.strip('$').isdigit():
            text = int(text.strip('$'))
            return "${:.2E}".format(text)
        return text[:max_length-3] + "..."
    return text
# Creation of lookup functions from a tuple through anonymous functions
#for fname, docstr, link in MCOC.lookup_functions:
    #async def new_func(self):
        #await self.bot.say('{}\n{}'.format(docstr, link))
        #raise Exception
    ##print(new_func)
    ##setattr(MCOC, fname, commands.command(name=fname, help=docstr)(new_func))
    #new_func = commands.command(name=fname, help=docstr)(new_func)
    #setattr(MCOC, fname, new_func)
    ##print(getattr(MCOC, fname).name, getattr(MCOC, fname).callback)



def setup(bot):
    # if hook is None:
    #     raise RuntimeError('Please install mcoc-cogs hook')
    # if clanmod is None:
    #     raise RuntimeError('Please install mcoc-cogs clan_mod')
    bot.add_cog(MCOC(bot))
