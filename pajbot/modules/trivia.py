import base64
import datetime
import logging
import math

import Levenshtein
import requests
from collections import Counter

import pajbot.models
from pajbot.managers.db import DBManager
from pajbot.managers.handler import HandlerManager
from pajbot.managers.schedule import ScheduleManager
from pajbot.modules import BaseModule
from pajbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class TriviaModule(BaseModule):

    ID = __name__.split('.')[-1]
    NAME = 'Trivia'
    DESCRIPTION = 'Trivia!'
    CATEGORY = 'Game'
    SETTINGS = [
            ModuleSetting(
                key='hint_count',
                label='How many hints the user should get before the question is ruined.',
                type='number',
                required=True,
                default=2,
                constraints={
                    'min_value': 0,
                    'max_value': 4,
                    }),
            ModuleSetting(
                key='step_delay',
                label='Time between each step (step_delay*(hint_count+1) = length of each question)',
                type='number',
                required=True,
                placeholder='',
                default=10,
                constraints={
                    'min_value': 5,
                    'max_value': 45,
                    }),
            ModuleSetting(
                key='default_point_bounty',
                label='Default point bounty per right answer',
                type='number',
                required=True,
                placeholder='',
                default=0,
                constraints={
                    'min_value': 0,
                    'max_value': 1000,
                    }),
            ]

    def __init__(self):
        super().__init__()

        self.job = ScheduleManager.execute_every(1, self.poll_trivia)
        self.job.pause()
        self.checkjob = ScheduleManager.execute_every(10, self.check_run)
        self.checkjob.pause()
        self.checkPaused = True

        self.jservice = False
        self.trivia_running = False
        self.manualStart = False
        self.last_question = None
        self.question = None
        self.step = 0
        self.last_step = None
        self.correct_dict = {}
<<<<<<< HEAD
        
        self.gazCategories = ['W_OMEGALUL_W', 'Vietnam', 'Video_Games',
                              'Video Games', 'Twitch', 'Sports', 'Spongebob',
                              'Jokes', 'Science', 'Programming', 'Music',
                              'Memes', 'Math', 'Maths', 'Movies', 'Languages',
                              'History', 'Geography', 'Gachimuchi', 'Gachi',
                              'Emotes', 'Bees', 'Country', 'Books']
        
        self.recent_questions = list() # List of most recent questions
        self.q_memory = 200            # No. of recent questions to remember
        self.winstreak = [None,None]   # Stored winstreak [user name, winstreak]
        self.min_streak = 3            # minimum correct answers for a streak 
        
=======
        self.recent_questions = list()   # List of most recent questions
>>>>>>> 25b80a2213da36420ecb4c4d7951f9b4a35101ac
        self.point_bounty = 0
        self.q_memory = 0                # No. of recent questions to remember
        self.winstreak = [None,None]     # Stored winstreak [user name, winstreak]
        self.min_streak = 5              # minimum correct answers for a streak to show up
        
    def format_question(self):
        self.question['answer'] = self.question['answer'].replace('<i>', '').replace('</i>', '').replace('\\', '').replace('(', '').replace(')', '')
        self.question['answer'] = self.question['answer'].strip('"').strip('.')

        if self.question['answer'].startswith('a '):
            self.question['answer'] = self.question['answer'].replace('a ', '')
            
        elif self.question['answer'].startswith('an '):
            self.question['answer'] = self.question['answer'].replace('an ', '')
            
        if self.question['answer'].lower().startswith('the '):
            self.question['answer'] = self.question['answer'].replace('the ', '')
                    
    ############################################################################        
    ############################################################################
    
    def poll_trivia(self):
