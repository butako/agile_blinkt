#!/usr/bin/env python3

"""
    AGILE BLINKT!

    An Octopus Agile and Energy Consumption Visualizer.

    This script is written to be used with the Pimoroni Blinkt LED board,
    Octopus Energy Agile price tariff, and a live power consumption/export
    feed (e.g. from Open Emon CMS). Of course, you could use other similar data sources if available. 

    It displays a Larson oscillating LED display (aka Knight Rider)
    that changes speed and changes colour according to the power consumption,
    power export, or Agile price at the moment.

    The more energy that's being consumed (or generated) the faster the LED animation.

    The higher the Agile price the more red the colour gets, the lower the price
    the more blue it gets (negative prices), and if exporting energy the 
    color is sunshine yellow! yay!

    All data is received over MQTT, one topic per field. I chose this method
    because MQTT was easy to integrate with Home Assistant. HA has excellent support
    for many add-ons and many IoT devices, it has custom components for collecting
    prices from Agile and power from EmonCMS. So overall it makes a good 'hub'. 

    I wrote this script to help my family to be more aware of the current 
    energy consumption, generation and prices. And with a bit luck, create some behaviour
    changes! It's intended to be a passive piece of furniture, intuitively
    visualizing our homes energy data. 

    Enjoy.

    Components used:
        Pimoroni Blinkt board: https://shop.pimoroni.com/products/blinkt
        Octopus Energy Agile: https://octopus.energy/agile/ 
        EmonCMS power monitor: https://openenergymonitor.org/ 
        Home Assistant: https://www.home-assistant.io/

"""


from sys import exit

import paho.mqtt.client as mqtt
import blinkt
import argparse
import sys
import time
import math
import colorsys


# A global dict that is used to store the input data received from MQTT
# The key is the MQTT topic, and value is that received from MQTT.
DATA = {}


def on_connect(client, userdata, flags, rc):
    """
    MQTT Client on_connect callback. 
    Subscribes to the MQTT required topics for price and power.
    """
    print("Connected with result code " + str(rc))
    print("Subscribing to topics:")
    print(f"  Octopus price: {userdata.topic_octopus}")
    print(f"  Import power: {userdata.topic_import}")
    print(f"  Export power: {userdata.topic_export}")
    topics = [
        (t, 0)
        for t in [userdata.topic_octopus, userdata.topic_import, userdata.topic_export]
        if not t is None
    ]
    client.subscribe(topics)


def on_message(client, userdata, msg):
    """
    MQTT Client on_message callback.
    Consumes the messages from MQTT and stores the values received into 
    the DATA global dict. 
    The topic payload is expected to be a float.
    """
    global DATA
    print(
        "Received message '"
        + str(msg.payload)
        + "' on topic '"
        + msg.topic
        + "' with QoS "
        + str(msg.qos)
    )
    DATA[msg.topic] = float(msg.payload)


def setup_mqtt(mqtt_server, mqtt_port, mqtt_user, mqtt_passwd, userdata):
    """
    Create MQTT Client, connect it to the server and wire up callbacks.
    """
    client = mqtt.Client(
        client_id="Agile Blinkt!", clean_session=True, userdata=userdata
    )
    client.on_connect = on_connect
    client.on_message = on_message

    if mqtt_user is not None and mqtt_passwd is not None:
        print(
            "Using username: {un} and password: {pw}".format(
                un=mqtt_user, pw="*" * len(mqtt_passwd)
            )
        )
        client.username_pw_set(username=mqtt_user, password=mqtt_passwd)

    print(f"Connecting to MQTT server: {mqtt_server}:{mqtt_port}")
    client.connect(mqtt_server, mqtt_port, 60)

    return client


