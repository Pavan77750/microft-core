import time
from threading import Thread

from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill


class Mark1DemoSkill(MycroftSkill):
    def __init__(self):
        super(Mark1DemoSkill, self).__init__("Mark1DemoSkill")
        self.animations = []
        self.playing = True
        self.thread = None

    def initialize(self):
        self.emitter.on("mycroft.mark1.demo", self.demo)

    def animate(self, t, often, func, *args):
        t = time.time() + t
        self.animations.append({
            "time": t,
            "often": often,
            "func": func,
            "args": args
        })

    def __get_time(self, often, t):
        return often - t % often

    def run(self):
        while self.playing:
            for animation in self.animations:
                if animation["time"] <= time.time():
                    animation["func"](*animation["args"])
                    if type(animation["often"]) is int:
                        animation["time"] = time.time() + animation["often"]
                    else:
                        often = int(animation["often"])
                        t = animation["time"]
                        animation["time"] = time.time() + self.__get_time(
                            often, t)
            time.sleep(0.1)

    def demo(self, message):
        self.animate(0, 8, self.enclosure.eyes_look, "r")
        self.animate(2, 8, self.enclosure.eyes_look, "l")
        self.animate(4, 8, self.enclosure.eyes_look, "d")
        self.animate(6, 8, self.enclosure.eyes_look, "u")
        self.animate(self.__get_time(120, time.time()), "120",
                     self.emitter.emit, Message("mycroft.sing"))
        self.thread = Thread(None, self.run)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.playing = False
        if self.thread:
            self.thread.cancel()
        self.enclosure.eyes_reset()


def create_skill():
    return Mark1DemoSkill()
