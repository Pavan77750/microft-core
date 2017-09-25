# Copyright 2017 Mycroft AI, Inc.
#
# This file is part of Mycroft Core.
#
# Mycroft Core is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Mycroft Core is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Mycroft Core.  If not, see <http://www.gnu.org/licenses/>.

from mycroft.configuration import ConfigurationManager
from mycroft.util.log import getLogger
from mycroft.client.speech.aawscd import start_aawscd
from os.path import dirname, exists, join, abspath
import os
import time
import tempfile
import socket
import json
from threading import Thread

__author__ = 'seanfitz, jdorleans, jarbas'

LOG = getLogger("HotwordFactory")

RECOGNIZER_DIR = join(abspath(dirname(__file__)), "recognizer")


class HotWordEngine(object):
    def __init__(self, key_phrase="hey mycroft", config=None, lang="en-us"):
        self.lang = str(lang).lower()
        self.key_phrase = str(key_phrase).lower()
        # rough estimate 1 phoneme per 2 chars
        self.num_phonemes = len(key_phrase) / 2 + 1
        if config is None:
            config = ConfigurationManager.get().get("hot_words", {})
            config = config.get(self.key_phrase, {})
        self.config = config
        self.listener_config = ConfigurationManager.get().get("listener", {})

    def found_wake_word(self, frame_data):
        return False


class PocketsphinxHotWord(HotWordEngine):
    def __init__(self, key_phrase="hey mycroft", config=None, lang="en-us"):
        super(PocketsphinxHotWord, self).__init__(key_phrase, config, lang)
        # Hotword module imports
        from pocketsphinx import Decoder
        # Hotword module config
        module = self.config.get("module")
        if module != "pocketsphinx":
            LOG.warning(
                str(module) + " module does not match with "
                              "Hotword class pocketsphinx")
        # Hotword module params
        self.phonemes = self.config.get("phonemes", "HH EY . M AY K R AO F T")
        self.num_phonemes = len(self.phonemes.split())
        self.threshold = self.config.get("threshold", 1e-90)
        self.sample_rate = self.listener_config.get("sample_rate", 1600)
        dict_name = self.create_dict(key_phrase, self.phonemes)
        config = self.create_config(dict_name, Decoder.default_config())
        self.decoder = Decoder(config)

    def create_dict(self, key_phrase, phonemes):
        (fd, file_name) = tempfile.mkstemp()
        words = key_phrase.split()
        phoneme_groups = phonemes.split('.')
        with os.fdopen(fd, 'w') as f:
            for word, phoneme in zip(words, phoneme_groups):
                f.write(word + ' ' + phoneme + '\n')
        return file_name

    def create_config(self, dict_name, config):
        model_file = join(RECOGNIZER_DIR, 'model', self.lang, 'hmm')
        if not exists(model_file):
            LOG.error('PocketSphinx model not found at ' + str(model_file))
        config.set_string('-hmm', model_file)
        config.set_string('-dict', dict_name)
        config.set_string('-keyphrase', self.key_phrase)
        config.set_float('-kws_threshold', float(self.threshold))
        config.set_float('-samprate', self.sample_rate)
        config.set_int('-nfft', 2048)
        config.set_string('-logfn', '/dev/null')
        return config

    def transcribe(self, byte_data, metrics=None):
        start = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(byte_data, False, False)
        self.decoder.end_utt()
        if metrics:
            metrics.timer("mycroft.stt.local.time_s", time.time() - start)
        return self.decoder.hyp()

    def found_wake_word(self, frame_data):
        hyp = self.transcribe(frame_data)
        return hyp and self.key_phrase in hyp.hypstr.lower()


class SnowboyHotWord(HotWordEngine):
    def __init__(self, key_phrase="hey mycroft", config=None, lang="en-us"):
        super(SnowboyHotWord, self).__init__(key_phrase, config, lang)
        # Hotword module imports
        from snowboydecoder import HotwordDetector
        # Hotword module config
        module = self.config.get("module")
        if module != "snowboy":
            LOG.warning(module + " module does not match with Hotword class "
                                 "snowboy")
        # Hotword params
        models = self.config.get("models", {})
        paths = []
        for key in models:
            paths.append(models[key])
        sensitivity = self.config.get("sensitivity", 0.5)
        self.snowboy = HotwordDetector(paths,
                                       sensitivity=[sensitivity] * len(paths))
        self.lang = str(lang).lower()
        self.key_phrase = str(key_phrase).lower()

    def found_wake_word(self, frame_data):
        wake_word = self.snowboy.detector.RunDetection(frame_data)
        return wake_word == 1


class AAWHotWord(HotWordEngine):
    def __init__(self, key_phrase="hey mycroft", config=None, lang="en-us"):
        super(AAWHotWord, self).__init__(key_phrase, config, lang)
        LOG.info("aaw init")
        self.activate = False
        event_thread = Thread(target=self.listen_to_aawscd)
        event_thread.setDaemon(True)
        event_thread.start()

    def listen_to_aawscd(self):
        LOG.info("connecting to aawscd socket")
        start_aawscd()
        clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientSocket.connect(('localhost', 8889))

        while True:
            msg = self.read_msg(clientSocket)
            if msg:
                LOG.info("found wakeword")
                self.activate = True

    def read_blob(self, sock, size):
        buf = ""
        while len(buf) != size:
            ret = sock.recv(size - len(buf))
            if not ret:
                raise Exception("Socket closed")
            buf += ret
        return buf

    def read_header(self, sock):
        data = self.read_blob(sock, 4)
        return int(data)

    def read_body(self, sock, size):
        data = self.read_blob(sock, size)
        return json.loads(data)

    def read_msg(self, sock):
        size = self.read_header(sock)
        return self.read_body(sock, size)

    def print_msg(self, msg):
        LOG.info('Detected ' + msg['detect']['phrase'] +
                 ' in direction ' + repr(msg['detect']['azimuth']) +
                 ' at ' + msg['detect']['time'])

    def found_wake_word(self, frame_data=None):
        LOG.info("aaw")
        if self.activate is True:
            LOG.info("found wake word")
            self.activate = False
            return True
        else:
            return False


class HotWordFactory(object):
    CLASSES = {
        "pocketsphinx": PocketsphinxHotWord,
        "snowboy": SnowboyHotWord,
        "aaw": AAWHotWord
    }

    @staticmethod
    def create_hotword(hotword="hey mycroft", config=None, lang="en-us"):
        LOG.info("creating " + hotword)
        if not config:
            config = ConfigurationManager.get().get("hotwords", {})
        module = config.get(hotword).get("module", "pocketsphinx")
        config = config.get(hotword, {"module": module})
        clazz = HotWordFactory.CLASSES.get("aaw")
        LOG.info(clazz)
        return clazz(hotword, config, lang=lang)