def animation_loop(
    client, topic_import, topic_export, topic_octopus, high_usage, high_price, low_price
):
    """
    Main animation loop.
    """

    # Initialize our global DATA dict for holding all the power & price data
    global DATA
    DATA[topic_import] = 0.0
    DATA[topic_export] = 0.0
    DATA[topic_octopus] = 0.0

    # Setup Blinkt
    blinkt.set_clear_on_exit()
    blinkt.set_brightness(1.0)

    # This is the Knight Rider car pulsing animation.
    LARSON = [0, 0, 0, 0, 0, 16, 64, 255, 64, 16, 0, 0, 0, 0, 0, 0]
    delta = 0
    last_time = time.time()

    # The main loop...
    while True:
        # Calling mqtt client loop will give mqtt a chance to service any
        # incoming messages and invoke the callbacks that update DATA.
        # A timeout of 0 is used so that timing of the animation is not effected.
        client.loop(timeout=0)

        import_elec = DATA[topic_import]
        export_elec = DATA[topic_export]
        price = DATA[topic_octopus]
        # elec_rate is either consumption or export power, whichever is greater
        # expressed as a ratio of what is considered a high value (aka high water mark)
        # The Larson will complete approx 1 cycle per second when the elec_rate is 1.0
        elec_rate = max(import_elec, export_elec) / high_usage
        if elec_rate == 0.0:
            print("No electricity consumption or export yet received...")
            time.sleep(1)
            continue

        loop_time = time.time() - last_time
        last_time = time.time()

        # number of chunks to cover a full 2pi per second, scaled by the elec rate
        chunks = (1.0 / elec_rate) / loop_time
        # step animation forward by the appropriate chunk size in radians
        delta += (2 * math.pi) / chunks
        # Offset is a sine wave derived from the delta
        # This has the effect of spending a little more time at either end
        # of the LED blinkt board.
        offset = (math.sin(delta) + 1) / 2

        # Now we generate a value from 0 to max_val
        # Offset now points to a pixel...
        offset = int(round(offset * (blinkt.NUM_PIXELS - 1)))

        # Next, we determine a colour for the pixels.
        # Exporting = Yellow (for sunshine!)
        # Importing = Blue (low price) to Red (high price)
        if export_elec <= 0:
            # Importing, use the price to determine the colour
            # Rebase the price to be a positive range from 0 to High+abs(Low)
            price_rebased = max(0, price + abs(low_price))
            price_ratio = min(price_rebased / (high_price + abs(low_price)), 1.0)
            # 120 hue is Green, 240 is Blue, 360 is Red.
            # Starting from Blue, going through to Red, use price_ratio to determine intensity.
            hue = ((120 * price_ratio) + 240) / 360  # blue to red
        else:
            # If exporting, use sunshine yellow! 60 is yellow.
            hue = 60 / 360

        # Convert HSV to RGB. Remember Hue is a float, expressed as a ratio of 360 degrees.
        r, g, b = [c for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
        # DEBUG (TODO: use logging?)
        # print(f"last_time={last_time},rate={elec_rate}, offset={offset}, price={price}, hue={hue}")

        # Set each pixel value, using the Larson animation frames, offset in animation,
        # and the colour as influenced by the price.
        for x in range(blinkt.NUM_PIXELS):
            larson_val = LARSON[offset + x]
            blinkt.set_pixel(x, r * larson_val, g * larson_val, b * larson_val)

        # Showtime!
        blinkt.show()
        time.sleep(0.001)


def main():
    """
    Main loop.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--mqtt_server", help="MQTT Server hostname", required=True
    )
    parser.add_argument(
        "-t", "--mqtt_port", type=int, help="MQTT Server port", default=1883
    )
    parser.add_argument("-u", "--mqtt_user", help="MQTT username", required=False)
    parser.add_argument("-p", "--mqtt_passwd", help="MQTT password", required=False)
    parser.add_argument(
        "-o",
        "--topic_octopus",
        help="Topic of the Octopus Agile price in pence",
        required=True,
    )
    parser.add_argument(
        "-i",
        "--topic_import",
        help="Topic of import electricity power in W",
        required=True,
    )
    parser.add_argument(
        "-x",
        "--topic_export",
        help="Topic of export electricity power in W",
        required=False,
    )
    parser.add_argument(
        "-g",
        "--high_usage",
        help="Power considered a high usage for scaling the animation speed. When power reaches this level the Larson pulse cycles approx once-per-second. Value in Watts.",
        type=int,
        default=2000,
        required=False,
    )
    parser.add_argument(
        "--low_price",
        type=int,
        help="Low price used for colour scaling, can be negative",
        default=-5,
    )
    parser.add_argument(
        "--high_price", type=int, help="High price used for colour scaling", default=25
    )
    args = parser.parse_args()
    client = setup_mqtt(
        args.mqtt_server, args.mqtt_port, args.mqtt_user, args.mqtt_passwd, args
    )
    animation_loop(
        client,
        args.topic_import,
        args.topic_export,
        args.topic_octopus,
        args.high_usage,
        args.high_price,
        args.low_price,
    )


if __name__ == "__main__":
    sys.exit(not main())
