import datetime
import logging
import requests

import pajbot.models
import pajbot.utils
from pajbot.actions import ActionQueue
from pajbot.managers.db import DBManager
from pajbot.managers.schedule import ScheduleManager
from pajbot.models.dotabet import DotaBetBet
from pajbot.models.dotabet import DotaBetGame
from pajbot.modules import BaseModule
from pajbot.modules import ModuleType
from pajbot.modules import ModuleSetting

log = logging.getLogger(__name__)

class ExitLoop(Exception):
    pass


class Bet(object):
    # Individual bet made by a user
    def __init__(self, *args,source,message,specating,**kwargs):
        self.valid_bet = True
        self.error = None
        self.source = source
        self.spectating = spectating
        self.initiate_bet(message)
    
    def initiate_bet(self,message):
        # Initiated when user sends bet command
        outcome,points = message.split(' ')
        outcome = outcome.lower()
        
        if 'w' in outcome or 'radi' in outcome:
            self.bet_for_win = True
        elif 'l' in outcome or 'dire' in outcome:
            self.bet_for_win = False
        else:
            self.valid_bet = False
            self.error = 'Invalid bet. You must do !dotabet radiant/dire ' \
                         'POINTS (if spectating a game) or !dotabet ' \
                         'win/loss POINTS (if playing)'
            return
        
        try:
            self.points = pajbot.utils.parse_points_amount(source, msg_parts[1])
            if self.points > 1000:
                self.points = 1000
            elif points <= 0:
                self.valid_bet = False
                self.error = 'The fuck you tryna do?'
                return
            
        except pajbot.exc.InvalidPointAmount as e:
            self.error = 'Invalid bet. You must do !dotabet radiant/dire ' \
                         'POINTS (if spectating a game) or !dotabet ' \
                         'win/loss POINTS (if playing) {}'.format(e))
            self.valid_bet = False
            return

    def approve_bet(self,odds_r, odds_d):
        if self.valid_bet:
            self.source.points -= self.points
            if self.bet_for_win:
                self.odds = odds_r
            else:
                self.odds = odds_d
            
    def evaluate_bet(self,message):
        # Returns result of bet and lets user know result
        
    def query_bet(self,spectating):
        # User can query the bet they made whilst bet is open
        if spectating:
            if self.bet_for_win:
                team = 'Radiant'
            else:
                team = 'Dire'
            return 'You have bet {} points on this game resulting in a {} win at odds of {}'.format(
                    self.points,team,self.odds))
        else:
            return 'You have bet {} points on this game resulting in a w in at odds of {}'.format(self.points,self.odds)

################################################################################
################################################################################
################################################################################
################################################################################
        
