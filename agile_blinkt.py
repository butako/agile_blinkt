#!/usr/bin/env python3

from sys import exit

import paho.mqtt.client as mqtt
import blinkt
import argparse
import sys
import time
import math
import colorsys

DATA = {}

#./agile_blinkt.py  -s hassio -u kevin -p kevin -o homeassistant_statestream/sensor/octopus_agile_current_rate/state -i homeassistant_statestream/sensor/emoncms_import/state  -x homeassistant_statestream/sensor/elec_export/state


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    print("Subscribing to topics:")
    print(f"  Octopus price: {userdata.topic_octopus}")
    print(f"  Import power: {userdata.topic_import}")
    print(f"  Export power: {userdata.topic_export}")
    topics=[(t,0) for t in [userdata.topic_octopus, userdata.topic_import, userdata.topic_export] if not t is None]
    client.subscribe(topics)

def on_message(client, userdata, msg):
    global DATA
    print("Received message '" + str(msg.payload) + "' on topic '"
            + msg.topic + "' with QoS " + str(msg.qos))
    DATA[msg.topic] = float(msg.payload)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s","--mqtt_server", help="MQTT Server hostname", required=True)
    parser.add_argument("-t","--mqtt_port", type=int, help="MQTT Server port", default=1883)
    parser.add_argument("-u","--mqtt_user", help="MQTT username", required=False)
    parser.add_argument("-p","--mqtt_passwd", help="MQTT password", required=False)
    parser.add_argument("-o","--topic_octopus", help="Topic of the Octopus Agile price in pence", required=True)
    parser.add_argument("-i","--topic_import", help="Topic of import electricity power in W", required=True)
    parser.add_argument("-x","--topic_export", help="Topic of export electricity power in W", required=False)
    parser.add_argument("-g","--high_usage", help="Power considered a high usage for scaling the larson speed W", type=int, default=2000,required=False)
    
    args = parser.parse_args()

    client = mqtt.Client(client_id="Agile Blinkt!", clean_session=True, userdata=args)
    client.on_connect = on_connect
    client.on_message = on_message

    if args.mqtt_user is not None and args.mqtt_passwd is not None:
        print("Using username: {un} and password: {pw}".format(un=args.mqtt_user , pw="*" * len(args.mqtt_passwd)))
        client.username_pw_set(username=args.mqtt_user, password=args.mqtt_passwd)

    print(f"Connecting to MQTT server: {args.mqtt_server}:{args.mqtt_port}")
    client.connect(args.mqtt_server, args.mqtt_port, 60)


    DATA[args.topic_import]=0.0
    DATA[args.topic_export]=0.0
    DATA[args.topic_octopus]=0.0


    blinkt.set_clear_on_exit()

    MAXPRICE = 25.0
    MINPRICE = -5.0
    #LARSON = [0.0, 0.0, 0.0, 0.0, 0.0, 0.06, 0.25, 1.0, 0.25, 0.06, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    LARSON = [0, 0, 0, 0, 0, 16, 64, 255, 64, 16, 0, 0, 0, 0, 0, 0]

    # When power reaches this level the larson lights will complete
    # one swipe back'n'forth per second

    delta = 0
    last_time=time.time()
    blinkt.set_brightness(0.1)

    price_hack = -10
    while True:
        client.loop(timeout=0)

        import_elec = DATA[args.topic_import]
        export_elec = DATA[args.topic_export]
        price = DATA[args.topic_octopus]
        elec_rate = max(import_elec, export_elec) / args.high_usage
        if elec_rate==0.0:
            print("No electricity consumption or export received.")
            time.sleep(1)
            continue


        loop_time = (time.time() - last_time)
        last_time = time.time()

        # number of chunks to cover a full 2pi per second, scaled by the elec consumption rate
        chunks = (1.0/elec_rate)/loop_time 
        # step forward by the appropriate chunk size in radians
        delta += ((2*math.pi) / chunks) 

        # Offset is a sine wave derived from the time delta
        # we use this to animate both the hue and larson scan
        # so they are kept in sync with each other
        offset = (math.sin(delta) + 1) / 2


        # Now we generate a value from 0 to max_val
        # Offset now points to a pixel...
        offset = int(round(offset * (blinkt.NUM_PIXELS - 1)))

        #price_hack += 0.1
        #price = price_hack
        #if price_hack > MAXPRICE+10:
        #    price_hack = MINPRICE-10



        if import_elec > 0:
            # If importing, use the price to determine the colour
            # Rebase the price to be a positive range from 0 to MAX+abs(MIN)
            price_rebased = max(0, price+abs(MINPRICE))
            price_ratio = min(price_rebased/(MAXPRICE+abs(MINPRICE)),1.0)
            hue=((120*price_ratio)+240)/360  # blue to red
        else:
            # If exporting, use sunshine yellow
            hue=60/360

        r, g, b = [c for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
        #print(f"last_time={last_time},rate={elec_rate}, offset={offset}, price={price}, hue={hue}")

        for x in range(blinkt.NUM_PIXELS):
            larson_val=LARSON[offset + x]
            blinkt.set_pixel(x, r*larson_val, g*larson_val, b*larson_val)

        blinkt.show()

        time.sleep(0.001)        

       




if __name__ == '__main__':
  sys.exit(not main())