<<<<<<< HEAD
        #######################################################################
        #######################################################################
        # Check if new question needed
        if self.question is None and \
        ( self.last_question is None \
          or (datetime.datetime.now() - self.last_question) \
          >= datetime.timedelta(seconds=11) ):


            # GET TRIVIA QUESTION

            new_question = False
            if self.jservice:
                # Load from jservice database

                while not new_question:
                    r = requests.get('http://jservice.io/api/random')
                    self.question = r.json()[0]

                    # check question isn't repeat of recent one.
                    if self.question['question'] not in self.recent_questions:
                        self.format_question()
                        self.recent_questions.append(self.question['question'])
                        new_question = True

            else:
                # Load from gazatu and opentdb
                chosenInt = random.randint(0, 10)
                if chosenInt < 3: # load opentdb
                    self.gazatuService = True
                    category = random.choice([9, 11, 15, 17, 18, 20, 21, 22, 23,
                                              24, 26, 27, 29, 30])
                    while not new_question:                                       
                        r = requests.get('https://opentdb.com/api.php?amount=1&category={}&type=multiple&encode=base64'.format(category))
                        try:
                            resjson = r.json()['results'][0]
                        except:
                            return

                        self.question = {}
                        self.question['question'] = base64.b64decode(resjson['question']).decode('utf-8')

                        # Should take care of answers like 'eighteen,' etc.
                        startAnswer = base64.b64decode(resjson['correct_answer']).decode('utf-8')
                        try:
                            self.question['answer'] = str(w2n.word_to_num(startAnswer))
                        except ValueError:
                            self.question['answer'] = startAnswer

                        self.question['answer'] = self.question['answer'].strip()
                        self.question['category'] = base64.b64decode(resjson['category']).decode('utf-8')
                        # check question isn't repeat of recent one.
                        if self.question['question'] not in self.recent_questions:
                            self.recent_questions.append(self.question['question'])
                            new_question = True
                else:
                    self.gazatuService = True
                    # category = random.choice(self.gazCategories)
                    # r = requests.get('https://api.gazatu.xyz/trivia/questions?count=1&include=[{}]'.format(category)) # Can do ','.join(categories) but this way it's more varied
                    while not new_question:
                        r = requests.get('https://api.gazatu.xyz/trivia/questions?count=1&include=[{}]'.format(','.join(self.gazCategories)))
                        resjson = r.json()[0]
                        if resjson['disabled']:
                            self.question = None
                            return
                        self.question = resjson
                        if self.question['question'] not in self.recent_questions:
                            self.recent_questions.append(self.question['question'])
                            self.question['category'] = self.question['category'].replace('_', ' ')
                            new_question = True
            # Remove oldest question
            if len(self.recent_questions) > self.q_memory:
                del self.recent_questions[0]
                
            ## FIXME: Cleanup this bullshit
            if not self.question['answer'] or not self.question['question'] or \
               'href=' in self.question['answer'] or \
               'Which of these' in self.question['question'] or \
               'Which one of these' in self.question['question'] or \
               'Which of the following' in self.question['question']):

=======
        # Load question if no current question or time since last question
        if self.question is None \
        and (self.last_question is None \
             or datetime.datetime.now() \
             - self.last_question >= datetime.timedelta(seconds=12)):
            # get question if database loaded
            if self.jservice:
                getting_question = True
                while getting_question:
                    r = requests.get('http://jservice.io/api/random')
                    self.question = r.json()[0]
                    
                    self.format_question()
                    # check question isn't repeat of recent one.
                    if self.question['question'] not in self.recent_questions:
                        if len(self.recent_questions) > self.q_memory:
                            del self.recent_questions[0]
                        self.recent_questions.append(self.question['question'])
                        getting_question = False
            else:
                r = requests.get('https://opentdb.com/api.php?amount=1&category=15&type=multiple&encode=base64')
                resjson = r.json()['results'][0]
                self.question = {}
                self.question['question'] = base64.b64decode(resjson['question']).decode('utf-8')
                self.question['answer'] = base64.b64decode(resjson['correct_answer']).decode('utf-8')
                self.recent_questions.append(self.question)
            if len(self.question['answer']) == 0 or len(self.question['question']) <= 1 or 'href=' in self.question['answer'] or 'Which of these' in self.question['answer']:
>>>>>>> 25b80a2213da36420ecb4c4d7951f9b4a35101ac
                self.question = None
                return

            self.step = 0
            self.last_step = None

        ########################################################################
        ########################################################################
        # Is it time for the next step?
        
        if self.last_step is None or (datetime.datetime.now() - self.last_step >= datetime.timedelta(seconds=self.settings['step_delay']):
            self.last_step = datetime.datetime.now()
            self.step += 1

            if self.step == 1:
                self.step_announce()
            elif self.step < self.settings['hint_count'] + 2:
                self.step_hint()
            else:
                self.step_end()

    def step_announce(self):
        try:
            if self.jservice:
                self.bot.me('PogChamp A new question has begun! In the category "{0[category][title]}", the question/hint/clue is "{0[question]}" Bruh'.format(self.question))
            else:
                self.bot.me('PogChamp A new question has begun! The question is: "{0[question]}"'.format(self.question))
        except:
            self.step = 0
            self.question = None
            pass

    def step_hint(self):
        # find out what % of the answer should be revealed
        full_hint_reveal = int(math.floor(len(self.question['answer']) / 2))
        current_hint_reveal = int(math.floor(((self.step) / 2.2) * full_hint_reveal))
        hint_arr = []
        index = 0
        for c in self.question['answer']:
            if c == ' ':
                hint_arr.append(' ')
            else:
                if index < current_hint_reveal:
                    hint_arr.append(self.question['answer'][index])
                else:
                    hint_arr.append('_')
            index += 1
        hint_str = ''.join(hint_arr)
        if (hint_str == hint_str[0] * len(hint_str)) and len(self.question['answer']) > 1:
            copy_str = self.question['answer'][0]
            copy_str += hint_str[1:]
            hint_str = copy_str

        self.bot.me('OpieOP Here\'s a hint, "{hint_str}" OpieOP'.format(hint_str=hint_str))

    def step_end(self):
        if self.question is not None:
            self.bot.me('MingLee No one could answer the trivia! The answer was "{}" MingLee. Since you\'re all useless, DatGuy gets one point.'.format(self.question['answer']))
            self.question = None
            self.step = 0
            self.last_question = datetime.datetime.now()
            with DBManager.create_session_scope() as db_session:
                user = self.bot.users.find('datguy1', db_session=db_session)
                user.points += 1

    def check_run(self):
        if self.bot.is_online:
             if self.trivia_running and not self.manualStart:
                self.stop_trivia()
        else:
            if not self.trivia_running:
                self.manualStart = False
                self.start_trivia()

    def start_trivia(self, message = None):
        if self.checkPaused and not self.manualStart:
            return

        self.trivia_running = True
        self.job.resume()

        try:
            self.point_bounty = int(message)
            if self.point_bounty < 0:
                self.point_bounty = 0
        except:
            self.point_bounty = self.settings['default_point_bounty']

        if self.point_bounty > 0:
            self.bot.me('The trivia has started! {} points for each right answer!'.format(self.point_bounty))
        else:
            self.bot.me('The trivia has started!')

        HandlerManager.add_handler('on_message', self.on_message)

    def stop_trivia(self):
        self.job.pause()
        self.trivia_running = False
        self.step_end()
        stopOutput = 'The trivia has been stopped. The top five participants are: '

        c = Counter(self.correct_dict)

        for player, correct in c.most_common(5):
            stopOutput += f'{player}, with {correct} correct guesses. '

        self.bot.me(stopOutput)
        self.correct_dict = {}

        HandlerManager.remove_handler('on_message', self.on_message)

    def command_start(self, **options):
        bot = options['bot']
        source = options['source']
        message = options['message']

        if self.trivia_running:
            bot.me('{}, a trivia is already running'.format(source.username_raw))
            return

        self.manualStart = True
        self.start_trivia(message)
        self.checkPaused = False
        self.checkjob.resume()


    def command_stop(self, **options):
        bot = options['bot']
        source = options['source']

        if not self.trivia_running:
            bot.me('{}, no trivia is active right now'.format(source.username_raw))
            return

        self.stop_trivia()
        self.checkPaused = True
        self.checkjob.pause()

    def on_message(self, source, message, emotes, whisper, urls, event):
        if message is None:
            return

        if self.question:
            right_answer = self.question['answer'].lower()
            user_answer = message.lower()
            if len(right_answer) <= 5:
                correct = right_answer == user_answer
            else:
                ratio = Levenshtein.ratio(right_answer, user_answer)
                correct = ratio >= 0.86

            if correct:
                if self.point_bounty > 0:
                    self.bot.me('{} got the answer right! The answer was {} FeelsGoodMan They get {} points! PogChamp'.format(source.username_raw, self.question['answer'], self.point_bounty))
                    source.points += self.point_bounty
                else:
                    self.bot.me('{} got the answer right! The answer was {} FeelsGoodMan'.format(source.username_raw, self.question['answer']))

                self.question = None
                self.step = 0
                self.last_question = datetime.datetime.now()
                self.correct_dict[source.username_raw] = self.correct_dict.get(source.username_raw, 0) + 1
<<<<<<< HEAD
                                      
                # record winstreak of correct answers for user
=======
                # record winstreak of correct answers for user

>>>>>>> 25b80a2213da36420ecb4c4d7951f9b4a35101ac
                if source.username_raw != self.winstreak[0]:
                    self.winstreak = [source.username_raw, 1]
                else:
                    self.winstreak[1] += 1
                    if self.winstreak[1] >= self.min_streak:
<<<<<<< HEAD
                        self.bot.me('{} is on a {} streak of correct answers PogU'.format(
                            *self.winstreak))
=======
                        self.bot.me('{} is on a {} answer streak PogU '.format(
                            *self.winstreak))
                

>>>>>>> 25b80a2213da36420ecb4c4d7951f9b4a35101ac

    def load_commands(self, **options):
        self.commands['trivia'] = pajbot.models.command.Command.multiaction_command(
                level=100,
                delay_all=0,
                delay_user=0,
                can_execute_with_whisper=True,
                commands={
                    'start': pajbot.models.command.Command.raw_command(
                        self.command_start,
                        level=500,
                        delay_all=0,
                        delay_user=10,
                        can_execute_with_whisper=True,
                        ),
                    'stop': pajbot.models.command.Command.raw_command(
                        self.command_stop,
                        level=500,
                        delay_all=0,
                        delay_user=0,
                        can_execute_with_whisper=True,
                        ),
                    }
                )

    def enable(self, bot):
        self.bot = bot
        self.checkjob.resume()
        self.checkPaused = False
    def disable(self, bot):
        self.checkjob.pause()
        self.checkPaused = True