class DotaBetModule(BaseModule):
    AUTHOR = 'DatGuy1'
    ID = __name__.split('.')[-1]
    NAME = 'DotA Betting'
    DESCRIPTION = 'Enables betting on DotA 2 games with !dotabet'
    CATEGORY = 'Game'

    SETTINGS = [
            ModuleSetting(
                key='steam3_id',
                label='Steam 3 ID of streamer (number only)',
                type='number',
                required=True,
                placeholder='',
                default=''),
            ModuleSetting(
                key='api_key',
                label='Steam API Key',
                type='text',
                required=True,
                placeholder='',
                default=''),
            ]

    def __init__(self):
        super().__init__()
        self.action_queue = ActionQueue()
        self.action_queue.start()
        self.bets = {}
        self.betting_open = False
        self.message_closed = True
        self.isRadiant = False
        self.matchID = 0
        self.oldID = 0
        self.winBetters = 0
        self.lossBetters = 0
        self.gettingTeam = False
        self.secondAttempt = False
        self.calibrating = True
        self.calibratingSecond = True
        self.jobPaused = False
        self.spectating = False

        self.job = ScheduleManager.execute_every(25, self.poll_webapi)
        self.job.pause()

        self.reminder_job = ScheduleManager.execute_every(200, self.reminder_bet)
        self.reminder_job.pause()

        self.finish_job = ScheduleManager.execute_every(60, self.get_game)
        self.finish_job.pause()

        #self.close_job = ScheduleManager.execute_every(1200, self.bot.websocket_manager.emit, ('dotabet_close_game', ))
        #self.close_job.pause()

        # beansock
        self.bet_list = list() # list of bet objects
        self.betters  = list() # list of names of betters
        self.odds_w   = 2.0    # initial odds of win
        self.odds_l   = 2.0    # initial odds of loss
        self.initial_odds = 2.0 # initial odds for any bias
        self.r_total  = 0      # total possible loss on radiant win
        self.d_total  = 0      # total possible loss on dire win

    def reminder_bet(self):
        if self.betting_open:
            self.bot.me('monkaS 👉 🕒 place your bets people')
            self.bot.websocket_manager.emit('notification', {'message': 'monkaS 👉 🕒 place your bets people'})
        else:
            if not self.message_closed:
                self.bot.me('The betting for the current game has been closed! Winners can expect a {:0.2f} (win betters) or {:0.2f} (loss betters) return ' \
                            'ratio'.format((((self.lossBetters + 1) / (self.winBetters + self.lossBetters + 1)) + 0.15) + 1,
                            (((self.winBetters + 1) / (self.winBetters + self.lossBetters + 1)) + 0.15) + 1))
                self.bot.websocket_manager.emit('notification', {'message': 'The betting for the current game has been closed!'})
                if not self.spectating:
                    self.bot.execute_delayed(15, self.bot.websocket_manager.emit, ('dotabet_close_game', ))
                self.message_closed = True

    def spread_points(self, gameResult):
        winners = 0
        losers = 0
        total_winnings = 0
        total_losses = 0
        total_profit = 0.
        
        #not needed if each person has an individual odds value on their bet
        #if gameResult == 'win':
        #    solveFormula = ((self.lossBetters + 1) / (self.winBetters + self.lossBetters + 1)) + 0.15
        #else:
        #    solveFormula = ((self.winBetters + 1) / (self.winBetters + self.lossBetters + 1)) + 0.15

        with DBManager.create_session_scope() as db_session:
            db_bets = {}
            for bet in self.bet_list:
                
                #bet_for_win, betPoints = self.bets[username]
                #points = int((betPoints + 1) * solveFormula) + 1

                # log.debug(points)
                # log.debug(betPoints)

                user = self.bot.users.find(bet.source.username, db_session=db_session)
                if user is None:
                    continue

                # log.debug(gameResult)
                correct_bet = (gameResult == 'win' and bet.bet_for_win)\
                              or (gameResult == 'loss' and not bet.bet_for_win)
                
                db_bets[bet.source.username] = DotaBetBet(
                    user.id, 'win' if bet.bet_for_win else 'loss', bet.points, 0)

                if correct_bet:
                    winners += 1
                    total_winnings += bet.points * bet.odds
                    profit = bet.points * (bet.odds-1.)
                    total_profit += profit
                    db_bets[username].profit = profit
                    user.points += bet.points * bet.odds
                    user.save()
                    self.bot.whisper(user.username,
                                     'You bet {} points on the correct outcome and gained an extra {} points, ' \
                                     'you now have {} points PogChamp'.format(bet.points, profit, user.points))
                else:
                    losers += 1
                    total_losses += bet.points
                    db_bets[bet.source.username].profit = -betPoints
                    user.save()
                    self.bot.whisper(user.username,
                                     'You bet {} points on the wrong outcome, so you lost it all. :('.format(betPoints))

        startString = 'The game ended as a {}. {} users won a total of {} points, while {}' \
                       ' lost {} points.'.format(
                           gameResult, winners, total_winnings,losers, total_losses,
                           solveFormula + 1)
        if self.spectating:
            resultString = startString[:20] + 'radiant ' + startString[20:]
        else:
            resultString = startString
        real_profit = total_losses - total_profit
        if total_profit > 0.:
            resultString += ' AdmiralBulldog made a profit of {} points off of you degenerate gamblers, damn it feels good to be rich GabeN.'.format(total_profit)
            self.bot.users.find('AdmiralBulldog', db_session=db_session).points += total_profit
            
        for username in db_bets:
            bet = db_bets[username]
            db_session.add(bet)
            # db_session.commit()

        # cleanup at the end of the bet
        # self.bets = {}
        self.betting_open = False
        self.message_closed = True
        self.winBetters = 0
        self.lossBetters = 0

        bet_game = DotaBetGame(gameResult, total_winnings - total_losses, winners, losers)
        db_session.add(bet_game)
        db_session.commit()

        self.bot.websocket_manager.emit('notification', {'message': resultString, 'length': 8})
        self.bot.me(resultString)

    def get_game(self):
        gameResult = 'loss'
        # log.debug(self.isRadiant)

        odURL = 'https://api.opendota.com/api/players/{}/recentMatches'.format(self.settings['steam3_id'])
        gameHistory = requests.get(odURL).json()[0]

        if gameHistory['match_id'] != self.matchID:
            self.matchID = gameHistory['match_id']

            if self.calibrating:
                self.calibrating = False
                return

            if self.isRadiant and gameHistory['radiant_win']:
                gameResult = 'win'
            else:
                if not self.isRadiant and not gameHistory['radiant_win']:
                    gameResult = 'win'
                else:
                    gameResult = 'loss'
            # log.error(gameResult)
            self.spread_points(gameResult)

    def poll_webapi(self):
        serverID = ''

        with open('/srv/admiralbullbot/configs/currentID.txt', 'r') as f:
            serverID = f.read()

        try:
            serverID = int(serverID)
        except:
            return False

        if self.calibratingSecond == True and serverID != 0:
            self.calibratingSecond = False
            return False

        if serverID == 0:
            self.bot.execute_delayed(100, self.close_shit)
            return False

        if self.oldID == serverID:
            return False

        self.oldID = serverID

        self.bot.execute_delayed(12, self.get_team, (serverID, ))

    def get_odds(self):
        # The odds are calculated to give the bookies a 5% return on the
        # total bet value over the long run, it's rigged against the punters
        # but it's their choice to bet or not. If no initial odds are given
        # when the bet is opened, it will be set at evens ( 1.0 returns 1.0 )
        # and the odds that a punter gets will vary simply depending on how
        # much has been bet. If the admin wishes to, he/she may open the bets
        # with an initial odds offering (on radiant win) which will then bias
        # the calculated odds from there on out.

        self.odds_r = (((self.r_total + self.d_total) / self.r_total)-1)*(self.phi * 0.95) + 1.
        self.odds_d = (((self.d_total + self.r_total) / self.d_total)-1)*(self.phi**(-1) * 0.95) + 1.
        
    def startGame(self):
        if not self.betting_open:
            self.bets = {}
            self.betting_open = True
            self.message_closed = False
            self.winBetters = 0
            self.lossBetters = 0
            self.bot.websocket_manager.emit('dotabet_new_game')

        bulldogTeam = 'radiant' if self.isRadiant else 'dire'
        openString = 'A new game has begun! Bulldog is on {}. Vote with !dotabet win/lose POINTS'.format(bulldogTeam)

        self.bot.websocket_manager.emit('notification', {'message': openString})
        # self.bot.websocket_manager.emit('dotabet_new_game')

        self.bot.me(openString)

    def get_team(self, serverID):
        attempts = 0
        if not serverID:
            return

        webURL = 'https://api.steampowered.com/IDOTA2MatchStats_570/GetRealtimeStats/v1?' \
                 'server_steam_id={}&key={}'.format(serverID, self.settings['api_key'])
        jsonText = requests.get(webURL).json()

        try:
            while not jsonText: # Could bug and not return anything
                if attempts > 60:
                    if not self.secondAttempt:
                        self.bot.execute_delayed(20, self.get_team, (serverID, ))
                        self.secondAttempt = True
                    else:
                        self.bot.say('Couldn\'t find which team Bulldog is on for this game. Mods - handle this round manually :)')
                        self.job.pause()
                        self.jobPaused = True
                        self.secondAttempt = False

                    attempts = 0
                    return

                attempts += 1
                jsonText = requests.get(webURL).json()
                log.debug(jsonText)

                try:
                    self.gettingTeam = True
                    for i in range(2):
                        for player in jsonText['teams'][i]['players']:
                            log.debug(player['name'])
                            if player['accountid'] == self.settings['steam3_id']:
                                if i == 0:
                                    self.isRadiant = True
                                else:
                                    self.isRadiant = False
                                self.bot.me('Is bulldog on radiant? {}. If he isn\'t then tag a mod with BabyRage fix ' \
                                            'bet'.format(self.isRadiant))
                                raise ExitLoop
                except KeyError:
                    jsonText = ''

        except ExitLoop:
            pass

        self.gettingTeam = False
        self.betting_open = True
        self.secondAttempt = False
        self.startGame()

    def command_open(self, **options):
        openString = 'Betting has been opened'
        bot = options['bot']
        message = options['message']
        self.calibrating = True

        if message:
            if 'dire' in message or message.lower() == 'd':
                self.isRadiant = False
            elif 'radi' in message or message.lower() == 'r':
                self.isRadiant = True
            elif 'spectat' in message or message.lower() == 's':
                self.isRadiant = True
                self.spectating = True
                openString += '. Reminder to bet with radiant/dire instead of win/loss'
                self.calibrating = False
        try:
            m = message.split(' ')
            initial = float(m[1])
            if self.isRadiant:
                self.phi = initial / 2.
            else:
                self.phi = 2. / initial
        except:
            self.phi = 1.0
        if self.spectating:
            openstring +='. The opening odds for a Radiant win have been set at {:.02f}:1'.format(self.odds_w)
        else:
            openstring +='. The opening odds for a win have been set at {:.02f}:1'.format(self.odds)    
        if not self.betting_open:
            self.bets = {}
            self.winBetters = 0
            self.lossBetters = 0
            bot.websocket_manager.emit('notification', {'message': openString})
            if not self.spectating:
                bot.websocket_manager.emit('dotabet_new_game')
            bot.me(openString)

        self.betting_open = True
        self.message_closed = False
        self.job.pause()
        self.jobPaused = True

    def command_stats(self, **options):
        bot = options['bot']
        source = options['source']

        bot.say('Current win/lose points: {}/{}'.format(self.winBetters, self.lossBetters))

    def close_shit(self):
        if self.jobPaused:
            return False

        self.betting_open = False
        self.reminder_bet()

    def command_close(self, **options):
        bot = options['bot']
        source = options['source']
        message = options['message']

        if message:
            if 'l' in message.lower() or 'dire' in message.lower():
                self.spread_points('loss')
            else:
                self.spread_points('win')
            self.bets = {}
            self.winBetters = 0
            self.lossBetters = 0
            self.calibrating = True
            self.spectating = False

        if self.betting_open:
            bot.me('Betting will be locked in 15 seconds! Place your bets people monkaS')
            bot.execute_delayed(15, self.lock_bets, (bot,))

    def lock_bets(self, bot):
        self.betting_open = False
        self.reminder_bet()
        self.job.resume()
        self.jobPaused = False

    def command_restart(self, **options):
        bot = options['bot']
        message = options['message']
        source = options['source']
        reason = ''

        if not message:
            reason = 'No reason given EleGiggle'
        else:
            reason = message

        with DBManager.create_session_scope() as db_session:
            for username in self.bets:
                bet_for_win, betPoints = self.bets[username]
                user = self.bot.users.find(username, db_session=db_session)
                if not user:
                    continue

                user.points += betPoints
                bot.whisper(user.username, 'Your {} points bet has been refunded. The reason given is: ' \
                                           '{}'.format(betPoints, reason))

        self.bets = {}
        self.betting_open = False
        self.message_closed = True

        self.winBetters = 0
        self.lossBetters = 0

        bot.me('All your bets have been refunded and betting has been restarted.')

    def command_resetbet(self, **options):
        self.bets = {}
        options['bot'].me('The bets have been reset :)')
        self.winBetters = 0
        self.lossBetters = 0

    def command_betstatus(self, **options):
        bot = options['bot']
        if self.betting_open:
            bot.say('Betting is open')
        elif self.winBetters > 0 or self.lossBetters > 0:
            bot.say('There is currently a bet with points not given yet')
        else:
            bot.say('There is no bet running')

    def command_bet(self, **options):
        bot = options['bot']
        source = options['source']
        message = options['message']
        
        # Check if bet is valid
        if not message:
            return False

        if not self.betting_open:
            bot.whisper(source.username, \
                        'Betting is not currently open. ' \
                        'Wait until the next game :\\')
            return False
        
        if len(message.split(' ')) < 2:
            bot.whisper(source.username, \
                        'Invalid bet. You must do !dotabet radiant/dire ' \
                        'POINTS (if spectating a game) or !dotabet ' \
                        'win/loss POINTS (if playing)')
            return False

        # Create bet from inputs
        bet = Bet(spectating=self.spectating, **options)
        
        if not bet.valid_bet:
            bot.whisper(bet.source.username, bet.error)
            return False
        elif not bet.source.can_afford(bet.points):
            bot.whisper(bet.source.username,
                        'You don\'t have {} points to bet'.format(bet.points))
            return False
        elif bet.source.username in self.betters:
            bot.whisper(source.username,
                        'You have already bet on this game. '\
                        'Wait until the next game starts!')
            return False
        else:
            #load bet in to list  
            self.betters.append(bet.source.username)
            if bet.bet_for_win:
                bet.approve_bet(self.odds_r)
                self.r_total  += bet.points
            else:
                bet.approve_bet(self.odds_d)
                self.d_total += bet.points
            self.bet_list.append(bet)


        payload = {'win_betters' : self.winBetters,
                   'loss_betters': self.lossBetters,
                   'win'         : 0,
                   'loss'        : 0}
        
        if bet.bet_for_win:
            payload['win']  = bet.points
            
        else:
            payload['loss'] = bet.points
            
        if not self.spectating:
            bot.websocket_manager.emit('dotabet_update_data', data=payload)

        bot.whisper(bet.source.username, bet.query_bet())

    def load_commands(self, **options):
        self.commands['dotabet'] = pajbot.models.command.Command.raw_command(self.command_bet,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=True,
            description='Bet points',
            examples=[
                pajbot.models.command.CommandExample(None, 'Bet 69 points on a win',
                    chat='user:!dotabet win 69\n'
                    'bot>user: You have bet 69 points on this game resulting in a win.',
                    description='Bet that the streamer will win for 69 points').parse(),
                ],
            )
        self.commands['bet'] = self.commands['dotabet']

        self.commands['openbet'] = pajbot.models.command.Command.raw_command(self.command_open,
            level = 420,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=True,
            description='Open bets',
            )
        self.commands['restartbet'] = pajbot.models.command.Command.raw_command(self.command_restart,
            level = 500,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=True,
            description='Restart bets',
            )
        self.commands['closebet'] = pajbot.models.command.Command.raw_command(self.command_close,
            level = 420,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=True,
            description='Close bets',
            )
        self.commands['resetbet'] = pajbot.models.command.Command.raw_command(self.command_resetbet,
            level = 500,
            can_execute_with_whisper=True,
            description='Reset bets',
            )
        self.commands['betstatus'] = pajbot.models.command.Command.raw_command(self.command_betstatus,
            level = 500,
            can_execute_with_whisper=True,
            description='Status of bets',
            )
        self.commands['currentbets'] = pajbot.models.command.Command.raw_command(self.command_stats,
            level=100,
            delay_all=0,
            delay_user=10,
            can_execute_with_whisper=True,
            )
        # self.commands['betstats']

    def enable(self, bot):
        if bot:
            self.job.resume()
            self.reminder_job.resume()
            self.finish_job.resume()
            #self.close_job.resume()
        self.bot = bot

    def disable(self, bot):
        if bot:
            self.job.pause()
            self.reminder_job.pause()
            self.finish_job.pause()
            #self.close_job.pause()
