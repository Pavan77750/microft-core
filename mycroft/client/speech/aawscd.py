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

import time
import subprocess
from mycroft.util.log import getLogger
import pyaudio
logger = getLogger("AAWSCD Module")

"""
    This module has helper functions to interface with the aawscd daemon
"""


def stop_aawscd():
    """Stops the aawscd dameon so pyaudio doesn't hang
    """
    # Stop aawscd if it is running
    logger.info("stoping aawscd if it's on")
    output = subprocess.check_output(['initctl', 'status', 'aawscd'])
    if "stop" not in output:
        subprocess.call(['sudo', 'initctl', 'stop', 'aawscd'])
        output = subprocess.check_output(['initctl', 'status', 'aawscd'])
        if "stop" not in output:
            logger.error("Could not stop aawscd, exiting")
            sys.exit()


def start_aawscd():
    """Start the aawscd daemon after loading all of pyaudio stuff
        sometimes this will as you to type in password - need a way to
        prevent that
    """
    logger.info("starting aawscd if it's off")
    ot = subprocess.check_output(['initctl', 'status', 'aawscd'])
    if "start" in ot:
        logger.info("already started")
        return
    subprocess.call(['sudo', 'initctl', 'start', 'aawscd'])
    output = subprocess.check_output(['initctl', 'status', 'aawscd'])
    if "start" not in output:
        logger.error("Could not start aawscd, exiting")
        sys.exit()
    time.sleep(0.5)


def get_aawscd_device_id():
    p = pyaudio.PyAudio()
    # Find index of aawaloop sound card
    idev = -1
    for i in range(p.get_device_count()):
        devinf = p.get_device_info_by_index(i)
        if "aawaloop" in devinf['name']:
            idev = i
            continue

    if idev == -1:
        logger.info("Could not find aawaloop device")
        return None
    return idev
