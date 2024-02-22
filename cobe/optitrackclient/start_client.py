﻿# Copyright © 2018 Naturalpoint
#
# Licensed under the Apache License, Version 2.0 (the "License")
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# OptiTrack NatNet direct depacketization sample for Python 3.x
#
# Uses the Python NatNetClient.py library to establish a connection (by creating a NatNetClient),
# and receive data via a NatNet connection and decode it using the NatNetClient library.

import sys
import time

from cobe.cobe.cobemasterabm import generate_pred_json_abm
from cobe.optitrackclient.NatNetClient import NatNetClient
import cobe.optitrackclient.DataDescriptions as DataDescriptions
import cobe.optitrackclient.MoCapData as MoCapData

from cobe.pmodule.pmodule import generate_pred_json

import cobe.settings.optitrack as otsettings

# setting the size of the virtual arena according to the mode, i.e. the
# simulation engine CoBe is connected. E.g. this is usually 40x40 for the original
# PModule, but 500x500 for the ABM simulation.
if otsettings.mode == "abm":
    import cobe.settings.abm_simulation as abm_settings

    max_abs_coord = abm_settings.max_abs_coord
else:
    import cobe.settings.pmodulesettings as cobe_settings

    max_abs_coord = cobe_settings.max_abs_coord

# global variable to store and update the rigid bodies
rigid_bodies = {}


# This is a callback function that gets connected to the NatNet client
# and called once per mocap frame.
def receive_new_frame(data_dict):
    global rigid_bodies
    try:
        if otsettings.mode == "cobe":
            # using PModule input convention
            list_to_write = [[key, value[0], value[1]] for key, value in rigid_bodies.items()]
            generate_pred_json(list_to_write, with_explicit_IDs=True)

        elif otsettings.mode == "abm":
            # using PyGame ABM input convention
            list_to_write = [[key, value[0], -value[1]] for key, value in rigid_bodies.items()]
            generate_pred_json_abm(list_to_write, with_explicit_ids=True)

        else:
            raise ValueError("Mode not supported: ", otsettings.mode)

    except ValueError as e:
        print("ValueError: ", e)
        print("rigid_bodies: ", rigid_bodies)


# This is a callback function that gets connected to the NatNet client. It is called once per rigid body per frame
def receive_rigid_body_frame(new_id, position, rotation):
    global rigid_bodies

    # get position according to ground plane conmvention
    x, y = position[0], position[2]

    # rescaling to original arena size
    x_rescale = otsettings.x_rescale
    y_rescale = otsettings.y_rescale

    # rescaling and matching the directions in the arena
    # please keep convention of ground plane in Motive as defined in settings
    x = - x / x_rescale * max_abs_coord
    y = y / y_rescale * max_abs_coord

    # update rigid bodies global data that will be only written with every frame to the file
    if otsettings.mode == "cobe":
        rigid_bodies[new_id] = [x, y]
    elif otsettings.mode == "abm":
        rigid_bodies[new_id] = [x, y, rotation]
    else:
        raise ValueError("Mode not supported: ", otsettings.mode)


def add_lists(totals, totals_tmp):
    totals[0] += totals_tmp[0]
    totals[1] += totals_tmp[1]
    totals[2] += totals_tmp[2]
    return totals


def print_configuration(natnet_client):
    natnet_client.refresh_configuration()
    print("Connection Configuration:")
    print("  Client:          %s" % natnet_client.local_ip_address)
    print("  Server:          %s" % natnet_client.server_ip_address)
    print("  Command Port:    %d" % natnet_client.command_port)
    print("  Data Port:       %d" % natnet_client.data_port)

    if natnet_client.use_multicast:
        print("  Using Multicast")
        print("  Multicast Group: %s" % natnet_client.multicast_address)
    else:
        print("  Using Unicast")

    # NatNet Server Info
    application_name = natnet_client.get_application_name()
    nat_net_requested_version = natnet_client.get_nat_net_requested_version()
    nat_net_version_server = natnet_client.get_nat_net_version_server()
    server_version = natnet_client.get_server_version()

    print("  NatNet Server Info")
    print("    Application Name %s" % (application_name))
    print("    NatNetVersion  %d %d %d %d" % (
        nat_net_version_server[0], nat_net_version_server[1], nat_net_version_server[2], nat_net_version_server[3]))
    print(
        "    ServerVersion  %d %d %d %d" % (server_version[0], server_version[1], server_version[2], server_version[3]))
    print("  NatNet Bitstream Requested")
    print("    NatNetVersion  %d %d %d %d" % (nat_net_requested_version[0], nat_net_requested_version[1], \
                                              nat_net_requested_version[2], nat_net_requested_version[3]))
    # print("command_socket = %s"%(str(natnet_client.command_socket)))
    # print("data_socket    = %s"%(str(natnet_client.data_socket)))


