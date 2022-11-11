import machine, ubinascii
import time, socket, network, _thread
from umqtt.simple import MQTTClient
import config
from led import LED

import machine 

# Initialization
restarting = False
last_update = time.time()
connection_led = LED(config.connection_led_pin, 0)
main_loop_errors = 0
button1 = machine.Pin(config.button1_pin)

# Networking
SSID = config.wifi_ssid
WIFI_PASSWORD = config.wifi_password
station = network.WLAN(network.STA_IF)

station.active(True)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 80))
s.listen(5)

# MQTT
mqttc = None
mqttc_isconnected = False

# Button debouncer
button1_is_held = False

def reset_device():
    """
    Restarts the software for the ESP32 based on an MQTT call - hopefully never necessary, but could prove useful
    """
    global restarting
    global connection_led

    led_indicator = 1
    connection_led.blink_start()
    restarting = True

    for i in range(config.seconds_to_wait_after_reset_call):
        print("Resetting in {} seconds".format(config.seconds_to_wait_after_reset_call - i))
        time.sleep(1)

    machine.reset()
        
def connect_wifi():
    """
    Connect to the WiFi network
    """
    global connection_led

    try:        
        connection_led.blink_start()

        station.connect(SSID, WIFI_PASSWORD)
        
        print("Connecting to %s" % SSID)
        pending = ''

        while station.isconnected() == False:
            pending += '.'

            if len(pending) > 15:
                pending = '.'
 
            print(".", end="")
            time.sleep(.5)

        print()
        print("WiFi connection successful")
        print(station.ifconfig())
        connection_led.blink_stop(1)
        
        connect_mqtt()
        
    except OSError as e:
        print("ERROR: Unable to connect to the SSID %s" % SSID)
        print(e)

def mqtt_callback(topic, msg):
    """
    Process incoming MQTT events from subscription(s)
    """
    global last_update
    global connection_led
    
    print('Received subscribed topic message')
    print(topic, msg)
    connection_led.set_state(0)
    
    if topic == config.reset_topic.encode():
        reset_device()

    connection_led.set_state(1)
    
def connect_mqtt():
    """
    Connect to the MQTT broker and set up subscription(s)
    """
    global mqttc
    global mqttc_isconnected
    global connection_led
    
    connection_led.blink_start()
    mqttc_isconnected = False
    print('Connecting to MQTT broker')

    try:
        # Use the machine's unique ID as the client_id by default
        client_id = ubinascii.hexlify(machine.unique_id())

        # If the client_id has been overridden in the config, use that instead
        if config.mqtt_client_id != None:
            client_id = config.mqtt_client_id
            
        # Connect to the MQTT broker, setting the callback and subscrption(s)
        mqtt_server = config.mqtt_broker
        mqttc = MQTTClient(client_id, mqtt_server, user=config.mqtt_user_id, password=config.mqtt_password, keepalive=config.mqtt_keep_alive_interval_in_seconds)
        mqttc.set_callback(mqtt_callback)
        mqttc.connect()
        mqttc_isconnected = True        
        
        mqttc.subscribe(config.reset_topic.encode())

        connection_led.blink_stop(1)

        print('Connection Successful')
    except OSError as e:
        print(e)
        time.sleep(30)

def mqtt_publish_button_press(topic):
    """
    Send the button press signal to the MQTT broker
    """
    print('Button pressed, publishing to topic ' + config.button1_pressed_topic)
    if mqttc_isconnected:
        try:
            mqttc.publish(topic.encode(), b'')
        except OSError as e:
            print(e)
    else:
        pass

def main():
    """
    Constant loop to check for connectivity, button state, etc
    """
    global last_update
    global button1_is_held
    global main_loop_errors

    while True:
        try:            
            if (not station.isconnected()):
                connect_wifi()
            
            try:
                # See if there are any pending MQTT messages
                if mqttc_isconnected:
                    mqttc.check_msg()
                else:
                    connect_mqtt()
            except OSError as e:
                print(str(e))        
                connect_mqtt()

            
            now = time.time()

            # Is it time to ping for keep alive/connection check?
            if now - last_update >= config.mqtt_keep_alive_interval_in_seconds:   
                try:
                    mqttc.ping()
                    mqttc.wait_msg()
                    last_update = now
                except OSError as e:
                    print(e)
                    connect_mqtt()

            # Check to see if the button has been pressed or not
            button1_is_pressed = button1.value()

            if (button1_is_pressed == 1 and not button1_is_held):
                # Publish MQTT that the button is pressed, accounting for it not being released since the last press
                button1_is_held = True
                mqtt_publish_button_press(config.button1_pressed_topic)
                time.sleep(.25)
            elif not button1_is_pressed:
                button1_is_held = False

        except OSError as e:
            print(e)
            
            if main_loop_errors == 5:
                reset_device()
            else:
                main_loop_errors += 1
                time.sleep(5)

# Make initial WiFi connection, then run the main loop.  
# The initial connection is important to prevent issues with timing and multiple calls to connect
connect_wifi()
main()        
