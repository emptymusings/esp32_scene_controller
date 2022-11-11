from machine import Pin
import _thread, time

class LED:
  def __init__(self, pin, initial_state=0):
    global _flash

    self._pin = Pin(pin, Pin.OUT)
    self._pin.value(initial_state)
    _flash = 0
    self._flash_interval = .25

  def get_state(self):
    return self._pin.value()

  def set_state(self, value):
    self._pin.value(value)

  def flip_state(self):
    self._pin.value(1 - self._pin.value())

  def blink_start(self, interval=.25):
    global _flash

    _flash = 1
    self._flash_interval = interval
    _thread.start_new_thread(self._do_blink, ())

  def blink_stop(self, end_state=1):
    global _flash

    _flash = 0
    time.sleep(.5)
    self._pin.value(end_state)
    
  def _do_blink(self):
    global _flash
    while _flash == 1:
      self.flip_state()
      time.sleep(self._flash_interval)
