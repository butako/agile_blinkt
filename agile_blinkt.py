#!/usr/bin/env python3

from sys import exit

import paho.mqtt.client as mqtt
import blinkt
import argparse
import sys

DATA = {}

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    print("Subscribing to topics:")
    print(f"  Octopus price: {userdata.topic_octopus}")
    print(f"  Import power: {userdata.topic_import}")
    print(f"  Export power: {userdata.topic_export}")
    topics=[(t,0) for t in [userdata.topic_octopus, userdata.topic_import, userdata.topic_export] if not t is None]
    print(topics)
    client.subscribe(topics)

def on_message(client, userdata, msg):
    global DATA
    print("Received message '" + str(msg.payload) + "' on topic '"
            + msg.topic + "' with QoS " + str(msg.qos))

    data = str(msg.payload,'utf-8')
    DATA[msg.topic] = data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s","--mqtt_server", help="MQTT Server hostname", required=True)
    parser.add_argument("-t","--mqtt_port", type=int, help="MQTT Server port", default=1883)
    parser.add_argument("-u","--mqtt_user", help="MQTT username", required=False)
    parser.add_argument("-p","--mqtt_passwd", help="MQTT password", required=False)
    parser.add_argument("-o","--topic_octopus", help="Topic of the Octopus Agile price in pence", required=True)
    parser.add_argument("-i","--topic_import", help="Topic of import electricity power in W", required=True)
    parser.add_argument("-x","--topic_export", help="Topic of export electricity power in W", required=False)
    args = parser.parse_args()

    blinkt.set_clear_on_exit()

    client = mqtt.Client(client_id="Agile Blinkt!", clean_session=True, userdata=args)
    client.on_connect = on_connect
    client.on_message = on_message

    if args.mqtt_user is not None and args.mqtt_passwd is not None:
        print("Using username: {un} and password: {pw}".format(un=args.mqtt_user , pw="*" * len(args.mqtt_passwd)))
        client.username_pw_set(username=args.mqtt_user, password=args.mqtt_passwd)

    print(f"Connecting to MQTT server: {args.mqtt_server}:{args.mqtt_port}")
    client.connect(args.mqtt_server, args.mqtt_port, 60)

    while True:
        client.loop(timeout=0.01)
        # lights camera action!!


if __name__ == '__main__':
  sys.exit(not main())