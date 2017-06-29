#
# Copyright (c) 2017 Mycroft AI, Inc.
#
# This file is part of Mycroft Simple
# (see https://github.com/MatthewScholefield/mycroft-simple).
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
import json
import os
import subprocess
from os import chdir, getcwd
from os.path import isfile, isdir
from subprocess import Popen, call
from threading import Event, Thread

from websocket_server import WebsocketServer

from mycroft.engines.intent_engine import IntentEngine, make_namespaced

## pulled from intent_service:

from adapt.engine import IntentDeterminationEngine
from mycroft.messagebus.message import Message
from mycroft.skills.core import open_intent_envelope
from mycroft.util.log import getLogger
from mycroft.util.parse import normalize

logger = getLogger(__name__)


class AdaptEngine(IntentEngine):
    """Interface between Adapt and Mycroft"""

    def __init__(self, emitter):
        self.engine = IntentDeterminationEngine()
        self.emitter = emitter
        self.emitter.on('register_vocab', self.handle_register_vocab)
        self.emitter.on('register_intent', self.try_register_intent)
        self.emitter.on('recognizer_loop:utterance', self.calc_intents)
        self.emitter.on('detach_intent', self.handle_detach_intent)
        self.emitter.on('detach_skill', self.handle_detach_skill)


    def calc_intents(self, query):
        # Get language of the utterance
        lang = query.data.get('lang', None)
        if not lang:
            lang = "en-us"

        utterances = query.data.get('utterances', '')

        best_intent = None
        for utterance in utterances:
            try:
                # normalize() changes "it's a boy" to "it is boy", etc.
                best_intent = next(self.engine.determine_intent(
                    normalize(utterance, lang), 100))

                # TODO - Should Adapt handle this?
                best_intent['utterance'] = utterance
            except StopIteration, e:
                logger.exception(e)
                continue

        if best_intent and best_intent.get('confidence', 0.0) > 0.0:
            reply = query.reply(
                best_intent.get('intent_type'), best_intent)
            self.emitter.emit(reply)
            return reply
        else:
            self.emitter.emit(Message("intent_failure", {
                "utterance": utterances[0],
                "lang": lang
            }))

    def try_register_intent(self, request, parameters ={}):
        intent = open_intent_envelope(request)
        self.engine.register_intent_parser(intent)
        return intent

    def handle_register_vocab(self, message):
        start_concept = message.data.get('start')
        end_concept = message.data.get('end')
        regex_str = message.data.get('regex')
        alias_of = message.data.get('alias_of')
        if regex_str:
            self.engine.register_regex_entity(regex_str)
        else:
            self.engine.register_entity(
                start_concept, end_concept, alias_of=alias_of)

    def handle_register_intent(self, message):
        """TODO: Remove once certain no issues"""
        intent = open_intent_envelope(message)
        self.engine.register_intent_parser(intent)

    def handle_detach_intent(self, message):
        intent_name = message.data.get('intent_name')
        new_parsers = [
            p for p in self.engine.intent_parsers if p.name != intent_name]
        self.engine.intent_parsers = new_parsers

    def handle_detach_skill(self, message):
        skill_name = message.data.get('skill_name')
        new_parsers = [
            p for p in self.engine.intent_parsers if
            not p.name.startswith(skill_name)]
        self.engine.intent_parsers = new_parsers