def print_commands(can_change_bitstream):
    outstring = "Commands:\n"
    outstring += "Return Data from Motive\n"
    outstring += "  s  send data descriptions\n"
    outstring += "  r  resume/start frame playback\n"
    outstring += "  p  pause frame playback\n"
    outstring += "     pause may require several seconds\n"
    outstring += "     depending on the frame data size\n"
    outstring += "Change Working Range\n"
    outstring += "  o  reset Working Range to: start/current/end frame = 0/0/end of take\n"
    outstring += "  w  set Working Range to: start/current/end frame = 1/100/1500\n"
    outstring += "Return Data Display Modes\n"
    outstring += "  j  print_level = 0 supress data description and mocap frame data\n"
    outstring += "  k  print_level = 1 show data description and mocap frame data\n"
    outstring += "  l  print_level = 20 show data description and every 20th mocap frame data\n"
    outstring += "Change NatNet data stream version (Unicast only)\n"
    outstring += "  3  Request 3.1 data stream (Unicast only)\n"
    outstring += "  4  Request 4.1 data stream (Unicast only)\n"
    outstring += "t  data structures self test (no motive/server interaction)\n"
    outstring += "c  show configuration\n"
    outstring += "h  print commands\n"
    outstring += "q  quit\n"
    outstring += "\n"
    outstring += "NOTE: Motive frame playback will respond differently in\n"
    outstring += "       Endpoint, Loop, and Bounce playback modes.\n"
    outstring += "\n"
    outstring += "EXAMPLE: PacketClient [serverIP [ clientIP [ Multicast/Unicast]]]\n"
    outstring += "         PacketClient \"192.168.10.14\" \"192.168.10.14\" Multicast\n"
    outstring += "         PacketClient \"127.0.0.1\" \"127.0.0.1\" u\n"
    outstring += "\n"
    print(outstring)


def request_data_descriptions(s_client):
    # Request the model definitions
    s_client.send_request(s_client.command_socket, s_client.NAT_REQUEST_MODELDEF, "",
                          (s_client.server_ip_address, s_client.command_port))


def test_classes():
    totals = [0, 0, 0]
    print("Test Data Description Classes")
    totals_tmp = DataDescriptions.test_all()
    totals = add_lists(totals, totals_tmp)
    print("")
    print("Test MoCap Frame Classes")
    totals_tmp = MoCapData.test_all()
    totals = add_lists(totals, totals_tmp)
    print("")
    print("All Tests totals")
    print("--------------------")
    print("[PASS] Count = %3.1d" % totals[0])
    print("[FAIL] Count = %3.1d" % totals[1])
    print("[SKIP] Count = %3.1d" % totals[2])


def my_parse_args(arg_list, args_dict):
    # set up base values
    arg_list_len = len(arg_list)
    if arg_list_len > 1:
        args_dict["serverAddress"] = arg_list[1]
        if arg_list_len > 2:
            args_dict["clientAddress"] = arg_list[2]
        if arg_list_len > 3:
            if len(arg_list[3]):
                args_dict["use_multicast"] = True
                if arg_list[3][0].upper() == "U":
                    args_dict["use_multicast"] = False

    return args_dict


def start():
    """Fully from OptiTrack NatNet SDK"""
    optionsDict = {}
    optionsDict["clientAddress"] = otsettings.client_address
    optionsDict["serverAddress"] = otsettings.server_address
    optionsDict["use_multicast"] = otsettings.use_multicast

    # This will create a new NatNet client
    optionsDict = my_parse_args(sys.argv, optionsDict)

    streaming_client = NatNetClient()
    streaming_client.set_client_address(optionsDict["clientAddress"])
    streaming_client.set_server_address(optionsDict["serverAddress"])
    streaming_client.set_use_multicast(optionsDict["use_multicast"])

    # Configure the streaming client to call our rigid body handler on the emulator to send data out.
    streaming_client.new_frame_listener = receive_new_frame
    streaming_client.rigid_body_listener = receive_rigid_body_frame

    # Start up the streaming client now that the callbacks are set up.
    # This will run perpetually, and operate on a separate thread.
    is_running = streaming_client.run()
    if not is_running:
        print("ERROR: Could not start streaming client.")
        try:
            sys.exit(1)
        except SystemExit:
            print("...")
        finally:
            print("exiting")

    is_looping = True
    time.sleep(1)
    if streaming_client.connected() is False:
        print("ERROR: Could not connect properly.  Check that Motive streaming is on.")
        try:
            sys.exit(2)
        except SystemExit:
            print("...")
        finally:
            print("exiting")

    print_configuration(streaming_client)
    print("\n")
    print_commands(streaming_client.can_change_bitstream_version())

    while is_looping:
        inchars = input('Enter command or (\'h\' for list of commands)\n')
        if len(inchars) > 0:
            c1 = inchars[0].lower()
            if c1 == 'h':
                print_commands(streaming_client.can_change_bitstream_version())
            elif c1 == 'c':
                print_configuration(streaming_client)
            elif c1 == 's':
                request_data_descriptions(streaming_client)
                time.sleep(1)
            elif (c1 == '3') or (c1 == '4'):
                if streaming_client.can_change_bitstream_version():
                    tmp_major = 4
                    tmp_minor = 1
                    if (c1 == '3'):
                        tmp_major = 3
                        tmp_minor = 1
                    return_code = streaming_client.set_nat_net_version(tmp_major, tmp_minor)
                    time.sleep(1)
                    if return_code == -1:
                        print("Could not change bitstream version to %d.%d" % (tmp_major, tmp_minor))
                    else:
                        print("Bitstream version at %d.%d" % (tmp_major, tmp_minor))
                else:
                    print("Can only change bitstream in Unicast Mode")

            elif c1 == 'p':
                sz_command = "TimelineStop"
                return_code = streaming_client.send_command(sz_command)
                time.sleep(1)
                print("Command: %s - return_code: %d" % (sz_command, return_code))
            elif c1 == 'r':
                sz_command = "TimelinePlay"
                return_code = streaming_client.send_command(sz_command)
                print("Command: %s - return_code: %d" % (sz_command, return_code))
            elif c1 == 'o':
                tmpCommands = ["TimelinePlay",
                               "TimelineStop",
                               "SetPlaybackStartFrame,0",
                               "SetPlaybackStopFrame,1000000",
                               "SetPlaybackLooping,0",
                               "SetPlaybackCurrentFrame,0",
                               "TimelineStop"]
                for sz_command in tmpCommands:
                    return_code = streaming_client.send_command(sz_command)
                    print("Command: %s - return_code: %d" % (sz_command, return_code))
                time.sleep(1)
            elif c1 == 'w':
                tmp_commands = ["TimelinePlay",
                                "TimelineStop",
                                "SetPlaybackStartFrame,10",
                                "SetPlaybackStopFrame,1500",
                                "SetPlaybackLooping,0",
                                "SetPlaybackCurrentFrame,100",
                                "TimelineStop"]
                for sz_command in tmp_commands:
                    return_code = streaming_client.send_command(sz_command)
                    print("Command: %s - return_code: %d" % (sz_command, return_code))
                time.sleep(1)
            elif c1 == 't':
                test_classes()

            elif c1 == 'j':
                streaming_client.set_print_level(0)
                print("Showing only received frame numbers and supressing data descriptions")
            elif c1 == 'k':
                streaming_client.set_print_level(1)
                print("Showing every received frame")

            elif c1 == 'l':
                print_level = streaming_client.set_print_level(20)
                print_level_mod = print_level % 100
                if (print_level == 0):
                    print("Showing only received frame numbers and supressing data descriptions")
                elif (print_level == 1):
                    print("Showing every frame")
                elif (print_level_mod == 1):
                    print("Showing every %dst frame" % print_level)
                elif (print_level_mod == 2):
                    print("Showing every %dnd frame" % print_level)
                elif (print_level == 3):
                    print("Showing every %drd frame" % print_level)
                else:
                    print("Showing every %dth frame" % print_level)

            elif c1 == 'q':
                is_looping = False
                streaming_client.shutdown()
                break
            else:
                print("Error: Command %s not recognized" % c1)
            print("Ready...\n")
    print("exiting")


if __name__ == "__main__":
    start()
